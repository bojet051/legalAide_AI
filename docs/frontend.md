# LegalAide Frontend Design

## Goals
- Provide a clean operator console to ingest Supreme Court PDFs, monitor status, and query the knowledge base.
- Emphasize fast legal research: semantic search, filters, and RAG-powered answers front and center.
- Keep the stack lightweight (Vite + React + TypeScript) so it pairs naturally with the FastAPI backend.

## Information Architecture
1. **Global Shell**
   - Top navigation bar with brand, environment badge (“Local”/“Prod”), and quick links to API docs.
   - Left sidebar for primary flows: *Dashboard*, *Ingestion*, *Search & Ask*, *Cases*.
2. **Dashboard**
   - Summary cards (total cases, chunks, last ingest time).
   - Activity log stream (ingestion events, failed OCR, etc.).
3. **Ingestion**
   - File picker to upload single PDF (POST `/ingest_case`).
   - Folder ingest form with options (drop existing, dry run) hitting `/reindex_folder`.
   - Status table listing recent ingests with outcomes.
4. **Search & Ask**
   - Two tabs:
     - *Semantic Search*: query input, filters (court, date range, case number), results list with chunk preview + metadata.
     - *Ask Legal Question*: question input, same filters, displays synthesized answer + supporting chunks.
5. **Cases**
   - Table of known cases (lazy-loaded via `/case/{id}` fetches on demand).
   - Detail drawer showing metadata, full text (toggle), chunk list.

## Component Architecture
- `AppShell`: handles layout, navigation, theme.
- `DashboardView`, `IngestionView`, `SearchView`, `AskView`, `CasesView`.
- Shared components:
  - `FilterPanel` for court/date/case number filters.
  - `ChunkCard` for displaying chunk metadata and snippet.
  - `StatusToast` to surface API errors/success.
  - `LoadingOverlay` for async states.

## State Management
- React Query (TanStack) to manage API calls, caching, loading/error states.
- Local component state for form inputs, filters, selection.

## Styling
- Tailwind CSS for rapid utility-first styling.
- Color palette mirrors legal document aesthetics: navy, slate, and accent gold.
- Responsive layout (desktop-first but functional on tablet).

## API Client
- `src/lib/api.ts` centralizes fetch helpers for:
  - `ingestCase(file_path)`
  - `reindexFolder(folder_path, drop_existing)`
  - `searchChunks(payload)`
  - `askQuestion(payload)`
  - `getCase(case_id)`
- Base URL defaults to `http://localhost:8000`.

## Error Handling & UX
- All mutations show optimistic spinner + toast notifications.
- Validation for required fields (file path, question, query).
- Empty states with guidance (“Try narrowing the date range”).

## Implementation Notes
- Use Vite + React + TypeScript + Tailwind + React Query + Heroicons.
- Configure `pnpm dev` to run at `localhost:5173` and proxy `/api` calls to FastAPI for local dev if needed.
- `.env` for `VITE_API_BASE_URL`.

This design keeps the MVP focused while leaving room for richer analytics and collaboration tooling later.
