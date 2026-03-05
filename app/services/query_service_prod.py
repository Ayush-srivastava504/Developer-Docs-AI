from typing import List, Dict
from openai import OpenAI

from app.core.config import settings
from app.services.embeddings_service_prod import EmbeddingsService
from app.services.vector_store_prod import VectorStore
from app.core.logger import get_logger

logger = get_logger(__name__)


class RetrieverService:
    def __init__(self):
        self.embeddings = EmbeddingsService()
        self.vector_store = VectorStore()
        self.logger = get_logger(__name__)

    def retrieve(self, query: str, k: int = 5) -> List[Dict]:
        try:
            query_embedding = self.embeddings.embed_text(query)
            results = self.vector_store.search(query_embedding, k=k)
            
            self.logger.info(f"Retrieved {len(results)} results for query")
            return results

        except Exception as e:
            self.logger.error(f"Retrieval error: {str(e)}")
            raise


class ResponseGeneratorService:
    def __init__(self):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.LLM_MODEL
        self.logger = get_logger(__name__)

    def generate(
        self,
        query: str,
        context: List[Dict],
        temperature: float = settings.LLM_TEMPERATURE,
    ) -> str:
        if not context:
            return "No relevant documents found."

        context_text = "\n\n".join(
            [f"Source: {c['source']}\n{c['content']}" for c in context]
        )

        system_prompt = (
            "You are a helpful assistant that answers questions based on "
            "the provided documentation. Be concise and accurate."
        )

        user_message = (
            f"Based on this documentation:\n\n{context_text}\n\n"
            f"Answer this question: {query}"
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=temperature,
                max_tokens=settings.LLM_MAX_TOKENS,
            )

            answer = response.choices[0].message.content
            self.logger.info("Generated response")
            return answer

        except Exception as e:
            self.logger.error(f"Generation error: {str(e)}")
            raise


class QueryService:
    def __init__(self):
        self.retriever = RetrieverService()
        self.generator = ResponseGeneratorService()
        self.logger = get_logger(__name__)

    def query(
        self,
        text: str,
        k: int = 5,
        temperature: float = settings.LLM_TEMPERATURE,
    ) -> Dict:
        try:
            context = self.retriever.retrieve(text, k=k)
            answer = self.generator.generate(text, context, temperature)

            return {
                "query": text,
                "answer": answer,
                "sources": [c["source"] for c in context],
                "relevance": [c["score"] for c in context],
                "context_count": len(context),
            }

        except Exception as e:
            self.logger.error(f"Query error: {str(e)}")
            raise