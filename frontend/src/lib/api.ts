import type {
  AskRequestPayload,
  AskResponse,
  CaseRecord,
  SearchFilters,
  SearchRequestPayload,
  ChunkResult,
} from './types'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      'Content-Type': 'application/json',
    },
    ...options,
  })

  if (!response.ok) {
    const text = await response.text()
    throw new Error(text || response.statusText)
  }

  if (response.status === 204) {
    return {} as T
  }
  return response.json() as Promise<T>
}

export async function ingestCase(filePath: string) {
  return request<{ case_id: number; chunks: number }>('/ingest_case', {
    method: 'POST',
    body: JSON.stringify({ file_path: filePath }),
  })
}

export async function reindexFolder(folderPath: string, dropExisting: boolean) {
  return request<{ cases: number; chunks: number }>('/reindex_folder', {
    method: 'POST',
    body: JSON.stringify({ folder_path: folderPath, drop_existing: dropExisting }),
  })
}

export async function searchChunks(payload: SearchRequestPayload) {
  return request<{ results: ChunkResult[] }>('/search', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function askQuestion(payload: AskRequestPayload) {
  return request<AskResponse>('/ask', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function fetchCase(caseId: number) {
  return request<CaseRecord>(`/case/${caseId}`)
}

export function normalizeFilters(filters: SearchFilters): SearchFilters {
  return {
    court: filters.court || undefined,
    date_from: filters.date_from || undefined,
    date_to: filters.date_to || undefined,
    case_number: filters.case_number || undefined,
  }
}

// Sync API
export async function checkNewDecisions(yearFrom: number, yearTo: number, maxPerMonth: number) {
  return request<import('./types').CheckResponse>('/sync/check', {
    method: 'POST',
    body: JSON.stringify({ year_from: yearFrom, year_to: yearTo, max_per_month: maxPerMonth }),
  })
}

export async function downloadPendingPdfs() {
  return request<import('./types').DownloadResponse>('/sync/download', {
    method: 'POST',
  })
}

export async function ingestPendingDecisions(limit?: number) {
  return request<import('./types').IngestResponse>('/sync/ingest', {
    method: 'POST',
    body: JSON.stringify({ limit }),
  })
}

export async function getPendingDecisions() {
  return request<import('./types').PendingResponse>('/sync/pending')
}

export async function getSyncStatus() {
  return request<import('./types').SyncStatusResponse>('/sync/status')
}
