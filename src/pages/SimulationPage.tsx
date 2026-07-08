import { useState, type ReactNode } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer, Cell,
} from 'recharts'
import { postSimulate } from '../lib/api'
import { createSubmission } from '../lib/storage'
import type { PolicyParams, SimulationResponse } from '../types/simulation'
import type { Submission } from '../types/user'

// ── Constants ────────────────────────────────────────────────────────────────

const MONTH_LABELS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']

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

// ── Page ─────────────────────────────────────────────────────────────────────

interface Props {
  policyCode: string
  policyParams: PolicyParams
  results: SimulationResponse | null
  onResultsChange: (results: SimulationResponse) => void
  onSaveSubmission: (submission: Submission) => void
}

export default function SimulationPage({
  policyCode,
  policyParams,
  results,
  onResultsChange,
  onSaveSubmission,
}: Props) {
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState<string | null>(null)
  const [justSaved, setJustSaved] = useState(false)

  function saveToHistory() {
    if (!results) return
    onSaveSubmission(createSubmission(policyCode, policyParams, results))
    setJustSaved(true)
    setTimeout(() => setJustSaved(false), 2000)
  }

  const hasSignature = policyCode.includes('def admission_policy(')
  const paramEntries  = Object.entries(policyParams)

  async function runSimulation() {
    setLoading(true)
    setError(null)
    try {
      const res = await postSimulate({ policy_code: policyCode, params: policyParams, seed: 42 })
      onResultsChange(res)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Simulation failed')
    } finally {
      setLoading(false)
    }
  }

  const admitVsRejectData = results?.monthly.map((m) => ({
    month: m.month,
    Admitted: m.admitted_requests,
    Rejected: m.rejected_requests,
  }))

  const revenueData = results?.monthly.map((m) => ({
    month: m.month,
    Revenue: m.total_revenue,
  }))

  const byTypeData = results?.by_type.map((t) => ({
    type: t.type === 'VIP' ? 'VIP' : t.type.charAt(0).toUpperCase() + t.type.slice(1),
    Revenue: t.total_revenue,
    fill: TYPE_COLORS[t.type] ?? '#6b7280',
  }))

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
          Test Your Policy Against a Full Year
        </h1>
        <p className="text-gray-400 leading-relaxed max-w-3xl">
          Runs your current <span className="text-hud-accent font-medium">admission_policy</span> against
          a freshly generated year of arrivals with real capacity and departure dynamics — a job only earns
          revenue if it's admitted <em>and</em> completes before month-end. Tweak your code or parameters on{' '}
          <strong className="text-gray-300">02 Policy &amp; AI</strong> and come back here any time; your
          last run stays visible until you run again.
        </p>
      </div>

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
          <button
            onClick={runSimulation}
            disabled={loading || !hasSignature}
            className="rounded border border-hud-accent/30 bg-blue-950/30 px-5 py-2 text-xs font-medium text-hud-accent hover:bg-blue-950/50 disabled:opacity-30 disabled:cursor-not-allowed transition-colors shrink-0"
          >
            {loading ? 'Running…' : 'Run Simulation'}
          </button>
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
      {!results && !loading && (
        <div className="rounded-lg border border-dashed border-gray-800 bg-gray-900/40 p-10 text-center">
          <p className="text-gray-600 text-sm">
            No simulation run yet. Click <strong className="text-gray-400">Run Simulation</strong> above
            to see how your policy performs.
          </p>
        </div>
      )}

      {/* ── Results ───────────────────────────────────────────────────────── */}
      {results && (
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

          {results.warnings.length > 0 && (
            <div className="rounded border border-amber-800/40 bg-amber-950/20 px-4 py-3 text-xs text-amber-500 leading-relaxed">
              <strong>{results.warnings.length} warning{results.warnings.length === 1 ? '' : 's'}</strong> during
              the run (e.g. invalid or infeasible cluster choices were auto-rejected):
              <ul className="mt-1.5 list-disc list-inside space-y-0.5 text-amber-500/80">
                {results.warnings.slice(0, 5).map((w, i) => <li key={i}>{w}</li>)}
              </ul>
              {results.warnings.length > 5 && (
                <p className="mt-1 text-amber-600">…and {results.warnings.length - 5} more.</p>
              )}
            </div>
          )}

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <StatTile label="Total Revenue (Year)" value={`$${results.total_revenue.toLocaleString()}`} accent />
            <StatTile
              label="Total Requests"
              value={results.monthly.reduce((s, m) => s + m.total_requests, 0).toLocaleString()}
            />
            <StatTile
              label="Admitted"
              value={results.monthly.reduce((s, m) => s + m.admitted_requests, 0).toLocaleString()}
            />
            <StatTile
              label="Completed"
              value={results.monthly.reduce((s, m) => s + m.completed_requests, 0).toLocaleString()}
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
                <YAxis tick={{ fill: '#6b7280', fontSize: 11 }} axisLine={false} tickLine={false} />
                <Tooltip {...TOOLTIP} labelFormatter={(m: number) => MONTH_LABELS[m - 1]} />
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
                  <YAxis tick={{ fill: '#6b7280', fontSize: 11 }} axisLine={false} tickLine={false} />
                  <Tooltip {...TOOLTIP} />
                  <Bar dataKey="Revenue" radius={[3, 3, 0, 0]}>
                    {byTypeData?.map((entry, i) => <Cell key={i} fill={entry.fill} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </SectionCard>
          </div>
        </>
      )}

    </div>
  )
}
