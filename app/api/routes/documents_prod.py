from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from datetime import datetime
from typing import Optional

from app.schemas.schemas import DocumentUploadResponse
from app.services.document_loader_prod import DocumentLoaderService
from app.services.text_chunker_prod import TextChunkerService
from app.core.exceptions import DocumentParsingError, UnsupportedFileFormatError, FileSizeExceededError
from app.core.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/documents", tags=["Documents"])

loader = DocumentLoaderService()
chunker = TextChunkerService()

documents = {}
doc_counter = 0


def _gen_doc_id(filename: str) -> str:
    global doc_counter
    doc_counter += 1
    ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    return f"doc_{ts}_{doc_counter}"


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(file: UploadFile = File(...)) -> DocumentUploadResponse:
    try:
        filename = file.filename or "unnamed"
        logger.info(f"Uploading {filename}")

        content = await file.read()
        if not content:
            raise ValueError("File is empty")

        doc = loader.load_file(content, filename)
        chunks = chunker.chunk_text(doc.content, doc.metadata.source)

        doc_id = _gen_doc_id(filename)
        documents[doc_id] = {
            "metadata": doc.metadata,
            "chunks": chunks,
            "uploaded_at": datetime.utcnow(),
        }

        logger.info(f"Processed {doc_id}: {len(chunks)} chunks")

        return DocumentUploadResponse(
            success=True,
            document_id=doc_id,
            chunks_created=len(chunks),
            message=f"Document '{filename}' processed successfully",
        )

    except FileSizeExceededError as e:
        logger.warning(f"File too large: {filename}")
        raise HTTPException(status_code=413, detail=e.message)
    
    except UnsupportedFileFormatError as e:
        logger.warning(f"Unsupported format: {filename}")
        raise HTTPException(status_code=400, detail=e.message)
    
    except DocumentParsingError as e:
        logger.error(f"Parse error: {e.message}")
        raise HTTPException(status_code=400, detail=e.message)
    
    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to process document")


@router.get("")
async def list_documents(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
) -> dict:
    try:
        items = list(documents.items())
        total = len(items)
        paginated = items[skip : skip + limit]

        docs = []
        for doc_id, data in paginated:
            meta = data["metadata"]
            docs.append({
                "id": doc_id,
                "source": meta.source,
                "type": meta.document_type,
                "chunks": len(data["chunks"]),
                "size": meta.char_count,
                "uploaded": data["uploaded_at"].isoformat(),
            })

        return {"total": total, "skip": skip, "limit": limit, "items": docs}

    except Exception as e:
        logger.error(f"List error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list documents")


@router.get("/{doc_id}")
async def get_document(doc_id: str) -> dict:
    if doc_id not in documents:
        raise HTTPException(status_code=404, detail="Document not found")

    data = documents[doc_id]
    meta = data["metadata"]
    chunks = data["chunks"]

    sizes = [len(c.text) for c in chunks]
    
    return {
        "id": doc_id,
        "metadata": {
            "source": meta.source,
            "type": meta.document_type,
            "size": meta.char_count,
            "file_size": meta.file_size,
            "created": meta.created_at.isoformat(),
            "encoding": meta.encoding,
            "author": meta.author,
            "title": meta.title,
            "tags": meta.tags,
        },
        "chunks": {
            "total": len(chunks),
            "avg_size": sum(sizes) // len(sizes) if sizes else 0,
            "min_size": min(sizes) if sizes else 0,
            "max_size": max(sizes) if sizes else 0,
        },
        "uploaded": data["uploaded_at"].isoformat(),
    }


@router.delete("/{doc_id}")
async def delete_document(doc_id: str) -> dict:
    if doc_id not in documents:
        raise HTTPException(status_code=404, detail="Document not found")

    data = documents[doc_id]
    source = data["metadata"].source
    chunk_count = len(data["chunks"])

    del documents[doc_id]

    logger.info(f"Deleted {doc_id}: {source}")

    return {
        "success": True,
        "document_id": doc_id,
        "source": source,
        "chunks_deleted": chunk_count,
    }


@router.get("/health", tags=["Health"])
async def service_health() -> dict:
    return {
        "service": "documents",
        "status": "healthy",
        "documents": len(documents),
    }