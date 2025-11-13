import { type FormEvent, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import FilterPanel from '../components/FilterPanel'
import ChunkCard from '../components/ChunkCard'
import { askQuestion, normalizeFilters, searchChunks } from '../lib/api'
import type { ActivityType, AskResponse, ChunkResult, SearchFilters } from '../lib/types'

interface ResearchViewProps {
  onActivity: (type: ActivityType, description: string) => void
}

type Mode = 'search' | 'ask'

export default function ResearchView({ onActivity }: ResearchViewProps) {
  const [mode, setMode] = useState<Mode>('search')
  const [filters, setFilters] = useState<SearchFilters>({ court: 'PH Supreme Court' })
  const [query, setQuery] = useState('')
  const [question, setQuestion] = useState('')

  const searchMutation = useMutation({
    mutationFn: async (payload: { query: string }) => {
      const body = {
        query: payload.query,
        top_k: 12,
        ...normalizeFilters(filters),
      }
      return searchChunks(body)
    },
    onSuccess: (data, variables) => {
      onActivity('search', `Searched "${variables.query}" (${data.results.length} chunks)`)
    },
  })

  const askMutation = useMutation({
    mutationFn: async (payload: { question: string }) => {
      const body = {
        question: payload.question,
        top_k: 8,
        ...normalizeFilters(filters),
      }
      return askQuestion(body)
    },
    onSuccess: (_, variables) => {
      onActivity('ask', `Answered "${variables.question}"`)
    },
  })

  const handleSearch = (event: FormEvent) => {
    event.preventDefault()
    if (!query.trim()) return
    searchMutation.mutate({ query: query.trim() })
  }

  const handleAsk = (event: FormEvent) => {
    event.preventDefault()
    if (!question.trim()) return
    askMutation.mutate({ question: question.trim() })
  }

  const activeTabClasses = 'bg-white text-brand-navy shadow'
  const inactiveTabClasses = 'text-slate-500 hover:text-brand-navy'

  const chunkResults = (searchMutation.data?.results ?? []) as ChunkResult[]
  const askResults = askMutation.data as AskResponse | undefined

  return (
    <div className="space-y-6">
      <div className="inline-flex rounded-full border border-slate-200 bg-slate-100 p-1 text-sm">
        <button
          className={`rounded-full px-4 py-2 font-semibold transition ${mode === 'search' ? activeTabClasses : inactiveTabClasses}`}
          onClick={() => setMode('search')}
        >
          Semantic Search
        </button>
        <button
          className={`rounded-full px-4 py-2 font-semibold transition ${mode === 'ask' ? activeTabClasses : inactiveTabClasses}`}
          onClick={() => setMode('ask')}
        >
          Ask a Question
        </button>
      </div>

      <FilterPanel filters={filters} onChange={setFilters} />

      {mode === 'search' && (
        <section className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <form className="flex flex-col gap-3 md:flex-row" onSubmit={handleSearch}>
            <input
              type="text"
              placeholder="warrantless arrest hot pursuit"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="flex-1 rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-brand-navy focus:outline-none"
            />
            <button
              type="submit"
              className="rounded-lg bg-brand-navy px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
              disabled={searchMutation.isPending}
            >
              {searchMutation.isPending ? 'Searching…' : 'Search'}
            </button>
          </form>

          {searchMutation.isError && (
            <p className="text-sm text-red-600">Error: {(searchMutation.error as Error).message}</p>
          )}

          <div className="space-y-3">
            {chunkResults.length === 0 && !searchMutation.isPending && (
              <p className="text-sm text-slate-500">No results yet. Try searching for a doctrine or fact pattern.</p>
            )}
            {chunkResults.map((chunk) => (
              <ChunkCard key={chunk.chunk_id} chunk={chunk} />
            ))}
          </div>
        </section>
      )}

      {mode === 'ask' && (
        <section className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <form className="flex flex-col gap-3 md:flex-row" onSubmit={handleAsk}>
            <input
              type="text"
              placeholder="When is a warrantless arrest valid in hot pursuit?"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              className="flex-1 rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-brand-navy focus:outline-none"
            />
            <button
              type="submit"
              className="rounded-lg bg-brand-navy px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
              disabled={askMutation.isPending}
            >
              {askMutation.isPending ? 'Generating…' : 'Ask'}
            </button>
          </form>

          {askMutation.isError && <p className="text-sm text-red-600">Error: {(askMutation.error as Error).message}</p>}

          {askResults && (
            <div className="space-y-4">
              <article className="rounded-xl border border-brand-navy/20 bg-brand-navy/5 p-4">
                <h3 className="text-sm font-semibold uppercase tracking-wide text-brand-navy">Answer</h3>
                <p className="mt-2 whitespace-pre-line text-sm leading-relaxed text-slate-800">{askResults.answer}</p>
              </article>
              <div className="space-y-3">
                <h4 className="text-sm font-semibold text-slate-700">Supporting Chunks</h4>
                {askResults.supporting_chunks.map((chunk) => (
                  <ChunkCard key={chunk.chunk_id} chunk={chunk} />
                ))}
              </div>
            </div>
          )}
        </section>
      )}
    </div>
  )
}
