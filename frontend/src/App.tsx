import { useCallback, useState } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import AppShell from './components/AppShell'
import type { ActivityItem, ActivityType } from './lib/types'
import DashboardView from './pages/Dashboard'
import IngestionView from './pages/Ingestion'
import ResearchView from './pages/Research'
import CasesView from './pages/Cases'

export default function App() {
  const [activity, setActivity] = useState<ActivityItem[]>([])

  const recordActivity = useCallback((type: ActivityType, description: string) => {
    setActivity((prev) => {
      const entry: ActivityItem = {
        id: crypto.randomUUID(),
        type,
        description,
        timestamp: new Date().toISOString(),
      }
      return [entry, ...prev].slice(0, 40)
    })
  }, [])

  return (
    <AppShell activity={activity}>
      <Routes>
        <Route path="/" element={<DashboardView activity={activity} />} />
        <Route path="/ingest" element={<IngestionView onActivity={recordActivity} />} />
        <Route path="/research" element={<ResearchView onActivity={recordActivity} />} />
        <Route path="/cases" element={<CasesView onActivity={recordActivity} />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AppShell>
  )
}
