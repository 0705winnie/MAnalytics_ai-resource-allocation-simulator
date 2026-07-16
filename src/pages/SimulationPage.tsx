import { useState, type ReactNode } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer, Cell,
} from 'recharts'
import { postSimulateMonth } from '../lib/api'
import { createSubmission } from '../lib/storage'
import type {
  MonthDetailResult,
  PolicyParams,
  SimulationMonthResult,
  SimulationResponse,
  SimulationTypeResult,
} from '../types/simulation'
import type { Submission } from '../types/user'
import type { Page } from '../components/NavBar'

// ── Constants ────────────────────────────────────────────────────────────────

const MONTH_LABELS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
const TOTAL_MONTHS = 12

const TYPE_COLORS: Record<string, string> = { VIP: '#60a5fa', standard: '#a3e635', economy: '#9ca3af' }

const TOOLTIP = {
  contentStyle: {
    backgroundColor: '#0f172a',
    border: '1px solid #1f2937',
    borderRadius: '6px',
    fontSize: '12px',
  },
  labelStyle: { color: '#d1d5db', marginBottom: 4 },
  itemStyle:  { color: '#9ca3af' },
}

// Compact axis ticks ($60k) vs. exact tooltip values ($60,000) — same pattern
// used for the dollar-prefixed stat tiles above these charts.
function formatCurrencyTick(value: number): string {
  if (value === 0) return '$0'
  return `$${Math.round(value / 1000)}k`
}

function formatCurrencyExact(value: number): string {
  return `$${value.toLocaleString()}`
}

// Strips a MonthDetailResult down to the plain SimulationMonthResult shape
// (drops by_type/warnings/remaining_capacity, which the annual charts don't
// need and which SimulationResponse.monthly never carried).
function toMonthlySummary(m: MonthDetailResult): SimulationMonthResult {
  return {
    month: m.month,
    total_requests: m.total_requests,
    admitted_requests: m.admitted_requests,
    completed_requests: m.completed_requests,
    rejected_requests: m.rejected_requests,
    total_revenue: m.total_revenue,
    unfinished_requests: m.unfinished_requests,
    unfinished_value: m.unfinished_value,
    avg_utilization: m.avg_utilization,
    peak_utilization: m.peak_utilization,
  }
}

// Builds the same shape /simulate used to return in one shot, but from
// accumulated /simulate/month results — this is what feeds the annual
// charts and "Save to My History" (Submission extends SimulationResponse,
// and Page 4 reads it unmodified regardless of whether the session is
// partial or all 12 months are done).
function aggregateMonths(months: MonthDetailResult[]): SimulationResponse {
  const typeTotals = new Map<string, SimulationTypeResult>()
  for (const m of months) {
    for (const t of m.by_type) {
      const existing = typeTotals.get(t.type)
      typeTotals.set(t.type, {
        type: t.type,
        total_requests: (existing?.total_requests ?? 0) + t.total_requests,
        admitted_requests: (existing?.admitted_requests ?? 0) + t.admitted_requests,
        completed_requests: (existing?.completed_requests ?? 0) + t.completed_requests,
        total_revenue: (existing?.total_revenue ?? 0) + t.total_revenue,
      })
    }
  }

  return {
    monthly: months.map(toMonthlySummary),
    by_type: Array.from(typeTotals.values()),
    total_revenue: months.reduce((s, m) => s + m.total_revenue, 0),
    total_unfinished_requests: months.reduce((s, m) => s + m.unfinished_requests, 0),
    total_unfinished_value: months.reduce((s, m) => s + m.unfinished_value, 0),
    warnings: months.flatMap((m) => m.warnings),
  }
}

// Minimal runtime shape check on top of the TS type (which is erased at
// runtime) — guards against a malformed/truncated response before the UI
// trusts it as this month's result.
function isValidMonthDetailResult(value: unknown): value is MonthDetailResult {
  if (!value || typeof value !== 'object') return false
  const v = value as Record<string, unknown>
  return (
    typeof v.month === 'number' &&
    typeof v.total_requests === 'number' &&
    typeof v.admitted_requests === 'number' &&
    typeof v.rejected_requests === 'number' &&
    typeof v.completed_requests === 'number' &&
    typeof v.total_revenue === 'number' &&
    typeof v.unfinished_requests === 'number' &&
    Array.isArray(v.warnings) &&
    Array.isArray(v.by_type) &&
    typeof v.avg_utilization === 'object' &&
    typeof v.peak_utilization === 'object' &&
    typeof v.remaining_capacity === 'object'
  )
}

