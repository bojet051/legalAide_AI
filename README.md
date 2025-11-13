# LegalAide

LegalAide is a retrieval-augmented question-answering MVP for Philippine Supreme Court cases. It ingests PDF decisions, extracts/cleans text (with OCR fallbacks), chunks + embeds them, stores embeddings inside PostgreSQL (pgvector), and exposes FastAPI endpoints for ingestion, semantic search, and legal Q&A.

## Features

- PDF ingestion pipeline with scanned-PDF detection and pytesseract OCR
- Regex-based metadata extraction and section-aware chunking with sliding-window fallback
- Chunk/query embeddings via a pluggable embedding client interface
- PostgreSQL + pgvector storage with IVFFlat index for similarity search
- RAG answering service that retrieves top-K chunks, builds a context block, and calls a configurable LLM
- FastAPI endpoints:
  - `POST /ingest_case`
  - `POST /reindex_folder`
  - `POST /search`
  - `POST /ask`
  - `GET /case/{case_id}`

## Getting Started

1. **Install dependencies**
   ```bash
   pip install -e .
   ```
2. **Copy environment template**
   ```bash
   cp .env.example .env
   ```
   Fill in `DATABASE_URL`, embedding + LLM API credentials, and (optionally) `TESSERACT_CMD`.
3. **Apply migrations**
   ```bash
   psql "$DATABASE_URL" -f migrations/001_init.sql
   ```
4. **Run the API**
   ```bash
   uvicorn legal_aide.main:app --reload
   ```

Use `/docs` for interactive API exploration.

## Frontend Console

A companion React/Tailwind console lives under `frontend/` for ingestion + research workflows.

```bash
cd frontend
cp .env.example .env  # optional override of VITE_API_BASE_URL
pnpm install
pnpm dev
```

The frontend expects the FastAPI server (with CORS enabled) to be running locally on port `8000`.
