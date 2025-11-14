"""
FastAPI routes for ingestion, search, RAG answering, and eLibrary sync.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from legal_aide.db import queries, search

router = APIRouter()
sync_router = APIRouter(prefix="/sync", tags=["sync"])


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


# --- Sync Module Endpoints ---

class SyncCheckRequest(BaseModel):
    year_from: int = Field(2024, ge=1996, le=2025)
    year_to: int = Field(2025, ge=1996, le=2025)
    max_per_month: int = Field(10, ge=1, le=100)


class SyncIngestRequest(BaseModel):
    limit: Optional[int] = Field(None, description="Max number of decisions to ingest (None = all)")


@sync_router.post("/check")
async def sync_check_new_decisions(payload: SyncCheckRequest, state=Depends(get_app_state)):
    """Check eLibrary for new decisions and stage them in the queue."""
    sync_service = state.sync_service
    
    try:
        sync_job_id = await run_in_threadpool(
            sync_service.check_for_new_decisions,
            payload.year_from,
            payload.year_to,
            payload.max_per_month
        )
        
        # Get sync job results
        with state.db_pool.connection() as conn:
            result = conn.execute(
                """
                SELECT status, total_checked, new_found, failed_count
                FROM sync_jobs 
                WHERE id = %s
                """,
                (sync_job_id,)
            ).fetchone()
        
        if not result:
            raise HTTPException(status_code=404, detail="Sync job not found")
        
        return {
            "job_id": sync_job_id,
            "status": result[0],
            "total_checked": result[1] or 0,
            "new_found": result[2] or 0,
            "failed": result[3] or 0,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Sync check failed: {exc}")


@sync_router.post("/download")
async def sync_download_pdfs(state=Depends(get_app_state)):
    """Download PDFs for all pending decisions."""
    sync_service = state.sync_service
    result = await run_in_threadpool(sync_service.download_pending_pdfs)
    return result


@sync_router.post("/ingest")
async def sync_ingest_decisions(payload: SyncIngestRequest, state=Depends(get_app_state)):
    """Ingest downloaded decisions using the existing pipeline."""
    sync_service = state.sync_service
    pipeline = state.pipeline
    
    result = await run_in_threadpool(
        sync_service.ingest_pending_decisions,
        pipeline,
        payload.limit
    )
    return result


@sync_router.get("/pending")
async def sync_get_pending(state=Depends(get_app_state)):
    """Get list of pending decisions."""
    with state.db_pool.connection() as conn:
        pending = conn.execute(
            """
            SELECT id, doc_id, docket_no, title, decision_date, status, 
                   error_message, created_at, updated_at
            FROM pending_decisions
            ORDER BY created_at DESC
            """
        ).fetchall()
    
    return {
        "pending": [
            {
                "id": row[0],
                "doc_id": row[1],
                "docket_no": row[2],
                "title": row[3],
                "decision_date": row[4].isoformat() if row[4] else None,
                "status": row[5],
                "error_message": row[6],
                "created_at": row[7].isoformat(),
                "updated_at": row[8].isoformat(),
            }
            for row in pending
        ]
    }


@sync_router.get("/status")
async def sync_get_status(state=Depends(get_app_state)):
    """Get sync module status and statistics."""
    with state.db_pool.connection() as conn:
        stats = conn.execute(
            """
            SELECT 
                COUNT(*) FILTER (WHERE status = 'pending') as pending_count,
                COUNT(*) FILTER (WHERE status = 'downloading') as downloading_count,
                COUNT(*) FILTER (WHERE status = 'downloaded') as downloaded_count,
                COUNT(*) FILTER (WHERE status = 'ingesting') as ingesting_count,
                COUNT(*) FILTER (WHERE status = 'ingested') as ingested_count,
                COUNT(*) FILTER (WHERE status = 'failed') as failed_count
            FROM pending_decisions
            """
        ).fetchone()
        
        recent_jobs = conn.execute(
            """
            SELECT id, started_at, completed_at, status, total_checked, 
                   new_found, downloaded, failed
            FROM sync_jobs
            ORDER BY started_at DESC
            LIMIT 10
            """
        ).fetchall()
    
    return {
        "stats": {
            "pending": stats[0] or 0,
            "downloading": stats[1] or 0,
            "downloaded": stats[2] or 0,
            "ingesting": stats[3] or 0,
            "ingested": stats[4] or 0,
            "failed": stats[5] or 0,
        },
        "recent_jobs": [
            {
                "id": row[0],
                "started_at": row[1].isoformat(),
                "completed_at": row[2].isoformat() if row[2] else None,
                "status": row[3],
                "total_checked": row[4],
                "new_found": row[5],
                "downloaded": row[6],
                "failed": row[7],
            }
            for row in recent_jobs
        ]
    }
