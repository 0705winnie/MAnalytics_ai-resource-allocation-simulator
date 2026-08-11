import { useEffect, useState } from 'react'
import { useAuth } from '../auth/AuthProvider'
import {
  getInstructorFinalLeaderboard,
  getInstructorSameStageLeaderboard,
  InstructorCourseApiError,
} from './api'
import type { InstructorCourse, InstructorLeaderboardResponse } from './types'

type View = 'same-stage' | 'final'

function formatRevenue(value: number): string {
  return `$${Math.round(value).toLocaleString()}`
}

function formatTimestamp(value: string | null): string {
  return value === null
    ? '—'
    : new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
}

export default function InstructorLeaderboards({ course }: { course: InstructorCourse }) {
  const { refreshAuth } = useAuth()
  const [view, setView] = useState<View>('same-stage')
  const [stage, setStage] = useState(1)
  const [data, setData] = useState<InstructorLeaderboardResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [requestVersion, setRequestVersion] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    async function load() {
      setLoading(true)
      setError(null)
      try {
        setData(view === 'final'
          ? await getInstructorFinalLeaderboard(course.id, controller.signal)
          : await getInstructorSameStageLeaderboard(course.id, stage, controller.signal))
      } catch (requestError) {
        if (controller.signal.aborted) return
        setData(null)
        if (requestError instanceof InstructorCourseApiError && requestError.code === 'unauthorized') {
          await refreshAuth()
        }
        setError('Leaderboard is temporarily unavailable.')
      } finally {
        if (!controller.signal.aborted) setLoading(false)
      }
    }
    void load()
    return () => controller.abort()
  }, [course.id, refreshAuth, requestVersion, stage, view])

  return (
    <section className="mt-6 rounded-xl border border-line bg-white p-6 shadow-card">
      <div className="flex flex-wrap items-center gap-3">
        {(['same-stage', 'final'] as const).map((key) => (
          <button
            key={key}
            type="button"
            onClick={() => setView(key)}
            className={`rounded-md px-3 py-2 text-sm font-semibold ${view === key ? 'bg-hud-accent text-white' : 'bg-well text-ink-faint'}`}
          >
            {key === 'same-stage' ? 'Same-Month' : 'Final'}
          </button>
        ))}
        {view === 'same-stage' && (
          <label className="ml-auto text-sm text-ink-dim">
            <span className="sr-only">Month</span>
            <select
              aria-label="Month"
              value={stage}
              onChange={(event) => setStage(Number(event.target.value))}
              className="rounded-md border border-line-strong bg-white px-2 py-1"
            >
              {Array.from({ length: 12 }, (_, index) => index + 1).map((month) => (
                <option key={month} value={month}>Month {month}</option>
              ))}
            </select>
          </label>
        )}
      </div>

      {loading && <p className="mt-6 text-sm" aria-live="polite">Loading leaderboard…</p>}
      {!loading && error && (
        <div className="mt-6">
          <p className="text-sm text-red-800" role="alert">{error}</p>
          <button type="button" onClick={() => setRequestVersion((value) => value + 1)} className="mt-3 text-sm font-semibold text-hud-accent">Retry</button>
        </div>
      )}
      {!loading && !error && data && (
        data.items.length === 0 ? (
          <p className="mt-6 text-sm text-ink-faint">No eligible students have completed this month yet.</p>
        ) : (
          <div className="mt-6 overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="border-b border-line text-left text-ink-faint">
                <th className="px-4 py-3 font-medium">Rank</th>
                <th className="px-4 py-3 font-medium">Nickname</th>
                <th className="px-4 py-3 font-medium">Current Progress</th>
                <th className="px-4 py-3 font-medium">
                  {view === 'final' ? 'Total Revenue (12 Months)' : `Revenue through Month ${data.stage}`}
                </th>
                <th className="px-4 py-3 font-medium">Last Activity</th>
              </tr></thead>
              <tbody>{data.items.map((entry) => (
                <tr key={`${entry.rank}-${entry.nickname}`} className="border-b border-line last:border-0">
                  <td className="px-4 py-3 font-mono">{entry.rank}</td>
                  <td className="px-4 py-3 font-medium">{entry.nickname}</td>
                  <td className="px-4 py-3 font-mono">{entry.completed_months}/12</td>
                  <td className="px-4 py-3 font-mono">{formatRevenue(entry.cumulative_revenue)}</td>
                  <td className="px-4 py-3">{formatTimestamp(entry.last_activity)}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        )
      )}
    </section>
  )
}
