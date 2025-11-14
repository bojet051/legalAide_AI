"""
FastAPI routes for ingestion, search, and RAG answering.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from legal_aide.db import queries, search

router = APIRouter()


def get_app_state(request: Request):
    return request.app.state


class IngestCaseRequest(BaseModel):
    file_path: str = Field(..., description="Path to the PDF file to ingest.")


class ReindexFolderRequest(BaseModel):
    folder_path: str
    drop_existing: bool = False


class IngestScrapedDataRequest(BaseModel):
    metadata_csv_path: str = Field(..., description="Path to metadata.csv from scraper.")
    drop_existing: bool = False


class SearchRequest(BaseModel):
    query: str
    court: Optional[str] = "PH Supreme Court"
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    case_number: Optional[str] = None
    top_k: int = Field(20, ge=1, le=50)


class AskRequest(BaseModel):
    question: str = Field(..., description="Legal question to answer.")
    court: Optional[str] = "PH Supreme Court"
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    case_number: Optional[str] = None
    top_k: int = Field(10, ge=1, le=20)


@router.post("/ingest_case")
async def ingest_case(payload: IngestCaseRequest, state=Depends(get_app_state)):
    pipeline = state.pipeline
    case_id, chunk_count = await run_in_threadpool(pipeline.ingest_file, payload.file_path)
    return {"case_id": case_id, "chunks": chunk_count}


@router.post("/reindex_folder")
async def reindex_folder(payload: ReindexFolderRequest, state=Depends(get_app_state)):
    pipeline = state.pipeline
    summary = await run_in_threadpool(pipeline.reindex_folder, payload.folder_path, payload.drop_existing)
    return summary


@router.post("/ingest_scraped")
async def ingest_scraped_data(payload: IngestScrapedDataRequest, state=Depends(get_app_state)):
    """Ingest decisions from scraper metadata.csv with pre-extracted text files."""
    import csv
    from pathlib import Path
    
    metadata_path = Path(payload.metadata_csv_path)
    if not metadata_path.exists():
        raise HTTPException(status_code=404, detail=f"Metadata file not found: {payload.metadata_csv_path}")
    
    pipeline = state.pipeline
    
    if payload.drop_existing:
        with state.db_pool.connection() as conn:
            queries.delete_all_cases(conn)
    
    total_cases = 0
    total_chunks = 0
    failed = []
    
    with metadata_path.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            text_path = row.get("text_path", "")
            if not text_path or not Path(text_path).exists():
                failed.append(f"Missing text file: {text_path}")
                continue
            
            try:
                case_id, chunk_count = await run_in_threadpool(pipeline.ingest_file, text_path)
                total_cases += 1
                total_chunks += chunk_count
            except Exception as exc:
                failed.append(f"{text_path}: {exc}")
                continue
    
    return {
        "cases": total_cases,
        "chunks": total_chunks,
        "failed": failed,
    }


@router.post("/search")
async def search_chunks(payload: SearchRequest, state=Depends(get_app_state)):
    filters = search.SearchFilters(
        court=payload.court,
        date_from=payload.date_from,
        date_to=payload.date_to,
        case_number=payload.case_number,
    )
    rag_engine = state.rag_engine
    results = await run_in_threadpool(
        rag_engine.search_chunks,
        payload.query,
        filters=filters,
        top_k=payload.top_k,
    )
    return {"results": results}


@router.post("/ask")
async def ask_question(payload: AskRequest, state=Depends(get_app_state)):
    filters = search.SearchFilters(
        court=payload.court,
        date_from=payload.date_from,
        date_to=payload.date_to,
        case_number=payload.case_number,
    )
    rag_engine = state.rag_engine
    answer = await run_in_threadpool(
        rag_engine.answer_question,
        payload.question,
        filters=filters,
        top_k=payload.top_k,
    )
    return {
        "answer": answer.answer,
        "supporting_chunks": answer.supporting_chunks,
        "case_ids": answer.case_ids,
    }


@router.get("/case/{case_id}")
async def get_case(case_id: int, state=Depends(get_app_state)):
    with state.db_pool.connection() as conn:
        case = queries.fetch_case(conn, case_id)
        if not case:
            raise HTTPException(status_code=404, detail="Case not found.")
        chunks = queries.fetch_case_chunks(conn, case_id)
    case["chunks"] = chunks
    return case
