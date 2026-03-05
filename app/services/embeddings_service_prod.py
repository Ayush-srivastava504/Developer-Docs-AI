import numpy as np
from typing import List
from openai import OpenAI
from dataclasses import dataclass

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class Embedding:
    chunk_id: str
    vector: List[float]
    source: str
    chunk_index: int


class EmbeddingsService:
    def __init__(self):
        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY not configured")
        
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.EMBEDDING_MODEL
        self.logger = get_logger(__name__)

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []

        try:
            response = self.client.embeddings.create(
                input=texts,
                model=self.model,
            )
            return [item.embedding for item in response.data]
        except Exception as e:
            self.logger.error(f"Embedding error: {str(e)}")
            raise

    def embed_chunks(self, chunks: List) -> List[Embedding]:
        if not chunks:
            return []

        texts = [c.text for c in chunks]
        vectors = self.embed_texts(texts)

        embeddings = []
        for chunk, vector in zip(chunks, vectors):
            embeddings.append(Embedding(
                chunk_id=chunk.chunk_id,
                vector=vector,
                source=chunk.source,
                chunk_index=chunk.chunk_index,
            ))

        self.logger.info(f"Embedded {len(embeddings)} chunks")
        return embeddings

    def embed_text(self, text: str) -> List[float]:
        if not text.strip():
            raise ValueError("Text cannot be empty")
        
        return self.embed_texts([text])[0]

    @staticmethod
    def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
        a = np.array(vec1)
        b = np.array(vec2)
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))