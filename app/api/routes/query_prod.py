from fastapi import APIRouter, HTTPException, Query
import time

from app.schemas.schemas import QueryRequest, QueryResponse
from app.services.query_service_prod import QueryService
from app.core.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Query"])
query_service = QueryService()


@router.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest) -> QueryResponse:
    start = time.time()
    
    try:
        logger.info(f"Query: {req.query[:50]}...")
        
        result = query_service.query(
            req.query,
            k=req.top_k,
            temperature=req.temperature,
        )

        elapsed = (time.time() - start) * 1000
        
        # Map result to response model
        response = QueryResponse(
            success=True,
            answer=result["answer"],
            retrieved_docs=[],
            confidence_score=result["relevance"][0] if result["relevance"] else 0,
            processing_time_ms=elapsed,
            model_used=query_service.generator.model,
        )
        
        logger.info(f"Query completed in {elapsed:.0f}ms")
        return response

    except Exception as e:
        logger.error(f"Query failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Query processing failed")


@router.get("/search")
async def search(
    q: str = Query(..., min_length=1, max_length=500),
    limit: int = Query(5, ge=1, le=20),
) -> dict:
    try:
        from app.services.query_service_prod import RetrieverService
        
        retriever = RetrieverService()
        results = retriever.retrieve(q, k=limit)
        
        return {
            "query": q,
            "results": [
                {
                    "id": r["chunk_id"],
                    "source": r["source"],
                    "content": r["content"][:200],
                    "score": r["score"],
                }
                for r in results
            ],
            "count": len(results),
        }
    
    except Exception as e:
        logger.error(f"Search error: {str(e)}")
        raise HTTPException(status_code=500, detail="Search failed")