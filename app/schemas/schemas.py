from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime
from enum import Enum


class DocumentTypeEnum(str, Enum):
    MARKDOWN = "markdown"
    TEXT = "text"
    PDF = "pdf"
    RESTRUCTURED_TEXT = "rst"


class HealthCheckResponse(BaseModel):
    status: str = Field(..., description="Health status")
    message: str = Field(..., description="Status message")
    environment: str = Field(..., description="Environment name")
    timestamp: Optional[datetime] = Field(default_factory=datetime.utcnow)


class DocumentMetadata(BaseModel):
    source: str = Field(..., description="Source filename")
    document_type: DocumentTypeEnum = Field(..., description="Document type")
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    tags: List[str] = Field(default_factory=list)


class DocumentUploadRequest(BaseModel):
    filename: str = Field(..., description="Filename")
    content: str = Field(..., description="File content")
    document_type: DocumentTypeEnum = Field(..., description="Document type")
    metadata: Optional[DocumentMetadata] = None

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, v):
        if not v or len(v) == 0:
            raise ValueError("Filename cannot be empty")
        return v


class DocumentUploadResponse(BaseModel):
    success: bool = Field(..., description="Success status")
    document_id: str = Field(..., description="Document ID")
    chunks_created: int = Field(..., description="Number of chunks created")
    message: str = Field(..., description="Response message")


class RetrievedDocument(BaseModel):
    chunk_id: str = Field(..., description="Chunk ID")
    content: str = Field(..., description="Chunk content")
    source: str = Field(..., description="Source document")
    similarity_score: float = Field(
        ..., ge=0.0, le=1.0, description="Similarity score"
    )
    metadata: Optional[dict] = None


class QueryRequest(BaseModel):
    query: str = Field(
        ..., min_length=1, max_length=1000, description="Query text"
    )
    top_k: int = Field(default=5, ge=1, le=20, description="Results to retrieve")
    include_context: bool = Field(default=True, description="Include context")
    temperature: Optional[float] = Field(default=0.7, ge=0.0, le=2.0)

    @field_validator("query")
    @classmethod
    def validate_query(cls, v):
        if not v.strip():
            raise ValueError("Query cannot be empty")
        return v.strip()


class QueryResponse(BaseModel):
    success: bool = Field(..., description="Success status")
    answer: str = Field(..., description="Generated answer")
    retrieved_docs: List[RetrievedDocument] = Field(default_factory=list)
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    processing_time_ms: float = Field(..., description="Processing time")
    model_used: str = Field(..., description="Model used")


class ErrorResponse(BaseModel):
    error: str = Field(..., description="Error message")
    status_code: int = Field(..., description="HTTP status code")
    details: Optional[dict] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)