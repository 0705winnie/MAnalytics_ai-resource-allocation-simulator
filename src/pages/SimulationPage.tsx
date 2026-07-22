import { useState, type ReactNode } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer, Cell,
} from 'recharts'
import { postSimulateMonth } from '../lib/api'
import { createSubmission } from '../lib/storage'
import type {
  BenchmarkResult,
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

const TYPE_COLORS: Record<string, string> = { VIP: '#002676', standard: '#2E7D32', economy: '#8598AF' }

const POLICY_LABELS: Record<string, string> = {
  student_policy: 'Your policy',
  always_reject: 'Always reject',
  greedy_first_fit: 'Greedy first-fit',
  least_loaded: 'Least loaded',
  best_fit: 'Best fit',
  vip_priority: 'VIP priority',
  revenue_density: 'Revenue density',
}

const TOOLTIP = {
  contentStyle: {
    backgroundColor: '#FFFFFF',
    border: '1px solid #DCE3EC',
    borderRadius: '6px',
    fontSize: '12px',
  },
  labelStyle: { color: '#0F2247', marginBottom: 4 },
  itemStyle:  { color: '#3E5872' },
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
    benchmark_comparison: aggregateBenchmarkComparison(months),
  }
}

function aggregateBenchmarkComparison(months: MonthDetailResult[]): BenchmarkResult[] {
  const totals = new Map<string, BenchmarkResult>()

  for (const month of months) {
    for (const row of month.benchmark_comparison ?? []) {
      const existing = totals.get(row.policy)
      totals.set(row.policy, {
        policy: row.policy,
        total_revenue: (existing?.total_revenue ?? 0) + row.total_revenue,
        total_unfinished_requests: (existing?.total_unfinished_requests ?? 0) + row.total_unfinished_requests,
        total_unfinished_value: (existing?.total_unfinished_value ?? 0) + row.total_unfinished_value,
        admitted_requests: (existing?.admitted_requests ?? 0) + row.admitted_requests,
        completed_requests: (existing?.completed_requests ?? 0) + row.completed_requests,
        rejected_requests: (existing?.rejected_requests ?? 0) + row.rejected_requests,
        warnings_count: (existing?.warnings_count ?? 0) + row.warnings_count,
      })
    }
  }

  return Array.from(totals.values())
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
    Array.isArray(v.benchmark_comparison) &&
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
    <div className="rounded-lg border border-line bg-white p-6 shadow-card">
      <div className="flex items-center gap-3 mb-5">
        {label && (
          <span className="text-xs font-mono px-2 py-0.5 rounded bg-chip text-ink-faint shrink-0">
            {label}
          </span>
        )}
        <h2 className="text-xs font-semibold uppercase tracking-widest text-ink-faint">
          {title}
        </h2>
      </div>
      {children}
    </div>
  )
}

function ChartInsight({ children }: { children: ReactNode }) {
  return (
    <div className="mb-5 px-3 py-2.5 rounded border-l-2 border-hud-accent bg-hud-accent/6 text-sm text-ink-dim leading-relaxed">
      <span className="text-hud-accent font-semibold text-xs uppercase tracking-wider mr-2">
        What to notice
      </span>
      {children}
    </div>
  )
}

function StatTile({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className="rounded-lg border border-line bg-well px-4 py-3">
      <div className="text-xs text-ink-faint mb-1">{label}</div>
      <div className={`font-mono font-semibold text-sm ${accent ? 'text-hud-accent' : 'text-ink'}`}>
        {value}
      </div>
    </div>
  )
}

