import type { ReactNode } from 'react'
import { NavLink } from 'react-router-dom'
import { BookOpenIcon, CloudArrowUpIcon, MagnifyingGlassIcon, RectangleStackIcon, ArrowPathIcon } from '@heroicons/react/24/outline'
import clsx from 'clsx'
import type { ActivityItem } from '../lib/types'

interface AppShellProps {
  children: ReactNode
  activity: ActivityItem[]
}

const navItems = [
  { label: 'Dashboard', to: '/', icon: RectangleStackIcon },
  { label: 'Ingestion', to: '/ingest', icon: CloudArrowUpIcon },
  { label: 'Research', to: '/research', icon: MagnifyingGlassIcon },
  { label: 'Cases', to: '/cases', icon: BookOpenIcon },
  { label: 'Sync', to: '/sync', icon: ArrowPathIcon },
]

export default function AppShell({ children, activity }: AppShellProps) {
  const latestActivity = activity[0]
  const envLabel = import.meta.env.MODE === 'production' ? 'Production' : 'Local'

  return (
    <div className="flex min-h-screen bg-slate-50 text-slate-900">
      <aside className="hidden min-h-screen w-64 flex-shrink-0 bg-brand-navy px-4 py-6 text-white md:flex md:flex-col">
        <div className="mb-10 px-2">
          <div className="text-xs uppercase tracking-widest text-brand-gold">LegalAide</div>
          <div className="text-2xl font-semibold">Console</div>
        </div>
        <nav className="space-y-2 text-sm font-medium">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                clsx(
                  'flex items-center gap-2 rounded-md px-3 py-2 transition hover:bg-white/10',
                  isActive ? 'bg-white/15 text-white' : 'text-white/70',
                )
              }
            >
              <item.icon className="h-5 w-5" />
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="mt-auto rounded-lg bg-white/10 px-3 py-4 text-sm text-white/80">
          <p className="text-xs uppercase tracking-wide text-brand-gold">Latest</p>
          {latestActivity ? (
            <>
              <p className="font-semibold text-white">{latestActivity.description}</p>
              <p className="text-xs text-white/70">
                {new Date(latestActivity.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </p>
            </>
          ) : (
            <p>No activity yet.</p>
          )}
        </div>
      </aside>

      <main className="flex-1">
        <header className="flex flex-col gap-3 border-b border-slate-200 bg-white px-4 py-4 shadow-sm sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-xs uppercase tracking-widest text-slate-500">Legal Research Assistant</p>
            <h1 className="text-2xl font-semibold text-slate-900">LegalAide</h1>
            <nav className="mt-3 flex flex-wrap gap-2 md:hidden">
              {navItems.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={({ isActive }) =>
                    clsx(
                      'rounded-full border px-3 py-1 text-xs font-semibold transition',
                      isActive ? 'border-brand-navy text-brand-navy' : 'border-slate-200 text-slate-500',
                    )
                  }
                >
                  {item.label}
                </NavLink>
              ))}
            </nav>
          </div>
          <div className="flex items-center gap-3">
            <span className="rounded-full bg-brand-navy/10 px-3 py-1 text-xs font-semibold text-brand-navy">{envLabel}</span>
            <a
              href={`${import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'}/docs`}
              target="_blank"
              rel="noreferrer"
              className="rounded-full border border-brand-navy/30 px-3 py-1 text-xs font-medium text-brand-navy hover:bg-brand-navy hover:text-white"
            >
              API Docs
            </a>
          </div>
        </header>
        <div className="px-4 py-6 sm:px-8">{children}</div>
      </main>
    </div>
  )
}
