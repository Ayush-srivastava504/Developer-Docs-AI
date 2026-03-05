from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from app.core.config import settings
from app.schemas.schemas import HealthCheckResponse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Developer Docs AI - Steps 1-3")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Embeddings: {settings.EMBEDDING_MODEL}")
    logger.info(f"LLM: {settings.LLM_MODEL}")
    logger.info(f"Vector DB: {settings.CHROMA_DB_PATH}")
    yield
    logger.info("Shutting down")


app = FastAPI(
    title="Developer Docs AI",
    description="RAG system with embeddings and vector search",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    logger.error(f"HTTP error: {exc.detail}")
    return {"error": exc.detail, "status": exc.status_code}


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logger.error(f"Error: {str(exc)}", exc_info=True)
    return {"error": "Internal server error", "status": 500}


@app.get("/health", response_model=HealthCheckResponse)
async def health():
    return HealthCheckResponse(
        status="healthy",
        message="Developer Docs AI is running with embeddings",
        environment=settings.ENVIRONMENT,
    )


@app.get("/health/detailed")
async def detailed_health():
    return {
        "api": "healthy",
        "document_loader": "operational",
        "text_chunker": "operational",
        "embeddings_service": "operational",
        "vector_store": "operational",
        "retriever": "ready",
        "llm": "ready",
    }


@app.get("/")
async def root():
    return {
        "name": "Developer Docs AI",
        "version": "1.0.0",
        "description": "RAG system with semantic search",
        "docs": "/docs",
        "endpoints": {
            "upload": "/api/v1/documents/upload",
            "list": "/api/v1/documents",
            "search": "/api/v1/search",
            "query": "/api/v1/query",
        },
    }


from app.api.routes.documents_prod import router as documents_router
from app.api.routes.query_prod import router as query_router

app.include_router(documents_router)
app.include_router(query_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.PORT,
        reload=settings.DEBUG,
    )