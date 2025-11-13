import { type FormEvent, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { ingestCase, reindexFolder } from '../lib/api'
import type { ActivityType } from '../lib/types'

interface IngestionViewProps {
  onActivity: (type: ActivityType, description: string) => void
}

export default function IngestionView({ onActivity }: IngestionViewProps) {
  const [filePath, setFilePath] = useState('')
  const [folderPath, setFolderPath] = useState('')
  const [dropExisting, setDropExisting] = useState(false)

  const ingestMutation = useMutation({
    mutationFn: (path: string) => ingestCase(path),
    onSuccess: (data) => {
      onActivity('ingest', `Ingested case ${data.case_id} (${data.chunks} chunks)`)
      setFilePath('')
    },
  })

  const folderMutation = useMutation({
    mutationFn: ({ path, drop }: { path: string; drop: boolean }) => reindexFolder(path, drop),
    onSuccess: (data) => {
      onActivity('ingest', `Reindexed folder (${data.cases} cases)`)
      setFolderPath('')
    },
  })

  const handleSingleIngest = (event: FormEvent) => {
    event.preventDefault()
    if (!filePath.trim()) return
    ingestMutation.mutate(filePath.trim())
  }

  const handleFolderIngest = (event: FormEvent) => {
    event.preventDefault()
    if (!folderPath.trim()) return
    folderMutation.mutate({ path: folderPath.trim(), drop: dropExisting })
  }

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-slate-900">Ingest a single case PDF</h2>
        <p className="mt-1 text-sm text-slate-500">Provide an absolute file path accessible to the backend worker.</p>
        <form onSubmit={handleSingleIngest} className="mt-4 flex flex-col gap-3 md:flex-row">
          <input
            type="text"
            className="flex-1 rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-brand-navy focus:outline-none"
            placeholder="/cases/G.R.-12345.pdf"
            value={filePath}
            onChange={(e) => setFilePath(e.target.value)}
          />
          <button
            type="submit"
            className="rounded-lg bg-brand-navy px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
            disabled={ingestMutation.isPending}
          >
            {ingestMutation.isPending ? 'Ingesting...' : 'Ingest Case'}
          </button>
        </form>
        {ingestMutation.isError && (
          <p className="mt-2 text-sm text-red-600">Error: {(ingestMutation.error as Error).message}</p>
        )}
        {ingestMutation.isSuccess && (
          <p className="mt-2 text-sm text-emerald-600">
            Case {ingestMutation.data.case_id} stored ({ingestMutation.data.chunks} chunks)
          </p>
        )}
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-slate-900">Reindex a folder</h2>
        <p className="mt-1 text-sm text-slate-500">Batch process all PDFs inside a folder (recursive).</p>
        <form onSubmit={handleFolderIngest} className="mt-4 space-y-4">
          <input
            type="text"
            className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-brand-navy focus:outline-none"
            placeholder="/cases/supreme-court/"
            value={folderPath}
            onChange={(e) => setFolderPath(e.target.value)}
          />
          <label className="flex items-center gap-2 text-sm text-slate-600">
            <input
              type="checkbox"
              checked={dropExisting}
              onChange={(e) => setDropExisting(e.target.checked)}
              className="rounded border-slate-300"
            />
            Drop existing cases before reindexing
          </label>
          <button
            type="submit"
            className="rounded-lg bg-brand-navy px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
            disabled={folderMutation.isPending}
          >
            {folderMutation.isPending ? 'Reindexing...' : 'Reindex Folder'}
          </button>
        </form>
        {folderMutation.isError && (
          <p className="mt-2 text-sm text-red-600">Error: {(folderMutation.error as Error).message}</p>
        )}
        {folderMutation.isSuccess && (
          <p className="mt-2 text-sm text-emerald-600">
            Reindexed {folderMutation.data.cases} cases / {folderMutation.data.chunks} chunks
          </p>
        )}
      </section>
    </div>
  )
}
