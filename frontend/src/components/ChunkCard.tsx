import type { ChunkResult } from '../lib/types'

interface ChunkCardProps {
  chunk: ChunkResult
}

export default function ChunkCard({ chunk }: ChunkCardProps) {
  return (
    <article className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-2 text-sm text-slate-500">
        <div className="font-semibold text-slate-800">{chunk.title ?? 'Untitled Case'}</div>
        <span className="rounded-full bg-slate-100 px-3 py-0.5 text-xs uppercase tracking-wide text-slate-500">
          {chunk.section_type ?? 'chunk'} #{chunk.chunk_index}
        </span>
      </div>
      <p className="mt-3 max-h-48 overflow-hidden text-sm leading-relaxed text-slate-700">{chunk.chunk_text}</p>
      <div className="mt-4 flex flex-wrap items-center gap-3 text-xs text-slate-500">
        {chunk.case_number && <span>G.R. {chunk.case_number}</span>}
        {chunk.promulgation_date && (
          <span>{new Date(chunk.promulgation_date).toLocaleDateString(undefined, { dateStyle: 'medium' })}</span>
        )}
        <span>{chunk.token_count} tokens</span>
        <span>score {(1 - chunk.distance).toFixed(3)}</span>
      </div>
    </article>
  )
}
