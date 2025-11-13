import type { SearchFilters } from '../lib/types'

interface FilterPanelProps {
  filters: SearchFilters
  onChange: (next: SearchFilters) => void
}

export default function FilterPanel({ filters, onChange }: FilterPanelProps) {
  return (
    <div className="grid gap-4 rounded-xl border border-slate-200 bg-white p-4 md:grid-cols-4">
      <label className="text-sm font-medium text-slate-600">
        Court
        <input
          type="text"
          placeholder="PH Supreme Court"
          className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-brand-navy focus:outline-none"
          value={filters.court ?? ''}
          onChange={(e) => onChange({ ...filters, court: e.target.value })}
        />
      </label>
      <label className="text-sm font-medium text-slate-600">
        Date From
        <input
          type="date"
          className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-brand-navy focus:outline-none"
          value={filters.date_from ?? ''}
          onChange={(e) => onChange({ ...filters, date_from: e.target.value })}
        />
      </label>
      <label className="text-sm font-medium text-slate-600">
        Date To
        <input
          type="date"
          className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-brand-navy focus:outline-none"
          value={filters.date_to ?? ''}
          onChange={(e) => onChange({ ...filters, date_to: e.target.value })}
        />
      </label>
      <label className="text-sm font-medium text-slate-600">
        Case Number
        <input
          type="text"
          placeholder="G.R. No. 123456"
          className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-brand-navy focus:outline-none"
          value={filters.case_number ?? ''}
          onChange={(e) => onChange({ ...filters, case_number: e.target.value })}
        />
      </label>
    </div>
  )
}
