import type { ActivityItem } from '../lib/types'

interface DashboardProps {
  activity: ActivityItem[]
}

export default function DashboardView({ activity }: DashboardProps) {
  const ingestCount = activity.filter((item) => item.type === 'ingest').length
  const searchCount = activity.filter((item) => item.type === 'search').length
  const askCount = activity.filter((item) => item.type === 'ask').length

  const stats = [
    { label: 'Ingestion actions', value: ingestCount },
    { label: 'Semantic searches', value: searchCount },
    { label: 'LLM answers', value: askCount },
  ]

  return (
    <div className="space-y-6">
      <section className="grid gap-4 md:grid-cols-3">
        {stats.map((stat) => (
          <div key={stat.label} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-xs uppercase tracking-wide text-slate-500">{stat.label}</p>
            <p className="mt-2 text-3xl font-semibold text-brand-navy">{stat.value}</p>
          </div>
        ))}
      </section>

      <section className="grid gap-6 lg:grid-cols-2">
        <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="text-lg font-semibold text-slate-900">How to use LegalAide</h2>
          <ol className="mt-4 space-y-3 text-sm text-slate-700">
            <li>
              <span className="font-semibold text-brand-navy">1.</span> Use the Ingestion view to ingest individual PDFs
              or rebuild from a folder.
            </li>
            <li>
              <span className="font-semibold text-brand-navy">2.</span> Head to Research to run semantic searches or ask a
              legal question with RAG context.
            </li>
            <li>
              <span className="font-semibold text-brand-navy">3.</span> Inspect any case and its chunked text from the
              Cases view.
            </li>
          </ol>
        </article>

        <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="text-lg font-semibold text-slate-900">Activity feed</h2>
          <div className="mt-4 space-y-3">
            {activity.length === 0 && <p className="text-sm text-slate-500">No activity yet.</p>}
            {activity.slice(0, 6).map((item) => (
              <div key={item.id} className="rounded-xl bg-slate-50 px-4 py-3 text-sm">
                <p className="font-medium text-slate-800">{item.description}</p>
                <p className="text-xs text-slate-500">
                  {new Date(item.timestamp).toLocaleString(undefined, {
                    dateStyle: 'short',
                    timeStyle: 'short',
                  })}
                </p>
              </div>
            ))}
          </div>
        </article>
      </section>
    </div>
  )
}