// ── Sub-components ───────────────────────────────────────────────────────────

function SectionCard({
  title,
  label,
  children,
}: {
  title: string
  label?: string
  children: ReactNode
}) {
  return (
    <div className="rounded-lg border border-gray-800 bg-gray-900 p-6">
      <div className="flex items-center gap-3 mb-5">
        {label && (
          <span className="text-xs font-mono px-2 py-0.5 rounded bg-gray-800 text-gray-600 shrink-0">
            {label}
          </span>
        )}
        <h2 className="text-xs font-semibold uppercase tracking-widest text-gray-500">
          {title}
        </h2>
      </div>
      {children}
    </div>
  )
}

function ChartInsight({ children }: { children: ReactNode }) {
  return (
    <div className="mb-5 px-3 py-2.5 rounded border-l-2 border-hud-accent bg-blue-950/20 text-sm text-gray-400 leading-relaxed">
      <span className="text-hud-accent font-semibold text-xs uppercase tracking-wider mr-2">
        What to notice
      </span>
      {children}
    </div>
  )
}

function StatTile({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className="rounded-lg border border-gray-800 bg-gray-950 px-4 py-3">
      <div className="text-xs text-gray-600 mb-1">{label}</div>
      <div className={`font-mono font-semibold text-sm ${accent ? 'text-hud-accent' : 'text-gray-200'}`}>
        {value}
      </div>
    </div>
  )
}

function MonthStepper({
  completedCount,
  highlightedMonth,
  onSelectMonth,
}: {
  completedCount: number
  highlightedMonth: number | null
  onSelectMonth: (month: number) => void
}) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {MONTH_LABELS.map((label, i) => {
        const month = i + 1
        const isCompleted = month <= completedCount
        const isCurrent = month === completedCount + 1
        const isHighlighted = month === highlightedMonth

        return (
          <button
            key={month}
            type="button"
            disabled={!isCompleted}
            onClick={() => onSelectMonth(month)}
            title={
              isCompleted
                ? `View Month ${month} (${label}) results`
                : isCurrent
                  ? `Month ${month} (${label}) — up next`
                  : `Month ${month} (${label}) — locked until Month ${month - 1} is run`
            }
            className={[
              'flex-1 min-w-[52px] rounded border px-2 py-2 text-center transition-colors',
              isCompleted
                ? isHighlighted
                  ? 'border-hud-accent bg-blue-950/40 text-hud-accent cursor-pointer'
                  : 'border-lime-800/50 bg-lime-950/20 text-lime-400 hover:border-lime-600/70 cursor-pointer'
                : isCurrent
                  ? 'border-hud-accent/50 bg-blue-950/20 text-hud-accent cursor-default'
                  : 'border-gray-800 bg-gray-950 text-gray-700 cursor-not-allowed',
            ].join(' ')}
          >
            <div className="text-[10px] uppercase tracking-wide">{label}</div>
            <div className="text-xs font-mono mt-0.5">
              {isCompleted ? '✓' : isCurrent ? '●' : '○'}
            </div>
          </button>
        )
      })}
    </div>
  )
}

// ── Page ─────────────────────────────────────────────────────────────────────

interface Props {
  policyCode: string
  policyParams: PolicyParams
  completedMonths: MonthDetailResult[]
  onMonthCompleted: (result: MonthDetailResult) => void
  onResetSession: () => void
  onSaveSubmission: (submission: Submission) => void
  onNavigate: (page: Page) => void
}