function BenchmarkComparisonTable({ rows }: { rows: BenchmarkResult[] }) {
  const sorted = rows.slice().sort((a, b) => b.total_revenue - a.total_revenue)

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="text-left text-ink-faint border-b border-line">
            <th className="py-2 pr-4 font-medium">Policy</th>
            <th className="py-2 pr-4 font-medium">Revenue</th>
            <th className="py-2 pr-4 font-medium">Completed</th>
            <th className="py-2 pr-4 font-medium">Rejected</th>
            <th className="py-2 pr-4 font-medium">Unfinished</th>
            <th className="py-2 pr-4 font-medium">Unfinished Value</th>
            <th className="py-2 pr-4 font-medium">Warnings</th>
          </tr>
        </thead>
        <tbody className="font-mono text-ink-dim">
          {sorted.map((row) => {
            const isStudent = row.policy === 'student_policy'
            return (
              <tr
                key={row.policy}
                className={`border-b border-line ${isStudent ? 'bg-hud-accent/8 text-ink' : ''}`}
              >
                <td className="py-2 pr-4 font-sans">{POLICY_LABELS[row.policy] ?? row.policy}</td>
                <td className="py-2 pr-4 text-hud-accent">${row.total_revenue.toLocaleString()}</td>
                <td className="py-2 pr-4">{row.completed_requests.toLocaleString()}</td>
                <td className="py-2 pr-4">{row.rejected_requests.toLocaleString()}</td>
                <td className="py-2 pr-4">{row.total_unfinished_requests.toLocaleString()}</td>
                <td className="py-2 pr-4">${row.total_unfinished_value.toLocaleString()}</td>
                <td className="py-2 pr-4">{row.warnings_count}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
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
              'focus:outline-none focus-visible:ring-2 focus-visible:ring-hud-accent/60',
              isCompleted
                ? isHighlighted
                  ? 'border-hud-accent bg-hud-accent/10 text-hud-accent cursor-pointer'
                  : 'border-hud-positive/50 bg-hud-positive/7 text-hud-positive hover:border-hud-positive/70 cursor-pointer'
                : isCurrent
                  ? 'border-hud-accent/50 bg-hud-accent/6 text-hud-accent cursor-default'
                  : 'border-line bg-well text-ink-faintest cursor-not-allowed',
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
    fill: TYPE_COLORS[t.type] ?? '#5B7290',
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
      <div className="rounded-xl border border-line bg-gradient-to-br from-white via-white to-hud-accent/6 p-8 shadow-card">
        <div className="flex items-center gap-2 mb-5">
          <span className="text-xs font-mono px-2.5 py-1 rounded-full border border-line-strong text-ink-faint tracking-widest uppercase">
            03  Simulation
          </span>
        </div>
        <h1 className="text-2xl font-bold text-ink tracking-tight mb-3">
          Run Your Policy Month by Month
        </h1>
        <p className="text-ink-dim leading-relaxed max-w-3xl">
          Each click of <strong className="text-ink-dim">Run Month</strong> tests your current{' '}
          <span className="text-hud-accent font-medium">admission_policy</span> against that month's arrivals,
          with real capacity and departure dynamics — a job only earns revenue if it's admitted{' '}
          <em>and</em> completes before month-end. Revise your code on{' '}
          <strong className="text-ink-dim">02 Policy &amp; AI</strong> between months; completed months are
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
                  ? 'border-hud-positive/50 bg-hud-positive/10 text-hud-positive'
                  : 'border-amber-300 bg-amber-50 text-amber-700'
              }`}
            >
              {hasSignature ? '✓' : '!'} admission_policy defined
            </span>
            {paramEntries.length > 0 ? (
              paramEntries.map(([k, v]) => (
                <span
                  key={k}
                  className="text-xs font-mono px-2 py-0.5 rounded bg-chip text-ink-dim"
                >
                  {k}={v}
                </span>
              ))
            ) : (
              <span className="text-xs text-ink-faintest italic">no parameters set</span>
            )}
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <button
              onClick={() => onNavigate(2)}
              className="rounded border border-line-strong px-4 py-2 text-xs font-medium text-ink-dim hover:border-ink-faintest hover:text-ink focus:outline-none focus-visible:ring-2 focus-visible:ring-ink-faint transition-colors"
            >
              Revise Policy
            </button>
            <button
              onClick={runMonth}
              disabled={loading || sessionComplete || !hasSignature}
              className="rounded border border-hud-gold bg-hud-gold px-5 py-2 text-xs font-semibold text-ink hover:bg-hud-gold-hover hover:border-hud-gold-hover focus:outline-none focus-visible:ring-2 focus-visible:ring-hud-gold/70 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              {loading
                ? 'Running…'
                : sessionComplete
                  ? 'All 12 Months Complete'
                  : `Run Month ${nextMonth} (${MONTH_LABELS[nextMonth! - 1]})`}
            </button>
          </div>
        </div>
        <pre className="bg-well border border-line rounded p-3 text-xs font-mono text-ink-faint overflow-x-auto leading-relaxed max-h-32">
          {policyCode}
        </pre>
        {error && (
          <div className="mt-3 rounded border border-red-200 bg-red-50 px-3 py-2.5 text-xs text-red-600 leading-relaxed">
            <strong>Error:</strong> {error}
            <br />
            <span className="text-red-600">
              Is the backend running?{' '}
              <code className="text-red-600">cd backend &amp;&amp; uvicorn app.main:app --reload</code>
            </span>
          </div>
        )}
      </SectionCard>

      {/* ── Empty state ───────────────────────────────────────────────────── */}
      {completedMonths.length === 0 && !loading && (
        <div className="rounded-lg border border-dashed border-line bg-white/40 p-10 text-center">
          <p className="text-ink-faint text-sm">
            No months run yet. Click <strong className="text-ink-dim">Run Month 1</strong> above
            to see how your policy performs.
          </p>
        </div>
      )}

      {/* ── Session-complete summary ─────────────────────────────────────── */}
      {sessionComplete && aggregated && (
        <div className="rounded-xl border border-hud-positive/30 bg-gradient-to-r from-hud-positive/7 to-white p-6 shadow-card">
          <span className="text-xs font-mono uppercase tracking-widest text-hud-positive mb-2 block">
            Session Complete
          </span>
          <h3 className="text-ink font-semibold text-base mb-1.5">
            All 12 months finished — total revenue ${aggregated.total_revenue.toLocaleString()}
          </h3>
          <p className="text-ink-faint text-sm max-w-2xl">
            Save this run to your personal history on <strong className="text-ink-dim">04 History</strong>,
            or reset the session below to try a different policy from Month 1.
          </p>
        </div>
      )}

      {/* ── Latest / selected month detail ───────────────────────────────── */}
      {shownMonth && (
        <div className="flex items-center gap-3 pt-1">
          <span className="h-px flex-1 bg-chip" />
          <span className="text-xs uppercase tracking-widest text-ink-faint font-semibold shrink-0">
            This Month
          </span>
          <span className="h-px flex-1 bg-chip" />
        </div>
      )}
      {shownMonth && (
        <SectionCard
          title={`Month ${shownMonth.month} Results (${MONTH_LABELS[shownMonth.month - 1]})`}
          label="Monthly"
        >
          {shownMonth.warnings.length > 0 && (
            <div className="mb-4 rounded border border-amber-300 bg-amber-50 px-4 py-3 text-xs text-amber-700 leading-relaxed">
              <strong>{shownMonth.warnings.length} warning{shownMonth.warnings.length === 1 ? '' : 's'}</strong> during
              this month (e.g. invalid or infeasible cluster choices were auto-rejected):
              <ul className="mt-1.5 list-disc list-inside space-y-0.5 text-amber-700/90">
                {shownMonth.warnings.slice(0, 5).map((w, i) => <li key={i}>{w}</li>)}
              </ul>
              {shownMonth.warnings.length > 5 && (
                <p className="mt-1 text-amber-700">…and {shownMonth.warnings.length - 5} more.</p>
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

          <div className="mb-5">
            <div className="text-xs text-ink-faint mb-2 uppercase tracking-wide">
              Same-Month Benchmark Comparison
            </div>
            <BenchmarkComparisonTable rows={shownMonth.benchmark_comparison} />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <div className="text-xs text-ink-faint mb-2 uppercase tracking-wide">Revenue by Type</div>
              <div className="space-y-1.5">
                {shownMonth.by_type.map((t) => (
                  <div key={t.type} className="flex items-center justify-between text-xs">
                    <span className="text-ink-dim capitalize">{t.type}</span>
                    <span className="font-mono text-ink-dim">${t.total_revenue.toLocaleString()}</span>
                  </div>
                ))}
              </div>
            </div>
            <div>
              <div className="text-xs text-ink-faint mb-2 uppercase tracking-wide">Remaining Capacity (Month End)</div>
              <div className="space-y-1.5">
                {Object.entries(shownMonth.remaining_capacity).map(([cid, free]) => (
                  <div key={cid} className="flex items-center justify-between text-xs">
                    <span className="text-ink-dim">Cluster {cid}</span>
                    <span className="font-mono text-ink-dim">{free} units free</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </SectionCard>
      )}

      {/* ── Revise-for-next-month CTA ─────────────────────────────────────── */}
      {shownMonth && !sessionComplete && nextMonth !== null && (
        <button
          type="button"
          onClick={() => onNavigate(2)}
          className="w-full text-left rounded-xl border border-hud-accent/20 bg-gradient-to-r from-hud-accent/6 to-white p-6 flex items-center justify-between gap-6 hover:border-hud-accent/50 hover:from-hud-accent/8 transition-colors cursor-pointer shadow-card focus:outline-none focus-visible:ring-2 focus-visible:ring-hud-accent/60"
        >
          <div>
            <p className="text-xs font-mono uppercase tracking-widest text-hud-accent mb-2">
              Next Step
            </p>
            <h3 className="text-ink font-semibold text-base mb-1.5">
              Revise Policy for Month {nextMonth}
            </h3>
            <p className="text-ink-faint text-sm max-w-lg">
              Head to <strong className="text-ink-dim">02 Policy &amp; AI</strong> to tweak your code
              or parameters based on what you just saw — changes only affect Month {nextMonth} onward;
              Month {shownMonth.month} and earlier stay locked.
            </p>
          </div>
          <div className="shrink-0 flex items-center gap-2 rounded-lg border border-hud-gold bg-hud-gold px-4 py-2.5 text-ink text-xs font-semibold whitespace-nowrap">
            Revise Policy
            <span className="text-lg font-thin leading-none">→</span>
          </div>
        </button>
      )}

      {/* ── Cumulative results ───────────────────────────────────────────── */}
      {aggregated && (
        <>
          <div className="flex items-center gap-3 pt-1">
            <span className="h-px flex-1 bg-chip" />
            <span className="text-xs uppercase tracking-widest text-ink-faint font-semibold shrink-0">
              Cumulative — {completedMonths.length} of {TOTAL_MONTHS} Months
            </span>
            <span className="h-px flex-1 bg-chip" />
          </div>

          <div className="flex items-center justify-between gap-4">
            <p className="text-ink-faint text-xs">
              Save this run to your personal history on <strong className="text-ink-dim">04 History</strong>.
            </p>
            <button
              onClick={saveToHistory}
              className="shrink-0 rounded border border-hud-positive/30 bg-hud-positive/7 px-4 py-1.5 text-xs font-medium text-hud-positive hover:bg-hud-positive/14 focus:outline-none focus-visible:ring-2 focus-visible:ring-hud-positive/60 transition-colors"
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

          <SectionCard title="Cumulative Policy vs. Benchmarks" label="00">
            <ChartInsight>
              This compares your policy with fixed baseline policies over the same completed months.
              The goal is not just to beat every baseline, but to understand which tradeoff your policy is making.
            </ChartInsight>
            <BenchmarkComparisonTable rows={aggregated.benchmark_comparison} />
          </SectionCard>

          <SectionCard title="Monthly Revenue" label="01">
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={revenueData} margin={{ top: 4, right: 8, left: -10, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#DCE3EC" vertical={false} />
                <XAxis
                  dataKey="month"
                  tickFormatter={(m: number) => MONTH_LABELS[m - 1]}
                  tick={{ fill: '#5B7290', fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fill: '#5B7290', fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                  tickFormatter={formatCurrencyTick}
                />
                <Tooltip
                  {...TOOLTIP}
                  labelFormatter={(m: number) => MONTH_LABELS[m - 1]}
                  formatter={formatCurrencyExact}
                />
                <Bar dataKey="Revenue" fill="#002676" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </SectionCard>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
            <SectionCard title="Admitted vs. Rejected by Month" label="02">
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={admitVsRejectData} margin={{ top: 4, right: 8, left: -10, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#DCE3EC" vertical={false} />
                  <XAxis
                    dataKey="month"
                    tickFormatter={(m: number) => MONTH_LABELS[m - 1]}
                    tick={{ fill: '#5B7290', fontSize: 11 }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis tick={{ fill: '#5B7290', fontSize: 11 }} axisLine={false} tickLine={false} />
                  <Tooltip {...TOOLTIP} labelFormatter={(m: number) => MONTH_LABELS[m - 1]} />
                  <Legend wrapperStyle={{ fontSize: '12px', paddingTop: '10px', color: '#3E5872' }} />
                  <Bar dataKey="Admitted" fill="#2E7D32" radius={[2, 2, 0, 0]} />
                  <Bar dataKey="Rejected" fill="#DC2626" radius={[2, 2, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </SectionCard>

            <SectionCard title="Revenue by Request Type" label="03">
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={byTypeData} margin={{ top: 4, right: 8, left: -10, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#DCE3EC" vertical={false} />
                  <XAxis dataKey="type" tick={{ fill: '#5B7290', fontSize: 11 }} axisLine={false} tickLine={false} />
                  <YAxis
                    tick={{ fill: '#5B7290', fontSize: 11 }}
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
                <CartesianGrid strokeDasharray="3 3" stroke="#DCE3EC" vertical={false} />
                <XAxis dataKey="cluster" tick={{ fill: '#5B7290', fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis
                  tick={{ fill: '#5B7290', fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                  tickFormatter={(v: number) => `${v}%`}
                />
                <Tooltip {...TOOLTIP} formatter={(v: number) => `${v}%`} />
                <Legend wrapperStyle={{ fontSize: '12px', paddingTop: '10px', color: '#3E5872' }} />
                <Bar dataKey="Avg" fill="#002676" radius={[2, 2, 0, 0]} />
                <Bar dataKey="Peak" fill="#FDB515" radius={[2, 2, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </SectionCard>

          <SectionCard title="Past Monthly Results" label="05">
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-left text-ink-faint border-b border-line">
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
                <tbody className="font-mono text-ink-dim">
                  {completedMonths.map((m) => (
                    <tr
                      key={m.month}
                      onClick={() => setHighlightedMonth(m.month)}
                      className={`border-b border-line cursor-pointer hover:bg-chip/40 ${
                        m.month === highlightedMonth ? 'bg-hud-accent/8' : ''
                      }`}
                    >
                      <td className="py-2 pr-4 text-ink-dim">{MONTH_LABELS[m.month - 1]}</td>
                      <td className="py-2 pr-4">{m.total_requests}</td>
                      <td className="py-2 pr-4">{m.admitted_requests}</td>
                      <td className="py-2 pr-4">{m.rejected_requests}</td>
                      <td className="py-2 pr-4">{m.completed_requests}</td>
                      <td className="py-2 pr-4">{m.unfinished_requests}</td>
                      <td className="py-2 pr-4 text-ink">${m.total_revenue.toLocaleString()}</td>
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
            className="text-xs text-ink-faintest hover:text-red-600 border border-line hover:border-red-200 rounded px-3 py-1.5 focus:outline-none focus-visible:ring-2 focus-visible:ring-red-500/60 transition-colors"
          >
            Reset Session (discard all months)
          </button>
        </div>
      )}

    </div>
  )
}
