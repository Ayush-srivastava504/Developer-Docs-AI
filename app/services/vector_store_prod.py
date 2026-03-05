from typing import List, Dict, Optional
import chromadb
import os

from app.core.config import settings
from app.services.text_chunker_prod import TextChunk
from app.services.embeddings_service_prod import Embedding
from app.core.logger import get_logger

logger = get_logger(__name__)


class VectorStore:
    def __init__(self):
        # Create directory if it doesn't exist
        os.makedirs(settings.CHROMA_DB_PATH, exist_ok=True)
        
        # Use the new PersistentClient API
        self.client = chromadb.PersistentClient(path=settings.CHROMA_DB_PATH)
        self.collection = self.client.get_or_create_collection(
            name=settings.CHROMA_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        self.logger = get_logger(__name__)

    def add_chunks(
        self,
        doc_id: str,
        chunks: List[TextChunk],
        embeddings: List[Embedding],
    ) -> None:
        if not chunks or not embeddings:
            return

        chunk_ids = [e.chunk_id for e in embeddings]
        vectors = [e.embedding for e in embeddings]
        texts = [c.text for c in chunks]
        
        metadatas = []
        for chunk, emb in zip(chunks, embeddings):
            metadatas.append({
                "source": chunk.source,
                "doc_id": doc_id,
                "chunk_index": str(chunk.chunk_index),
                "start_char": str(chunk.start_char),
                "end_char": str(chunk.end_char),
            })

        self.collection.upsert(
            ids=chunk_ids,
            embeddings=vectors,
            documents=texts,
            metadatas=metadatas,
        )

        self.logger.info(f"Added {len(chunks)} chunks for {doc_id}")

    def search(
        self,
        query_embedding: List[float],
        k: int = 5,
        threshold: float = settings.SIMILARITY_THRESHOLD,
    ) -> List[Dict]:
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=k,
        )

        if not results["documents"] or not results["documents"][0]:
            return []

        matches = []
        for doc, dist, meta in zip(
            results["documents"][0],
            results["distances"][0],
            results["metadatas"][0],
        ):
            similarity = 1 - dist
            
            if similarity >= threshold:
                matches.append({
                    "chunk_id": meta.get("chunk_id"),
                    "source": meta.get("source"),
                    "content": doc,
                    "score": similarity,
                    "metadata": meta,
                })

        return sorted(matches, key=lambda x: x["score"], reverse=True)

    def delete_doc(self, doc_id: str) -> int:
        where = {"doc_id": {"$eq": doc_id}}
        
        results = self.collection.get(where=where)
        count = len(results["ids"])
        
        if count > 0:
            self.collection.delete(ids=results["ids"])
            self.logger.info(f"Deleted {count} chunks for {doc_id}")

        return count

    def get_stats(self) -> Dict:
        return {
            "total_vectors": self.collection.count(),
            "collection": settings.CHROMA_COLLECTION_NAME,
            "path": settings.CHROMA_DB_PATH,
        }