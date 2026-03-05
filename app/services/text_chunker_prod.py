import re
from dataclasses import dataclass, field
from typing import List, Optional
from abc import ABC, abstractmethod

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class TextChunk:
    text: str
    chunk_id: str
    source: str
    chunk_index: int
    start_char: int
    end_char: int
    metadata: dict = field(default_factory=dict)

    def char_count(self) -> int:
        return len(self.text)

    def word_count(self) -> int:
        return len(self.text.split())


class ChunkingStrategy(ABC):
    def __init__(self, chunk_size: int, overlap: int):
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if overlap < 0 or overlap >= chunk_size:
            raise ValueError("overlap must be 0 <= overlap < chunk_size")
        
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.logger = get_logger(self.__class__.__name__)

    @abstractmethod
    def chunk(self, text: str, source: str) -> List[TextChunk]:
        pass


class FixedSizeChunker(ChunkingStrategy):
    def chunk(self, text: str, source: str) -> List[TextChunk]:
        if not text or not text.strip():
            return []

        chunks = []
        start = 0
        idx = 0

        while start < len(text):
            end = min(start + self.chunk_size, len(text))
            chunk_text = text[start:end]

            chunks.append(TextChunk(
                text=chunk_text,
                chunk_id=f"{source}_{idx}",
                source=source,
                chunk_index=idx,
                start_char=start,
                end_char=end,
            ))

            start = end - self.overlap
            if start >= end:
                break
            idx += 1

        self.logger.debug(f"Created {len(chunks)} fixed chunks from {source}")
        return chunks


class RecursiveChunker(ChunkingStrategy):
    SEPARATORS = [
        "\n\n",
        "\n",
        r"(?<=[.!?])\s+",
        " ",
        "",
    ]

    def chunk(self, text: str, source: str) -> List[TextChunk]:
        if not text or not text.strip():
            return []
        
        chunks = self._recursive_split(text, source)
        self.logger.debug(f"Created {len(chunks)} recursive chunks from {source}")
        return chunks

    def _recursive_split(
        self,
        text: str,
        source: str,
        sep_idx: int = 0,
        chunk_idx: int = 0,
        start_pos: int = 0,
    ) -> List[TextChunk]:
        chunks = []
        good_splits = []

        sep = self.SEPARATORS[sep_idx]
        
        if sep and sep.startswith("\\"):
            splits = re.split(sep, text)
        else:
            splits = text.split(sep)

        merged = []
        for i, s in enumerate(splits):
            if i == len(splits) - 1:
                merged.append(s)
            else:
                merged.append(s + (sep if sep else ""))

        for split in merged:
            if len(split.strip()) < self.chunk_size:
                good_splits.append(split)
            else:
                if good_splits:
                    merged_text = "".join(good_splits)
                    chunks.append(TextChunk(
                        text=merged_text.strip(),
                        chunk_id=f"{source}_{chunk_idx}",
                        source=source,
                        chunk_index=chunk_idx,
                        start_char=start_pos,
                        end_char=start_pos + len(merged_text),
                    ))
                    start_pos += len(merged_text)
                    chunk_idx += 1
                    good_splits = []

                if sep_idx < len(self.SEPARATORS) - 1:
                    sub = self._recursive_split(
                        split, source, sep_idx + 1, chunk_idx, start_pos
                    )
                    chunks.extend(sub)
                    chunk_idx += len(sub)
                    start_pos += len(split)
                else:
                    chunks.append(TextChunk(
                        text=split[:self.chunk_size],
                        chunk_id=f"{source}_{chunk_idx}",
                        source=source,
                        chunk_index=chunk_idx,
                        start_char=start_pos,
                        end_char=start_pos + self.chunk_size,
                    ))
                    chunk_idx += 1
                    start_pos += self.chunk_size

        if good_splits:
            merged_text = "".join(good_splits)
            if merged_text.strip():
                chunks.append(TextChunk(
                    text=merged_text.strip(),
                    chunk_id=f"{source}_{chunk_idx}",
                    source=source,
                    chunk_index=chunk_idx,
                    start_char=start_pos,
                    end_char=start_pos + len(merged_text),
                ))

        return chunks


class TextChunkerService:
    def __init__(
        self,
        chunk_size: int = settings.CHUNK_SIZE,
        overlap: int = settings.CHUNK_OVERLAP,
        strategy: str = "recursive",
    ):
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.logger = get_logger(__name__)

        if strategy.lower() == "fixed":
            self.strategy = FixedSizeChunker(chunk_size, overlap)
        elif strategy.lower() == "recursive":
            self.strategy = RecursiveChunker(chunk_size, overlap)
        else:
            raise ValueError(f"Unknown strategy: {strategy}")

    def chunk_text(
        self, text: str, source: str, apply_overlap: bool = True
    ) -> List[TextChunk]:
        if not source or not source.strip():
            raise ValueError("Source cannot be empty")

        if not text or not text.strip():
            self.logger.warning(f"Empty text for {source}")
            return []

        text = self._clean_text(text)
        chunks = self.strategy.chunk(text, source)

        if apply_overlap and chunks:
            chunks = self._apply_overlap(chunks, text)

        self.logger.info(
            f"Chunked {source}: {len(text)} chars → {len(chunks)} chunks"
        )

        return chunks

    @staticmethod
    def _clean_text(text: str) -> str:
        text = " ".join(text.split())
        text = "".join(c for c in text if ord(c) >= 32 or c in "\n\t")
        return text.strip()

    def _apply_overlap(
        self, chunks: List[TextChunk], original: str
    ) -> List[TextChunk]:
        if len(chunks) <= 1 or self.overlap == 0:
            return chunks

        for i in range(1, len(chunks)):
            curr = chunks[i]
            overlap_start = max(0, curr.start_char - self.overlap)
            overlap_text = original[overlap_start:curr.start_char]

            if overlap_text and overlap_text != curr.text[:len(overlap_text)]:
                curr.text = overlap_text + curr.text
                curr.start_char = overlap_start

        return chunks

    def stats(self, chunks: List[TextChunk]) -> dict:
        if not chunks:
            return {
                "total": 0,
                "avg": 0,
                "min": 0,
                "max": 0,
                "total_chars": 0,
            }

        sizes = [len(c.text) for c in chunks]
        return {
            "total": len(chunks),
            "avg": sum(sizes) / len(sizes),
            "min": min(sizes),
            "max": max(sizes),
            "total_chars": sum(sizes),
        }