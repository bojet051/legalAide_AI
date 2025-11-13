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
from legal_aide.ingestion import ocr, parsing

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
        """Process a single PDF file into the database."""
        metadata, full_text = self.extract_text_and_metadata_from_pdf(file_path)
        chunks = self.chunk_case_text(full_text)
        chunks = self.embed_chunks(chunks)
        case_id = self.save_case_and_chunks_to_db(metadata, full_text, file_path, chunks)
        logger.info("Ingested %s with %d chunks (case_id=%s)", file_path, len(chunks), case_id)
        return case_id, len(chunks)

    def reindex_folder(self, folder_path: str, drop_existing: bool = False) -> dict:
        """Re-ingest all PDF files inside a folder."""
        folder = Path(folder_path)
        if not folder.exists():
            raise FileNotFoundError(f"{folder_path} does not exist")

        pdf_files = sorted(path for path in folder.rglob("*") if path.suffix.lower() == ".pdf")
        if not pdf_files:
            return {"cases": 0, "chunks": 0}

        with self.db_pool.connection() as conn:
            if drop_existing:
                logger.warning("Dropping existing cases before reindexing.")
                queries.delete_all_cases(conn)

        total_cases = 0
        total_chunks = 0
        for path in pdf_files:
            case_id, chunk_count = self.ingest_file(str(path))
            total_cases += 1
            total_chunks += chunk_count
            logger.debug("Reindexed %s -> case_id=%s", path, case_id)
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

        if len(combined) < 200:
            logger.info("Detected scanned PDF for %s. Running OCR.", path)
            combined = ocr.ocr_pdf(path, self.settings.ocr_tesseract_cmd)

        cleaned = parsing.clean_text(combined)
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
