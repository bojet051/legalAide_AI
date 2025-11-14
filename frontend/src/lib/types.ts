export interface SearchFilters {
  court?: string | null
  date_from?: string | null
  date_to?: string | null
  case_number?: string | null
}

export interface SearchRequestPayload extends SearchFilters {
  query: string
  top_k?: number
}

export interface AskRequestPayload extends SearchFilters {
  question: string
  top_k?: number
}

export interface ChunkResult {
  chunk_id: number
  case_id: number
  section_type: string | null
  chunk_index: number
  chunk_text: string
  token_count: number
  case_number: string | null
  title: string | null
  promulgation_date: string | null
  court: string | null
  distance: number
}

export interface AskResponse {
  answer: string
  supporting_chunks: ChunkResult[]
  case_ids: number[]
}

export interface CaseRecord {
  id: number
  case_number: string | null
  title: string | null
  court: string | null
  promulgation_date: string | null
  full_text: string | null
  source_file: string | null
  created_at: string
  chunks: Array<{
    id: number
    section_type: string | null
    chunk_index: number
    chunk_text: string
    token_count: number
    created_at: string
  }>
}

export type ActivityType = 'ingest' | 'search' | 'ask'

export interface ActivityItem {
  id: string
  type: ActivityType
  description: string
  timestamp: string
}

export interface PendingDecision {
  id: number
  doc_id: string
  docket_no: string | null
  title: string | null
  promulgation_date: string | null
  elibrary_url: string
  status: 'pending' | 'downloading' | 'downloaded' | 'ingesting' | 'ingested' | 'failed'
  file_path: string | null
  error_message: string | null
  created_at: string
  updated_at: string
}

export interface SyncJob {
  id: number
  job_type: 'check' | 'download' | 'ingest'
  status: 'running' | 'completed' | 'failed'
  year_from: number | null
  year_to: number | null
  max_per_month: number | null
  new_found: number | null
  total_checked: number | null
  downloaded: number | null
  ingested: number | null
  failed_count: number | null
  error_message: string | null
  started_at: string
  completed_at: string | null
}

export interface CheckResponse {
  new_found: number
  total_checked: number
  job_id: number
}

export interface DownloadResponse {
  downloaded: number
  failed: number
  job_id: number
}

export interface IngestResponse {
  ingested: number
  failed: number
  job_id: number
}

export interface PendingResponse {
  pending: PendingDecision[]
  count: number
}

export interface SyncStatusResponse {
  stats: {
    pending: number
    downloading: number
    downloaded: number
    ingesting: number
    ingested: number
    failed: number
  }
  recent_jobs: SyncJob[]
}
