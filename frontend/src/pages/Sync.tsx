import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { checkNewDecisions, downloadPendingPdfs, getPendingDecisions, getSyncStatus, ingestPendingDecisions } from '../lib/api'
import type { ActivityType, CheckResponse, DownloadResponse, IngestResponse, PendingDecision } from '../lib/types'

interface SyncViewProps {
  onActivity: (type: ActivityType, description: string) => void
}

export default function SyncView({ onActivity }: SyncViewProps) {
  const [yearFrom, setYearFrom] = useState(2024)
  const [yearTo, setYearTo] = useState(2025)
  const [maxPerMonth, setMaxPerMonth] = useState(10)

  const { data: statusData, refetch: refetchStatus } = useQuery({
    queryKey: ['sync-status'],
    queryFn: getSyncStatus,
    refetchInterval: 5000,
  })

  const { data: pendingData, refetch: refetchPending } = useQuery({
    queryKey: ['pending-decisions'],
    queryFn: getPendingDecisions,
    refetchInterval: 5000,
  })

  const checkMutation = useMutation({
    mutationFn: (params: { yearFrom: number; yearTo: number; maxPerMonth: number }) =>
      checkNewDecisions(params.yearFrom, params.yearTo, params.maxPerMonth),
    onSuccess: (data: CheckResponse) => {
      onActivity('ingest', `Found ${data.new_found} new decisions`)
      refetchStatus()
      refetchPending()
    },
  })

  const downloadMutation = useMutation({
    mutationFn: downloadPendingPdfs,
    onSuccess: (data: DownloadResponse) => {
      onActivity('ingest', `Downloaded ${data.downloaded} decisions`)
      refetchStatus()
      refetchPending()
    },
  })

  const ingestMutation = useMutation({
    mutationFn: (limit?: number) => ingestPendingDecisions(limit),
    onSuccess: (data: IngestResponse) => {
      onActivity('ingest', `Ingested ${data.ingested} decisions`)
      refetchStatus()
      refetchPending()
    },
  })

  const handleCheck = () => {
    checkMutation.mutate({ yearFrom, yearTo, maxPerMonth })
  }

  const stats = statusData?.stats || {
    pending: 0,
    downloading: 0,
    downloaded: 0,
    ingesting: 0,
    ingested: 0,
    failed: 0,
  }
  const pending = pendingData?.pending || []

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-slate-900">eLibrary Sync</h2>
        <p className="mt-1 text-sm text-slate-500">Check for new Supreme Court decisions and ingest them.</p>

        <div className="mt-4 grid gap-4 md:grid-cols-3">
          <label className="text-sm font-medium text-slate-600">
            From Year
            <input
              type="number"
              min={1996}
              max={2025}
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
              value={yearFrom}
              onChange={(e) => setYearFrom(Number(e.target.value))}
            />
          </label>
          <label className="text-sm font-medium text-slate-600">
            To Year
            <input
              type="number"
              min={1996}
              max={2025}
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
              value={yearTo}
              onChange={(e) => setYearTo(Number(e.target.value))}
            />
          </label>
          <label className="text-sm font-medium text-slate-600">
            Max per month
            <input
              type="number"
              min={1}
              max={100}
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
              value={maxPerMonth}
              onChange={(e) => setMaxPerMonth(Number(e.target.value))}
            />
          </label>
        </div>

        <div className="mt-4 flex gap-3">
          <button
            onClick={handleCheck}
            disabled={checkMutation.isPending}
            className="rounded-lg bg-brand-navy px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
          >
            {checkMutation.isPending ? 'Checking...' : 'Check for New Decisions'}
          </button>
          <button
            onClick={() => downloadMutation.mutate()}
            disabled={downloadMutation.isPending || stats.pending === 0}
            className="rounded-lg border border-brand-navy px-4 py-2 text-sm font-semibold text-brand-navy disabled:opacity-60"
          >
            {downloadMutation.isPending ? 'Downloading...' : `Download (${stats.pending || 0})`}
          </button>
          <button
            onClick={() => ingestMutation.mutate(undefined)}
            disabled={ingestMutation.isPending || stats.downloaded === 0}
            className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
          >
            {ingestMutation.isPending ? 'Ingesting...' : `Ingest All (${stats.downloaded || 0})`}
          </button>
        </div>

        {checkMutation.isError && (
          <p className="mt-2 text-sm text-red-600">Error: {(checkMutation.error as Error).message}</p>
        )}
        {checkMutation.isSuccess && (
          <p className="mt-2 text-sm text-emerald-600">
            Found {checkMutation.data.new_found} new decisions (checked {checkMutation.data.total_checked})
          </p>
        )}
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <h3 className="text-lg font-semibold text-slate-900">Status Overview</h3>
        <div className="mt-4 grid gap-3 md:grid-cols-6">
          {Object.entries(stats).map(([key, value]) => (
            <div key={key} className="rounded-lg border border-slate-200 bg-slate-50 p-3">
              <p className="text-xs uppercase tracking-wide text-slate-500">{key}</p>
              <p className="mt-1 text-2xl font-semibold text-brand-navy">{String(value)}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <h3 className="text-lg font-semibold text-slate-900">Pending Decisions ({pending.length})</h3>
        <div className="mt-4 space-y-2">
          {pending.length === 0 && <p className="text-sm text-slate-500">No pending decisions.</p>}
          {pending.slice(0, 50).map((item: PendingDecision) => (
            <div key={item.id} className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm">
              <div className="flex items-center justify-between">
                <div className="flex-1">
                  <p className="font-semibold text-slate-800">{item.docket_no || item.doc_id}</p>
                  <p className="text-slate-600">{item.title}</p>
                </div>
                <span
                  className={`rounded-full px-3 py-1 text-xs font-semibold ${
                    item.status === 'ingested'
                      ? 'bg-emerald-100 text-emerald-700'
                      : item.status === 'failed'
                        ? 'bg-red-100 text-red-700'
                        : 'bg-blue-100 text-blue-700'
                  }`}
                >
                  {item.status}
                </span>
              </div>
              {item.error_message && <p className="mt-1 text-xs text-red-600">{item.error_message}</p>}
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}
