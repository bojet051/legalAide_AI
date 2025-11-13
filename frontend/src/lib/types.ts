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
