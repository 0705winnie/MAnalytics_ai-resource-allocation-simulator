import { useEffect, useState, type ReactNode } from 'react'
import { getFinalLeaderboard, getSameStageLeaderboard } from '../lib/api'
import type { LeaderboardResponse, OfficialMonthlyResult, OfficialSimulationSession } from '../types/simulation'

type HistoryView = 'history' | 'same-stage' | 'final'

function SectionCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="rounded-lg border border-line bg-white p-6 shadow-card">
      <h2 className="mb-5 text-xs font-semibold uppercase tracking-widest text-ink-faint">
        {title}
      </h2>
      {children}
    </div>
  )
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

function formatMoney(value: number): string {
  return `$${value.toLocaleString()}`
}

function PolicySnapshot({ result }: { result: OfficialMonthlyResult }) {
  return (
    <details className="mt-4 rounded border border-line bg-well/60 p-3">
      <summary className="cursor-pointer text-xs font-semibold text-hud-accent">
        View Policy Used
      </summary>
      <div className="mt-3 space-y-3">
        <pre className="max-h-72 overflow-auto whitespace-pre-wrap rounded border border-line bg-white p-3 font-mono text-xs text-ink-dim">
          {result.policy_code}
        </pre>
        <div>
          <p className="mb-1 text-xs text-ink-faint">Parameters</p>
          <pre className="overflow-auto rounded border border-line bg-white p-3 font-mono text-xs text-ink-dim">
            {JSON.stringify(result.params, null, 2)}
          </pre>
        </div>
      </div>
    </details>
  )
}

function UtilizationValues({ values }: { values: Record<string, number> }) {
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1 font-mono text-xs text-ink-dim">
      {Object.entries(values).map(([key, value]) => (
        <span key={key}>Cluster {key}: {Math.round(value * 100)}%</span>
      ))}
    </div>
  )
}

function MonthHistoryItem({
  result,
  policyStatus,
}: {
  result: OfficialMonthlyResult
  policyStatus: string
}) {
  const summaryFields = [
    ['Completed at', formatDate(result.completed_at)],
    ['Revenue', formatMoney(result.total_revenue)],
    ['Requests', result.total_requests],
    ['Admitted', result.admitted_requests],
    ['Rejected', result.rejected_requests],
    ['Completed', result.completed_requests],
    ['Unfinished', result.unfinished_requests],
    ['Warnings', result.warnings.length],
    ['Policy', policyStatus],
  ]

  return (
    <details className="group rounded-lg border border-line bg-white shadow-sm">
      <summary className="cursor-pointer list-none p-4 focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-hud-accent/40 sm:p-5 [&::-webkit-details-marker]:hidden">
        <div className="flex items-center justify-between gap-4">
          <h3 className="text-base font-semibold text-ink">Month {result.month}</h3>
          <span className="shrink-0 text-xs font-semibold text-hud-accent">
            <span className="group-open:hidden">Show details</span>
            <span className="hidden group-open:inline">Hide details</span>
            <span aria-hidden="true" className="ml-1 inline-block transition-transform group-open:rotate-180">⌄</span>
          </span>
        </div>
        <dl className="mt-4 grid grid-cols-2 gap-x-5 gap-y-4 sm:grid-cols-3 lg:grid-cols-5">
          {summaryFields.map(([label, value]) => (
            <div key={label} className="min-w-0">
              <dt className="text-[11px] font-semibold uppercase tracking-wide text-ink-faint">{label}</dt>
              <dd className={`mt-1 truncate text-xs text-ink-dim ${label === 'Completed at' || label === 'Policy' ? 'font-sans' : 'font-mono'} ${label === 'Revenue' ? 'font-semibold text-ink' : ''}`}>
                {value}
              </dd>
            </div>
          ))}
        </dl>
      </summary>

      <div className="space-y-6 border-t border-line px-4 py-5 sm:px-5">
        <section aria-labelledby={`month-${result.month}-by-type`}>
          <h4 id={`month-${result.month}-by-type`} className="mb-3 text-xs font-semibold uppercase tracking-wide text-ink-faint">By type</h4>
          <div className="space-y-2 text-sm text-ink-dim">
            {result.by_type.map((row) => (
              <p key={row.type}>
                <span className="font-medium capitalize text-ink">{row.type}:</span>{' '}
                <span className="font-mono">{formatMoney(row.total_revenue)}</span>
              </p>
            ))}
          </div>
        </section>

        <section className="border-t border-line pt-5" aria-labelledby={`month-${result.month}-utilization`}>
          <h4 id={`month-${result.month}-utilization`} className="mb-3 text-xs font-semibold uppercase tracking-wide text-ink-faint">Utilization</h4>
          <div className="space-y-4 rounded-md bg-well/60 p-4">
            <div>
              <p className="mb-1.5 text-xs font-semibold text-ink">Average</p>
              <UtilizationValues values={result.avg_utilization} />
            </div>
            <div>
              <p className="mb-1.5 text-xs font-semibold text-ink">Peak</p>
              <UtilizationValues values={result.peak_utilization} />
            </div>
          </div>
        </section>

        <section className="border-t border-line pt-5" aria-labelledby={`month-${result.month}-warnings`}>
          <h4 id={`month-${result.month}-warnings`} className="mb-3 text-xs font-semibold uppercase tracking-wide text-ink-faint">Warnings</h4>
          {result.warnings.length === 0 ? (
            <p className="text-xs text-ink-faint">None</p>
          ) : (
            <ul className="list-disc space-y-1 pl-4 text-xs text-amber-700">
              {result.warnings.map((warning, index) => <li key={`${index}-${warning}`}>{warning}</li>)}
            </ul>
          )}
        </section>
      </div>
      <div className="px-4 pb-5 sm:px-5">
        <PolicySnapshot result={result} />
      </div>
    </details>
  )
}

