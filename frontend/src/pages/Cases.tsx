import { type FormEvent, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { fetchCase } from '../lib/api'
import type { ActivityType, CaseRecord } from '../lib/types'

interface CasesViewProps {
  onActivity: (type: ActivityType, description: string) => void
}

export default function CasesView({ onActivity }: CasesViewProps) {
  const [caseIdInput, setCaseIdInput] = useState('')
  const [caseRecord, setCaseRecord] = useState<CaseRecord | null>(null)

  const caseMutation = useMutation({
    mutationFn: (caseId: number) => fetchCase(caseId),
    onSuccess: (data) => {
      setCaseRecord(data)
      onActivity('search', `Opened case ${data.case_number ?? data.id}`)
    },
  })

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault()
    if (!caseIdInput.trim()) return
    const parsed = Number(caseIdInput)
    if (!Number.isFinite(parsed) || parsed <= 0) return
    caseMutation.mutate(parsed)
  }

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-slate-900">Lookup a case by ID</h2>
        <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-3 md:flex-row">
          <input
            type="number"
            min={1}
            placeholder="Case ID"
            value={caseIdInput}
            onChange={(e) => setCaseIdInput(e.target.value)}
            className="flex-1 rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-brand-navy focus:outline-none"
          />
          <button
            type="submit"
            className="rounded-lg bg-brand-navy px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
            disabled={caseMutation.isPending}
          >
            {caseMutation.isPending ? 'Loading…' : 'Fetch Case'}
          </button>
        </form>
        {caseMutation.isError && (
          <p className="mt-2 text-sm text-red-600">Error: {(caseMutation.error as Error).message}</p>
        )}
      </section>

      {caseRecord && (
        <section className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <header>
            <p className="text-xs uppercase tracking-wide text-slate-500">Case #{caseRecord.id}</p>
            <h2 className="text-2xl font-semibold text-slate-900">{caseRecord.title ?? 'Untitled Case'}</h2>
            <dl className="mt-2 grid gap-3 text-sm text-slate-600 sm:grid-cols-2">
              <div>
                <dt className="text-xs uppercase tracking-wide text-slate-500">G.R. Number</dt>
                <dd>{caseRecord.case_number ?? 'N/A'}</dd>
              </div>
              <div>
                <dt className="text-xs uppercase tracking-wide text-slate-500">Promulgation Date</dt>
                <dd>
                  {caseRecord.promulgation_date
                    ? new Date(caseRecord.promulgation_date).toLocaleDateString(undefined, { dateStyle: 'medium' })
                    : 'N/A'}
                </dd>
              </div>
              <div>
                <dt className="text-xs uppercase tracking-wide text-slate-500">Court</dt>
                <dd>{caseRecord.court ?? 'N/A'}</dd>
              </div>
              <div>
                <dt className="text-xs uppercase tracking-wide text-slate-500">Source File</dt>
                <dd className="truncate">{caseRecord.source_file ?? 'N/A'}</dd>
              </div>
            </dl>
          </header>

          <details className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700">
            <summary className="cursor-pointer text-sm font-semibold text-brand-navy">Full Text</summary>
            <p className="mt-3 whitespace-pre-wrap">{caseRecord.full_text?.slice(0, 5000) ?? 'No text stored.'}</p>
          </details>

          <div className="space-y-3">
            <h3 className="text-sm font-semibold text-slate-700">Chunks ({caseRecord.chunks.length})</h3>
            <div className="space-y-3">
              {caseRecord.chunks.map((chunk) => (
                <article key={chunk.id} className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm">
                  <div className="flex items-center justify-between text-xs font-semibold uppercase text-slate-500">
                    <span>{chunk.section_type ?? 'chunk'}</span>
                    <span># {chunk.chunk_index}</span>
                  </div>
                  <p className="mt-2 text-slate-700">{chunk.chunk_text.slice(0, 600)}...</p>
                </article>
              ))}
            </div>
          </div>
        </section>
      )}
    </div>
  )
}
