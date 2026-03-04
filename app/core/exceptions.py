class AppException(Exception):
    def __init__(self, message: str, code: str = "ERROR", status_code: int = 500):
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(self.message)


class DocumentException(AppException):
    pass


class DocumentNotFoundError(DocumentException):
    def __init__(self, doc_id: str):
        super().__init__(
            f"Document '{doc_id}' not found",
            "DOCUMENT_NOT_FOUND",
            404
        )


class DocumentUploadError(DocumentException):
    def __init__(self, filename: str, reason: str):
        super().__init__(
            f"Failed to upload '{filename}': {reason}",
            "DOCUMENT_UPLOAD_ERROR",
            400
        )


class DocumentParsingError(DocumentException):
    def __init__(self, filename: str, format: str):
        super().__init__(
            f"Cannot parse {format} file: {filename}",
            "DOCUMENT_PARSING_ERROR",
            400
        )


class UnsupportedFileFormatError(DocumentException):
    def __init__(self, filename: str, format: str, supported: str = ""):
        msg = f"Format '{format}' not supported"
        if supported:
            msg += f". Supported: {supported}"
        super().__init__(msg, "UNSUPPORTED_FILE_FORMAT", 400)


class FileSizeExceededError(DocumentException):
    def __init__(self, filename: str, max_size: int):
        super().__init__(
            f"File '{filename}' exceeds {max_size} bytes",
            "FILE_SIZE_EXCEEDED",
            413
        )


class EmbeddingException(AppException):
    pass


class EmbeddingGenerationError(EmbeddingException):
    def __init__(self, reason: str):
        super().__init__(
            f"Failed to generate embedding: {reason}",
            "EMBEDDING_GENERATION_ERROR",
            500
        )


class OpenAIAPIError(EmbeddingException):
    def __init__(self, error_msg: str):
        super().__init__(
            f"OpenAI API error: {error_msg}",
            "OPENAI_API_ERROR",
            503
        )


class VectorStoreException(AppException):
    pass


class VectorStoreConnectionError(VectorStoreException):
    def __init__(self):
        super().__init__(
            "Cannot connect to vector database",
            "VECTOR_STORE_CONNECTION_ERROR",
            503
        )


class CollectionNotFoundError(VectorStoreException):
    def __init__(self, name: str):
        super().__init__(
            f"Collection '{name}' not found",
            "COLLECTION_NOT_FOUND",
            404
        )


class QueryException(AppException):
    pass


class InvalidQueryError(QueryException):
    def __init__(self, reason: str):
        super().__init__(f"Invalid query: {reason}", "INVALID_QUERY", 400)


class NoRelevantDocumentsError(QueryException):
    def __init__(self):
        super().__init__(
            "No relevant documents found",
            "NO_RELEVANT_DOCUMENTS",
            404
        )


class ResponseGenerationError(QueryException):
    def __init__(self, reason: str):
        super().__init__(
            f"Failed to generate response: {reason}",
            "RESPONSE_GENERATION_ERROR",
            500
        )


class ConfigurationException(AppException):
    pass


class MissingConfigurationError(ConfigurationException):
    def __init__(self, key: str):
        super().__init__(
            f"Required configuration '{key}' is not set",
            "MISSING_CONFIGURATION",
            500
        )


class ValidationException(AppException):
    pass


class InvalidInput(ValidationException):
    def __init__(self, field: str, reason: str):
        super().__init__(
            f"Invalid input for '{field}': {reason}",
            "INVALID_INPUT",
            422
        )