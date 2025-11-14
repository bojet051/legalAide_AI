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

## Data scraping utility

The repository ships with `scripts/scrape_elibrary.py`, a polite scraper that walks the
Philippine Supreme Court E-Library “Bookshelf” (category 1) from 1996 through 2025,
collecting metadata plus full decision texts.

```bash
python scripts/scrape_elibrary.py --output-dir data
```

Key behaviors:
- Honors `robots.txt`, rate-limits requests (2–5 s jitter), and stops if CAPTCHAs or access-denied pages appear.
- Parses each year/month bucket, follows pagination, grabs docket/title/date/ponente/division/keywords, and saves metadata to `metadata.csv` and `metadata.json`.
- Downloads each decision body into `data/full_texts/decision_<doc_id>.txt`.
- Supports optional Selenium fallback (`--use-selenium`) if a month page renders without static HTML content.

Use `--max-decisions N` when testing to avoid long runs. The outputs can later feed the ingestion pipeline without requiring OCR because the site already exposes text.

## Environment variables

Create a `.env` (copy from `.env.example`) and set the variables below. Keep secrets out of source control and use a secret manager in production.

Required (backend)
- `DATABASE_URL` — PostgreSQL DSN (e.g. `postgresql://user:pass@host:5432/dbname`).

Optional / configuration
- `EMBEDDING_API_URL` — HTTP endpoint for the embedding service (if using a hosted embedder).
- `EMBEDDING_API_KEY` — API key for the embedding service.
- `EMBEDDING_MODEL` — embedding model name (used by the embedding client).
- `EMBEDDING_DIM` — embedding vector dimension (integer).
- `LLM_API_URL` — HTTP endpoint for the LLM (OpenAI-like API).
- `LLM_API_KEY` — API key for the LLM service.
- `LLM_MODEL` — model identifier used when calling the LLM.
- `TESSERACT_CMD` — path to the `tesseract` binary (only needed for OCR on scanned PDFs).
- `CHUNK_TOKEN_SIZE` — tokens per chunk (backend chunking setting).
- `CHUNK_OVERLAP_RATIO` — sliding window overlap ratio (0.0-1.0).

Frontend
- `VITE_API_BASE_URL` — base URL for the backend API (defaults to `http://localhost:8000` if not set).


## Frontend Console

A companion React/Tailwind console lives under `frontend/` for ingestion + research workflows.

```bash
cd frontend
cp .env.example .env  # optional override of VITE_API_BASE_URL
pnpm install
pnpm dev
```

The frontend expects the FastAPI server (with CORS enabled) to be running locally on port `8000`.