function Leaderboard({ kind }: { kind: 'same-stage' | 'final' }) {
  const [data, setData] = useState<LeaderboardResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [requestVersion, setRequestVersion] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    setError(null)
    const request = kind === 'same-stage'
      ? getSameStageLeaderboard(controller.signal)
      : getFinalLeaderboard(controller.signal)
    request
      .then(setData)
      .catch((requestError: unknown) => {
        if (controller.signal.aborted) return
        setData(null)
        setError(requestError instanceof Error ? requestError.message : 'Leaderboard is temporarily unavailable.')
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    return () => controller.abort()
  }, [kind, requestVersion])

  return (
    <SectionCard title={`${kind === 'same-stage' ? 'Same-Month' : 'Final'} Leaderboard`}>
      {loading && <p className="text-sm" aria-live="polite">Loading leaderboard…</p>}
      {!loading && error && (
        <div>
          <p className="text-sm text-red-800" role="alert">{error}</p>
          <button type="button" onClick={() => setRequestVersion((value) => value + 1)} className="mt-3 text-sm font-semibold text-hud-accent">Retry</button>
        </div>
      )}
      {!loading && !error && data && (
        <>
          {kind === 'same-stage' && data.stage === 0 && (
            <p className="text-sm text-ink-faint">Complete Month 1 to join and view a same-month ranking.</p>
          )}
          {kind === 'final' && data.current_user_eligible === false && (
            <p className="mb-4 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
              You can view the final ranking, but you will join it only after completing all 12 months.
            </p>
          )}
          {data.stage > 0 && data.items.length === 0 && (
            <p className="text-sm text-ink-faint">No eligible students have completed this month yet.</p>
          )}
          {data.items.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead><tr className="border-b border-line text-left text-ink-faint">
                  <th className="py-3 pr-4 font-medium">Rank</th>
                  <th className="py-3 pr-4 font-medium">Nickname</th>
                  <th className="py-3 pr-4 font-medium">Current Progress</th>
                  <th className="py-3 pr-4 font-medium">
                    {kind === 'final' ? 'Total Revenue (12 Months)' : `Revenue through Month ${data.stage}`}
                  </th>
                  <th className="py-3 pr-4 font-medium">Last Activity</th>
                </tr></thead>
                <tbody>{data.items.map((entry) => (
                  <tr key={`${entry.rank}-${entry.nickname}`} className={entry.is_current_user ? 'border-b border-line bg-hud-accent/6' : 'border-b border-line'}>
                    <td className="py-3 pr-4 font-mono">{entry.rank}</td>
                    <td className="py-3 pr-4 font-medium">{entry.nickname}{entry.is_current_user ? ' (you)' : ''}</td>
                    <td className="py-3 pr-4 font-mono">{entry.completed_months}/12</td>
                    <td className="py-3 pr-4 font-mono">{formatMoney(entry.cumulative_revenue)}</td>
                    <td className="py-3 pr-4">{entry.last_activity ? formatDate(entry.last_activity) : '—'}</td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
          )}
        </>
      )}
    </SectionCard>
  )
}

interface Props {
  nickname: string
  session: OfficialSimulationSession
}

export default function LeaderboardPage({ nickname, session }: Props) {
  const [view, setView] = useState<HistoryView>('history')
  const results = [...session.monthly_results].sort((a, b) => a.month - b.month)

  return (
    <div className="space-y-8">
      <div className="rounded-xl border border-line bg-gradient-to-br from-white via-white to-hud-accent/6 p-8 shadow-card">
        <span className="mb-5 inline-block rounded-full border border-line-strong px-2.5 py-1 font-mono text-xs uppercase tracking-widest text-ink-faint">
          04 History &amp; Leaderboards
        </span>
        <h1 className="mb-3 text-2xl font-bold tracking-tight text-ink">History &amp; Leaderboards</h1>
        <p className="max-w-3xl text-sm leading-relaxed text-ink-dim">
          <strong>{nickname}</strong>, review the monthly results restored from your official course session
          and compare your progress on the course leaderboards.
        </p>
      </div>

      <div className="flex flex-wrap gap-2" role="tablist" aria-label="History and leaderboard views">
        {([
          ['history', 'Simulation History'],
          ['same-stage', 'Same-Month Leaderboard'],
          ['final', 'Final Leaderboard'],
        ] as const).map(([key, label]) => (
          <button
            key={key}
            type="button"
            role="tab"
            aria-selected={view === key}
            onClick={() => setView(key)}
            className={`rounded border px-4 py-2 text-xs font-semibold transition-colors ${
              view === key
                ? 'border-hud-accent bg-hud-accent/8 text-hud-accent'
                : 'border-line-strong bg-white text-ink-faint hover:text-ink'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {view === 'same-stage' && <Leaderboard kind="same-stage" />}
      {view === 'final' && <Leaderboard kind="final" />}

      {view === 'history' && (
        <SectionCard title={`Persisted monthly results — ${session.completed_months}/12 complete`}>
          {results.length === 0 ? (
            <p className="text-sm text-ink-faint">
              No official months have been completed yet. Run Month 1 on Page 03 to begin.
            </p>
          ) : (
            <div className="space-y-3">
              {results.map((result, index) => {
                const changed = index > 0 && results[index - 1].policy_hash !== result.policy_hash
                return (
                  <MonthHistoryItem
                    key={result.month}
                    result={result}
                    policyStatus={index === 0 ? 'Initial policy' : changed ? 'Changed' : 'Unchanged'}
                  />
                )
              })}
            </div>
          )}
        </SectionCard>
      )}
    </div>
  )
}