export default function SimulationPage({
  policyCode,
  policyParams,
  completedMonths,
  onMonthCompleted,
  onResetSession,
  onSaveSubmission,
  onNavigate,
}: Props) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [justSaved, setJustSaved] = useState(false)
  const [highlightedMonth, setHighlightedMonth] = useState<number | null>(null)

  const hasSignature = policyCode.includes('def admission_policy(')
  const paramEntries = Object.entries(policyParams)

  const nextMonth = completedMonths.length < TOTAL_MONTHS ? completedMonths.length + 1 : null
  const sessionComplete = nextMonth === null
  const latestMonth = completedMonths.length > 0 ? completedMonths[completedMonths.length - 1] : null
  const shownMonth = highlightedMonth !== null
    ? (completedMonths.find((m) => m.month === highlightedMonth) ?? latestMonth)
    : latestMonth

  async function runMonth() {
    // Guards against duplicate/overlapping run attempts and against ever
    // requesting anything but the next sequential month.
    if (loading || nextMonth === null || !hasSignature) return

    setLoading(true)
    setError(null)
    try {
      const res = await postSimulateMonth({
        month: nextMonth,
        policy_code: policyCode,
        params: policyParams,
        previous_months: completedMonths,
      })

      if (!isValidMonthDetailResult(res) || res.month !== nextMonth) {
        throw new Error('The simulator returned an unexpected response. Please try again.')
      }

      onMonthCompleted(res)
      setHighlightedMonth(res.month)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Simulation failed')
    } finally {
      setLoading(false)
    }
  }

  function resetSession() {
    if (completedMonths.length === 0) return
    const confirmed = window.confirm(
      `This will discard all ${completedMonths.length} completed month${completedMonths.length === 1 ? '' : 's'} ` +
      `and restart the simulation from Month 1. Your policy code and parameters won't be affected. Continue?`
    )
    if (!confirmed) return
    onResetSession()
    setHighlightedMonth(null)
    setError(null)
  }

  function saveToHistory() {
    if (completedMonths.length === 0) return
    onSaveSubmission(createSubmission(policyCode, policyParams, aggregateMonths(completedMonths)))
    setJustSaved(true)
    setTimeout(() => setJustSaved(false), 2000)
  }

  const aggregated = completedMonths.length > 0 ? aggregateMonths(completedMonths) : null

  const revenueData = completedMonths.map((m) => ({ month: m.month, Revenue: m.total_revenue }))

  const admitVsRejectData = completedMonths.map((m) => ({
    month: m.month,
    Admitted: m.admitted_requests,
    Rejected: m.rejected_requests,
  }))

  const byTypeData = aggregated?.by_type.map((t) => ({
    type: t.type === 'VIP' ? 'VIP' : t.type.charAt(0).toUpperCase() + t.type.slice(1),
    Revenue: t.total_revenue,
    fill: TYPE_COLORS[t.type] ?? '#6b7280',
  }))

  // Cluster utilization across completed months so far: mean of monthly
  // averages, max of monthly peaks. Cluster ids come back as string object keys.
  const clusterIds = completedMonths.length > 0 ? Object.keys(completedMonths[0].avg_utilization) : []
  const utilizationData = clusterIds.map((cid) => {
    const avgVals = completedMonths.map((m) => m.avg_utilization[cid] ?? 0)
    const peakVals = completedMonths.map((m) => m.peak_utilization[cid] ?? 0)
    const avgPct = (avgVals.reduce((s, v) => s + v, 0) / avgVals.length) * 100
    const peakPct = Math.max(...peakVals) * 100
    return {
      cluster: `Cluster ${cid}`,
      Avg: Math.round(avgPct * 10) / 10,
      Peak: Math.round(peakPct * 10) / 10,
    }
  })

  const utilizationSpread = utilizationData.length > 0
    ? Math.max(...utilizationData.map((d) => d.Avg)) - Math.min(...utilizationData.map((d) => d.Avg))
    : 0

  return (
    <div className="space-y-8">

      {/* ── Hero ───────────────────────────────────────────────────────── */}
      <div className="rounded-xl border border-gray-800 bg-gradient-to-br from-gray-900 via-gray-900 to-blue-950/20 p-8">
        <div className="flex items-center gap-2 mb-5">
          <span className="text-xs font-mono px-2.5 py-1 rounded-full border border-gray-700 text-gray-500 tracking-widest uppercase">
            03  Simulation
          </span>
        </div>
        <h1 className="text-2xl font-bold text-gray-100 tracking-tight mb-3">
          Run Your Policy Month by Month
        </h1>
        <p className="text-gray-400 leading-relaxed max-w-3xl">
          Each click of <strong className="text-gray-300">Run Month</strong> tests your current{' '}
          <span className="text-hud-accent font-medium">admission_policy</span> against that month's arrivals,
          with real capacity and departure dynamics — a job only earns revenue if it's admitted{' '}
          <em>and</em> completes before month-end. Revise your code on{' '}
          <strong className="text-gray-300">02 Policy &amp; AI</strong> between months; completed months are
          locked and can't be rerun.
        </p>
      </div>

      {/* ── Month stepper ─────────────────────────────────────────────── */}
      <SectionCard title="Progress" label="Months">
        <MonthStepper
          completedCount={completedMonths.length}
          highlightedMonth={highlightedMonth}
          onSelectMonth={setHighlightedMonth}
        />
      </SectionCard>

      {/* ── Current policy snapshot + run control ────────────────────────── */}
      <SectionCard title="Policy Under Test" label="Snapshot">
        <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded border ${
                hasSignature
                  ? 'border-lime-800/50 bg-lime-950/30 text-lime-400'
                  : 'border-amber-800/40 bg-amber-950/20 text-amber-500'
              }`}
            >
              {hasSignature ? '✓' : '!'} admission_policy defined
            </span>
            {paramEntries.length > 0 ? (
              paramEntries.map(([k, v]) => (
                <span
                  key={k}
                  className="text-xs font-mono px-2 py-0.5 rounded bg-gray-800 text-gray-400"
                >
                  {k}={v}
                </span>
              ))
            ) : (
              <span className="text-xs text-gray-700 italic">no parameters set</span>
            )}
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <button
              onClick={() => onNavigate(2)}
              className="rounded border border-gray-700 px-4 py-2 text-xs font-medium text-gray-400 hover:border-gray-500 hover:text-gray-200 transition-colors"
            >
              Revise Policy Before Next Month
            </button>
            <button
              onClick={runMonth}
              disabled={loading || sessionComplete || !hasSignature}
              className="rounded border border-hud-accent/30 bg-blue-950/30 px-5 py-2 text-xs font-medium text-hud-accent hover:bg-blue-950/50 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              {loading
                ? 'Running…'
                : sessionComplete
                  ? 'All 12 Months Complete'
                  : `Run Month ${nextMonth} (${MONTH_LABELS[nextMonth! - 1]})`}
            </button>
          </div>
        </div>
        <pre className="bg-gray-950 border border-gray-800 rounded p-3 text-xs font-mono text-gray-500 overflow-x-auto leading-relaxed max-h-32">
          {policyCode}
        </pre>
        {error && (
          <div className="mt-3 rounded border border-red-900/40 bg-red-950/20 px-3 py-2.5 text-xs text-red-400 leading-relaxed">
            <strong>Error:</strong> {error}
            <br />
            <span className="text-red-600">
              Is the backend running?{' '}
              <code className="text-red-500">cd backend &amp;&amp; uvicorn app.main:app --reload</code>
            </span>
          </div>
        )}
      </SectionCard>

      {/* ── Empty state ───────────────────────────────────────────────────── */}
      {completedMonths.length === 0 && !loading && (
        <div className="rounded-lg border border-dashed border-gray-800 bg-gray-900/40 p-10 text-center">
          <p className="text-gray-600 text-sm">
            No months run yet. Click <strong className="text-gray-400">Run Month 1</strong> above
            to see how your policy performs.
          </p>
        </div>
      )}

      {/* ── Session-complete summary ─────────────────────────────────────── */}
      {sessionComplete && aggregated && (
        <div className="rounded-xl border border-hud-positive/30 bg-gradient-to-r from-lime-950/20 to-gray-900 p-6">
          <span className="text-xs font-mono uppercase tracking-widest text-hud-positive mb-2 block">
            Session Complete
          </span>
          <h3 className="text-gray-100 font-semibold text-base mb-1.5">
            All 12 months finished — total revenue ${aggregated.total_revenue.toLocaleString()}
          </h3>
          <p className="text-gray-500 text-sm max-w-2xl">
            Save this run to your personal history on <strong className="text-gray-300">04 History</strong>,
            or reset the session below to try a different policy from Month 1.
          </p>
        </div>
      )}

      {/* ── Latest / selected month detail ───────────────────────────────── */}
      {shownMonth && (
        <SectionCard
          title={`Month ${shownMonth.month} Results (${MONTH_LABELS[shownMonth.month - 1]})`}
          label="Monthly"
        >
          {shownMonth.warnings.length > 0 && (
            <div className="mb-4 rounded border border-amber-800/40 bg-amber-950/20 px-4 py-3 text-xs text-amber-500 leading-relaxed">
              <strong>{shownMonth.warnings.length} warning{shownMonth.warnings.length === 1 ? '' : 's'}</strong> during
              this month (e.g. invalid or infeasible cluster choices were auto-rejected):
              <ul className="mt-1.5 list-disc list-inside space-y-0.5 text-amber-500/80">
                {shownMonth.warnings.slice(0, 5).map((w, i) => <li key={i}>{w}</li>)}
              </ul>
              {shownMonth.warnings.length > 5 && (
                <p className="mt-1 text-amber-600">…and {shownMonth.warnings.length - 5} more.</p>
              )}
            </div>
          )}

          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mb-5">
            <StatTile label="Revenue" value={`$${shownMonth.total_revenue.toLocaleString()}`} accent />
            <StatTile label="Arrivals" value={shownMonth.total_requests.toLocaleString()} />
            <StatTile label="Admitted" value={shownMonth.admitted_requests.toLocaleString()} />
            <StatTile label="Rejected" value={shownMonth.rejected_requests.toLocaleString()} />
            <StatTile label="Completed" value={shownMonth.completed_requests.toLocaleString()} />
            <StatTile label="Unfinished" value={shownMonth.unfinished_requests.toLocaleString()} />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <div className="text-xs text-gray-600 mb-2 uppercase tracking-wide">Revenue by Type</div>
              <div className="space-y-1.5">
                {shownMonth.by_type.map((t) => (
                  <div key={t.type} className="flex items-center justify-between text-xs">
                    <span className="text-gray-400 capitalize">{t.type}</span>
                    <span className="font-mono text-gray-300">${t.total_revenue.toLocaleString()}</span>
                  </div>
                ))}
              </div>
            </div>
            <div>
              <div className="text-xs text-gray-600 mb-2 uppercase tracking-wide">Remaining Capacity (Month End)</div>
              <div className="space-y-1.5">
                {Object.entries(shownMonth.remaining_capacity).map(([cid, free]) => (
                  <div key={cid} className="flex items-center justify-between text-xs">
                    <span className="text-gray-400">Cluster {cid}</span>
                    <span className="font-mono text-gray-300">{free} units free</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </SectionCard>
      )}

      {/* ── Cumulative results ───────────────────────────────────────────── */}
      {aggregated && (
        <>
          <div className="flex items-center justify-between gap-4">
            <p className="text-gray-600 text-xs">
              Save this run to your personal history on <strong className="text-gray-400">04 History</strong>.
            </p>
            <button
              onClick={saveToHistory}
              className="shrink-0 rounded border border-hud-positive/30 bg-lime-950/20 px-4 py-1.5 text-xs font-medium text-hud-positive hover:bg-lime-950/40 transition-colors"
            >
              {justSaved ? 'Saved ✓' : 'Save to My History'}
            </button>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            <StatTile
              label={`Total Revenue (${completedMonths.length}/${TOTAL_MONTHS} mo.)`}
              value={`$${aggregated.total_revenue.toLocaleString()}`}
              accent
            />
            <StatTile
              label="Total Requests"
              value={aggregated.monthly.reduce((s, m) => s + m.total_requests, 0).toLocaleString()}
            />
            <StatTile
              label="Admitted"
              value={aggregated.monthly.reduce((s, m) => s + m.admitted_requests, 0).toLocaleString()}
            />
            <StatTile
              label="Completed"
              value={aggregated.monthly.reduce((s, m) => s + m.completed_requests, 0).toLocaleString()}
            />
            <StatTile
              label="Unfinished"
              value={aggregated.total_unfinished_requests.toLocaleString()}
            />
            <StatTile
              label="Unfinished Value"
              value={`$${aggregated.total_unfinished_value.toLocaleString()}`}
            />
          </div>

          <SectionCard title="Monthly Revenue" label="01">
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={revenueData} margin={{ top: 4, right: 8, left: -10, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" vertical={false} />
                <XAxis
                  dataKey="month"
                  tickFormatter={(m: number) => MONTH_LABELS[m - 1]}
                  tick={{ fill: '#6b7280', fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fill: '#6b7280', fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                  tickFormatter={formatCurrencyTick}
                />
                <Tooltip
                  {...TOOLTIP}
                  labelFormatter={(m: number) => MONTH_LABELS[m - 1]}
                  formatter={formatCurrencyExact}
                />
                <Bar dataKey="Revenue" fill="#60a5fa" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </SectionCard>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
            <SectionCard title="Admitted vs. Rejected by Month" label="02">
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={admitVsRejectData} margin={{ top: 4, right: 8, left: -10, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" vertical={false} />
                  <XAxis
                    dataKey="month"
                    tickFormatter={(m: number) => MONTH_LABELS[m - 1]}
                    tick={{ fill: '#6b7280', fontSize: 11 }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis tick={{ fill: '#6b7280', fontSize: 11 }} axisLine={false} tickLine={false} />
                  <Tooltip {...TOOLTIP} labelFormatter={(m: number) => MONTH_LABELS[m - 1]} />
                  <Legend wrapperStyle={{ fontSize: '12px', paddingTop: '10px', color: '#9ca3af' }} />
                  <Bar dataKey="Admitted" fill="#a3e635" radius={[2, 2, 0, 0]} />
                  <Bar dataKey="Rejected" fill="#f87171" radius={[2, 2, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </SectionCard>

            <SectionCard title="Revenue by Request Type" label="03">
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={byTypeData} margin={{ top: 4, right: 8, left: -10, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" vertical={false} />
                  <XAxis dataKey="type" tick={{ fill: '#6b7280', fontSize: 11 }} axisLine={false} tickLine={false} />
                  <YAxis
                    tick={{ fill: '#6b7280', fontSize: 11 }}
                    axisLine={false}
                    tickLine={false}
                    tickFormatter={formatCurrencyTick}
                  />
                  <Tooltip {...TOOLTIP} formatter={formatCurrencyExact} />
                  <Bar dataKey="Revenue" radius={[3, 3, 0, 0]}>
                    {byTypeData?.map((entry, i) => <Cell key={i} fill={entry.fill} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </SectionCard>
          </div>

          <SectionCard title={`Capacity Utilization by Cluster (${completedMonths.length} mo. so far)`} label="04">
            {utilizationSpread > 15 && (
              <ChartInsight>
                Utilization is uneven across clusters — a large gap usually means your
                policy consistently favors one cluster over the others (e.g. a first-fit
                rule always tries the lowest-numbered cluster first). Try routing to the
                least-loaded cluster to compare how evenly load spreads.
              </ChartInsight>
            )}
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={utilizationData} margin={{ top: 4, right: 8, left: -10, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" vertical={false} />
                <XAxis dataKey="cluster" tick={{ fill: '#6b7280', fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis
                  tick={{ fill: '#6b7280', fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                  tickFormatter={(v: number) => `${v}%`}
                />
                <Tooltip {...TOOLTIP} formatter={(v: number) => `${v}%`} />
                <Legend wrapperStyle={{ fontSize: '12px', paddingTop: '10px', color: '#9ca3af' }} />
                <Bar dataKey="Avg" fill="#60a5fa" radius={[2, 2, 0, 0]} />
                <Bar dataKey="Peak" fill="#a3e635" radius={[2, 2, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </SectionCard>

          <SectionCard title="Past Monthly Results" label="05">
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-left text-gray-600 border-b border-gray-800">
                    <th className="py-2 pr-4 font-medium">Month</th>
                    <th className="py-2 pr-4 font-medium">Arrivals</th>
                    <th className="py-2 pr-4 font-medium">Admitted</th>
                    <th className="py-2 pr-4 font-medium">Rejected</th>
                    <th className="py-2 pr-4 font-medium">Completed</th>
                    <th className="py-2 pr-4 font-medium">Unfinished</th>
                    <th className="py-2 pr-4 font-medium">Revenue</th>
                    <th className="py-2 pr-4 font-medium">Warnings</th>
                  </tr>
                </thead>
                <tbody className="font-mono text-gray-400">
                  {completedMonths.map((m) => (
                    <tr
                      key={m.month}
                      onClick={() => setHighlightedMonth(m.month)}
                      className={`border-b border-gray-900 cursor-pointer hover:bg-gray-800/40 ${
                        m.month === highlightedMonth ? 'bg-blue-950/30' : ''
                      }`}
                    >
                      <td className="py-2 pr-4 text-gray-300">{MONTH_LABELS[m.month - 1]}</td>
                      <td className="py-2 pr-4">{m.total_requests}</td>
                      <td className="py-2 pr-4">{m.admitted_requests}</td>
                      <td className="py-2 pr-4">{m.rejected_requests}</td>
                      <td className="py-2 pr-4">{m.completed_requests}</td>
                      <td className="py-2 pr-4">{m.unfinished_requests}</td>
                      <td className="py-2 pr-4 text-gray-200">${m.total_revenue.toLocaleString()}</td>
                      <td className="py-2 pr-4">{m.warnings.length > 0 ? m.warnings.length : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </SectionCard>
        </>
      )}

      {/* ── Reset session ─────────────────────────────────────────────────── */}
      {completedMonths.length > 0 && (
        <div className="flex justify-end">
          <button
            onClick={resetSession}
            className="text-xs text-gray-700 hover:text-red-400 border border-gray-800 hover:border-red-900/40 rounded px-3 py-1.5 transition-colors"
          >
            Reset Session (discard all months)
          </button>
        </div>
      )}

    </div>
  )
}
