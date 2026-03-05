import os
import io
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime
import pypdf

from app.core.config import settings
from app.core.exceptions import (
    DocumentParsingError,
    UnsupportedFileFormatError,
    FileSizeExceededError,
)
from app.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class DocumentMetadata:
    source: str
    document_type: str
    created_at: datetime
    file_size: int
    char_count: int
    encoding: str = "utf-8"
    author: Optional[str] = None
    title: Optional[str] = None
    tags: List[str] = field(default_factory=list)


@dataclass
class LoadedDocument:
    content: str
    metadata: DocumentMetadata
    pages: Optional[int] = None
    sections: List[str] = field(default_factory=list)


class DocumentLoader(ABC):
    def __init__(self):
        self.logger = get_logger(self.__class__.__name__)

    @abstractmethod
    def load(self, content: bytes, filename: str) -> LoadedDocument:
        pass

    def _validate_size(self, content: bytes, filename: str) -> None:
        if len(content) > settings.MAX_UPLOAD_SIZE:
            raise FileSizeExceededError(filename, settings.MAX_UPLOAD_SIZE)

    def _create_metadata(
        self, filename: str, doc_type: str, content: bytes, text: str, **kwargs
    ) -> DocumentMetadata:
        return DocumentMetadata(
            source=filename,
            document_type=doc_type,
            created_at=datetime.utcnow(),
            file_size=len(content),
            char_count=len(text),
            **kwargs
        )


class MarkdownLoader(DocumentLoader):
    def load(self, content: bytes, filename: str) -> LoadedDocument:
        self._validate_size(content, filename)
        
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError as e:
            raise DocumentParsingError(filename, "markdown") from e

        sections = [line.lstrip("#").strip() for line in text.split("\n") 
                   if line.startswith("#")]
        
        metadata = self._create_metadata(filename, "markdown", content, text)
        
        self.logger.info(f"Loaded {filename}: {len(text)} chars, {len(sections)} sections")
        
        return LoadedDocument(content=text, metadata=metadata, sections=sections)


class TextLoader(DocumentLoader):
    ENCODINGS = ["utf-8", "latin-1", "cp1252", "iso-8859-1"]

    def load(self, content: bytes, filename: str) -> LoadedDocument:
        self._validate_size(content, filename)

        text = None
        encoding = None
        
        for enc in self.ENCODINGS:
            try:
                text = content.decode(enc)
                encoding = enc
                break
            except UnicodeDecodeError:
                continue

        if text is None:
            raise DocumentParsingError(filename, "text")

        metadata = self._create_metadata(
            filename, "text", content, text, encoding=encoding
        )
        
        self.logger.info(f"Loaded {filename}: {len(text)} chars")
        
        return LoadedDocument(content=text, metadata=metadata)


class PDFLoader(DocumentLoader):
    def load(self, content: bytes, filename: str) -> LoadedDocument:
        self._validate_size(content, filename)

        try:
            reader = pypdf.PdfReader(io.BytesIO(content))
            text = self._extract_text(reader)
            pdf_meta = self._extract_metadata(reader)
            pages = len(reader.pages)
        except Exception as e:
            raise DocumentParsingError(filename, "pdf") from e

        metadata = self._create_metadata(
            filename, "pdf", content, text,
            author=pdf_meta.get("author"),
            title=pdf_meta.get("title")
        )
        
        self.logger.info(f"Loaded {filename}: {pages} pages, {len(text)} chars")
        
        return LoadedDocument(content=text, metadata=metadata, pages=pages)

    @staticmethod
    def _extract_text(reader: pypdf.PdfReader) -> str:
        parts = []
        for i, page in enumerate(reader.pages):
            try:
                text = page.extract_text()
                if text:
                    parts.append(f"--- Page {i + 1} ---\n{text}\n")
            except Exception as e:
                logger.warning(f"Failed to extract page {i + 1}: {e}")
        return "".join(parts)

    @staticmethod
    def _extract_metadata(reader: pypdf.PdfReader) -> dict:
        meta = {}
        try:
            if reader.metadata:
                meta["title"] = reader.metadata.get("/Title")
                meta["author"] = reader.metadata.get("/Author")
        except Exception:
            pass
        return meta


class RSTLoader(DocumentLoader):
    def load(self, content: bytes, filename: str) -> LoadedDocument:
        self._validate_size(content, filename)
        
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError as e:
            raise DocumentParsingError(filename, "rst") from e

        sections = self._extract_sections(text)
        metadata = self._create_metadata(filename, "rst", content, text)
        
        self.logger.info(f"Loaded {filename}: {len(text)} chars, {len(sections)} sections")
        
        return LoadedDocument(content=text, metadata=metadata, sections=sections)

    @staticmethod
    def _extract_sections(text: str) -> List[str]:
        sections = []
        lines = text.split("\n")
        
        for i in range(len(lines) - 1):
            curr = lines[i].strip()
            next_line = lines[i + 1].strip()
            
            if (curr and next_line and len(next_line) > 0 and
                all(c == next_line[0] for c in next_line) and
                next_line[0] in "=-~`#*+^"):
                sections.append(curr)
        
        return sections


class DocumentLoaderFactory:
    LOADERS = {
        ".md": MarkdownLoader,
        ".markdown": MarkdownLoader,
        ".txt": TextLoader,
        ".text": TextLoader,
        ".pdf": PDFLoader,
        ".rst": RSTLoader,
    }

    @classmethod
    def get_loader(cls, filename: str) -> DocumentLoader:
        _, ext = os.path.splitext(filename)
        ext = ext.lower()
        
        loader_class = cls.LOADERS.get(ext)
        if not loader_class:
            supported = ", ".join(sorted(cls.LOADERS.keys()))
            raise UnsupportedFileFormatError(filename, ext, supported)
        
        return loader_class()

    @classmethod
    def supported_formats(cls) -> List[str]:
        return sorted(cls.LOADERS.keys())


class DocumentLoaderService:
    def __init__(self):
        self.logger = get_logger(__name__)
        self.factory = DocumentLoaderFactory()

    def load_file(self, content: bytes, filename: str) -> LoadedDocument:
        if not filename or not filename.strip():
            raise ValueError("Filename cannot be empty")
        
        if not content:
            raise ValueError("File content cannot be empty")

        self.logger.info(f"Loading {filename} ({len(content)} bytes)")
        
        loader = self.factory.get_loader(filename)
        document = loader.load(content, filename)
        
        self.logger.info(f"Successfully loaded {filename}")
        
        return document

    def is_supported(self, filename: str) -> bool:
        _, ext = os.path.splitext(filename)
        return ext.lower() in self.factory.LOADERS