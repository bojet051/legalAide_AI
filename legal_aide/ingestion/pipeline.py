"""
End-to-end ingestion pipeline from PDF to pgvector.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, asdict
from datetime import date
from pathlib import Path
from typing import Iterable, List

from PyPDF2 import PdfReader
from psycopg_pool import ConnectionPool

from legal_aide.config import Settings
from legal_aide.db import queries
from legal_aide.embeddings import EmbeddingClient
from legal_aide.ingestion import parsing

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class CaseMetadata:
    case_number: str | None
    title: str | None
    court: str | None
    promulgation_date: date | None


@dataclass(slots=True)
class Chunk:
    section_type: str | None
    chunk_index: int
    chunk_text: str
    token_count: int
    embedding: list[float] | None = None


class IngestionPipeline:
    def __init__(
        self,
        settings: Settings,
        embedding_client: EmbeddingClient,
        db_pool: ConnectionPool,
    ) -> None:
        self.settings = settings
        self.embedding_client = embedding_client
        self.db_pool = db_pool

    def ingest_file(self, file_path: str) -> tuple[int, int]:
        """Process a single PDF or TXT file into the database."""
        path = Path(file_path)
        if path.suffix.lower() == ".txt":
            metadata, full_text = self.extract_text_and_metadata_from_txt(file_path)
        elif path.suffix.lower() == ".pdf":
            metadata, full_text = self.extract_text_and_metadata_from_pdf(file_path)
        else:
            raise ValueError(f"Unsupported file type: {path.suffix}. Expected .pdf or .txt")
        
        chunks = self.chunk_case_text(full_text)
        chunks = self.embed_chunks(chunks)
        case_id = self.save_case_and_chunks_to_db(metadata, full_text, file_path, chunks)
        logger.info("Ingested %s with %d chunks (case_id=%s)", file_path, len(chunks), case_id)
        return case_id, len(chunks)

    def reindex_folder(self, folder_path: str, drop_existing: bool = False) -> dict:
        """Re-ingest all PDF and TXT files inside a folder."""
        folder = Path(folder_path)
        if not folder.exists():
            raise FileNotFoundError(f"{folder_path} does not exist")

        files = sorted(
            path for path in folder.rglob("*") 
            if path.suffix.lower() in (".pdf", ".txt")
        )
        if not files:
            return {"cases": 0, "chunks": 0}

        with self.db_pool.connection() as conn:
            if drop_existing:
                logger.warning("Dropping existing cases before reindexing.")
                queries.delete_all_cases(conn)

        total_cases = 0
        total_chunks = 0
        for path in files:
            try:
                case_id, chunk_count = self.ingest_file(str(path))
                total_cases += 1
                total_chunks += chunk_count
                logger.debug("Reindexed %s -> case_id=%s", path, case_id)
            except Exception as exc:
                logger.error("Failed to ingest %s: %s", path, exc)
                continue
        return {"cases": total_cases, "chunks": total_chunks}

    # --- Pipeline stages -------------------------------------------------

    def extract_text_and_metadata_from_pdf(self, path: str) -> tuple[CaseMetadata, str]:
        """Extract clean text plus metadata from a PDF, running OCR if needed."""
        reader = PdfReader(path)
        raw_pages = []
        for page in reader.pages:
            text = page.extract_text() or ""
            raw_pages.append(text)
        combined = "\n\n".join(raw_pages).strip()

        cleaned = parsing.clean_text(combined)
        metadata_dict = parsing.extract_case_metadata(cleaned)
        metadata = CaseMetadata(**metadata_dict)
        return metadata, cleaned

    def extract_text_and_metadata_from_txt(self, path: str) -> tuple[CaseMetadata, str]:
        """Extract text and metadata from a plain text file (e.g., scraped decisions)."""
        path_obj = Path(path)
        raw_text = path_obj.read_text(encoding="utf-8")
        
        cleaned = parsing.clean_text(raw_text)
        metadata_dict = parsing.extract_case_metadata(cleaned)
        metadata = CaseMetadata(**metadata_dict)
        return metadata, cleaned

    def chunk_case_text(self, full_text: str) -> list[Chunk]:
        """Split case text into structured chunks."""
        segments = parsing.segment_by_headings(full_text)
        chunks: list[Chunk] = []
        chunk_index = 0

        for section_type, section_text in segments:
            if not section_text:
                continue
            section_tokens = parsing.token_count(section_text)
            if section_tokens > self.settings.chunk_token_size * 1.5:
                window_chunks = parsing.sliding_window_chunks(
                    section_text,
                    chunk_size_tokens=self.settings.chunk_token_size,
                    overlap_ratio=self.settings.chunk_overlap_ratio,
                )
                for window_text in window_chunks:
                    chunks.append(
                        Chunk(
                            section_type=section_type,
                            chunk_index=chunk_index,
                            chunk_text=window_text,
                            token_count=parsing.token_count(window_text),
                        )
                    )
                    chunk_index += 1
            else:
                chunks.append(
                    Chunk(
                        section_type=section_type,
                        chunk_index=chunk_index,
                        chunk_text=section_text,
                        token_count=section_tokens,
                    )
                )
                chunk_index += 1

        if not chunks:
            fallback_chunks = parsing.sliding_window_chunks(
                full_text,
                chunk_size_tokens=self.settings.chunk_token_size,
                overlap_ratio=self.settings.chunk_overlap_ratio,
            )
            for window_text in fallback_chunks:
                chunks.append(
                    Chunk(
                        section_type=None,
                        chunk_index=chunk_index,
                        chunk_text=window_text,
                        token_count=parsing.token_count(window_text),
                    )
                )
                chunk_index += 1

        return chunks

    def embed_chunks(self, chunks: Iterable[Chunk]) -> list[Chunk]:
        """Generate embeddings for each chunk."""
        embedded: list[Chunk] = []
        for chunk in chunks:
            embedding = self.embedding_client.embed_document(chunk.chunk_text)
            chunk.embedding = embedding
            embedded.append(chunk)
        return embedded

    def save_case_and_chunks_to_db(
        self,
        metadata: CaseMetadata,
        full_text: str,
        source_file: str,
        chunks: list[Chunk],
    ) -> int:
        """Persist case and chunk rows."""
        chunk_inserts = [
            queries.ChunkInsert(
                section_type=chunk.section_type,
                chunk_index=chunk.chunk_index,
                chunk_text=chunk.chunk_text,
                token_count=chunk.token_count,
                embedding=chunk.embedding or [],
            )
            for chunk in chunks
        ]
        with self.db_pool.connection() as conn:
            case_id = queries.save_case_with_chunks(
                conn,
                metadata=asdict(metadata),
                full_text=full_text,
                source_file=source_file,
                chunks=chunk_inserts,
            )
        return case_id
