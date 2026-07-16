import { type ReactNode } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer, Cell,
} from 'recharts'
import { byMonth, byType, monthlyTypeBreakdown } from '../data/historicalData'
import type { Page } from '../components/NavBar'

// ── Constants ────────────────────────────────────────────────────────────────

const MONTH_LABELS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']

const COLORS = { VIP: '#60a5fa', Standard: '#a3e635', Economy: '#9ca3af' }

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

const SYSTEM_PARAMS = [
  { label: 'Server Clusters',    value: '3'           },
  { label: 'Capacity / Cluster', value: '100 units'   },
  { label: 'VIP Price',          value: '$12 / unit'  },
  { label: 'Standard Price',     value: '$7 / unit'   },
  { label: 'Economy Price',      value: '$4 / unit'   },
  { label: 'Simulation Horizon', value: '12 months'   },
]

const KEY_INSIGHTS = [
  {
    borderClass: 'border-l-blue-400',
    tagClass:    'text-blue-400',
    tag:   'Demand',
    title: 'Seasonal peak in summer',
    body:  'Requests jump ~48% from Jan to Jul. Policies that ignore seasonality will underperform during peak months.',
  },
  {
    borderClass: 'border-l-lime-400',
    tagClass:    'text-lime-400',
    tag:   'Revenue',
    title: 'Standard dominates volume; VIP earns the most per unit',
    body:  'VIP averages $125 per job — 3× Standard — yet is only ~14% of arrivals. Prioritising VIP has high upside.',
  },
  {
    borderClass: 'border-l-amber-400',
    tagClass:    'text-amber-400',
    tag:   'Duration',
    title: 'Economy jobs hold capacity 2× longer',
    body:  'Economy averages ~9 h vs. ~4 h for VIP. Admitting a cheap long job now can block several high-value arrivals.',
  },
]

// ── Helpers ──────────────────────────────────────────────────────────────────

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

// ── Page ─────────────────────────────────────────────────────────────────────

interface Props {
  onNavigate: (page: Page) => void
}

export default function IntroDataPage({ onNavigate }: Props) {
  const durationData = byType.map((t) => {
    const label = t.type === 'VIP' ? 'VIP'
      : t.type.charAt(0).toUpperCase() + t.type.slice(1)
    return {
      type:        label,
      'Avg Hours': parseFloat(t.avg_duration.toFixed(1)),
      fill:        COLORS[label as keyof typeof COLORS] ?? '#6b7280',
    }
  })

  const completionData = byType.map((t) => {
    const label = t.type === 'VIP' ? 'VIP'
      : t.type.charAt(0).toUpperCase() + t.type.slice(1)
    return {
      type:    label,
      'Rate %': parseFloat((t.completion_rate * 100).toFixed(1)),
      fill:    COLORS[label as keyof typeof COLORS] ?? '#6b7280',
    }
  })

  return (
    <div className="space-y-8">

      {/* ── Hero ───────────────────────────────────────────────────────── */}
      <div className="rounded-xl border border-gray-800 bg-gradient-to-br from-gray-900 via-gray-900 to-blue-950/20 p-8">
        <div className="flex items-center gap-2 mb-5">
          <span className="text-xs font-mono px-2.5 py-1 rounded-full border border-gray-700 text-gray-500 tracking-widest uppercase">
            Case Study
          </span>
          <span className="text-gray-700 text-xs">·</span>
          <span className="text-xs font-mono text-gray-600">Cloud Resource Allocation</span>
        </div>

        <h1 className="text-2xl font-bold text-gray-100 tracking-tight mb-3">
          Allocate Servers. Maximize Revenue.
        </h1>

        <p className="text-gray-400 leading-relaxed max-w-3xl mb-5">
          You are the operations lead of a cloud provider managing{' '}
          <span className="text-hud-accent font-medium">3 server clusters</span>, each
          with <span className="text-hud-accent font-medium">100 server-units</span> of
          reusable capacity. Incoming customer requests are one of three types —{' '}
          <span className="text-blue-400 font-medium">VIP</span>,{' '}
          <span className="text-lime-400 font-medium">Standard</span>, or{' '}
          <span className="text-gray-400 font-medium">Economy</span> — each with different
          revenue rates and service durations. When a job completes within the month,
          revenue is collected and capacity is released for reuse.
        </p>

        <div className="inline-flex flex-wrap items-center gap-3 rounded-lg border border-hud-accent/30 bg-blue-950/30 px-4 py-3">
          <span className="text-hud-accent font-semibold text-sm shrink-0">Your Task</span>
          <span className="w-px h-4 bg-gray-700 shrink-0" />
          <span className="text-gray-300 text-sm">
            Design an <strong>admission &amp; routing policy</strong> — for each arriving
            request, decide: <em>admit or reject?</em> If admitted, <em>which cluster?</em>
          </span>
        </div>

        <p className="text-gray-600 text-xs mt-4 leading-relaxed max-w-2xl">
          The core tension: admitting a low-value, long-duration Economy job now may block a
          higher-value VIP job that arrives later. Use the data below to understand the
          trade-offs before you design your policy.
        </p>
      </div>

      {/* ── System Parameters ──────────────────────────────────────────── */}
      <div className="rounded-lg border border-gray-800 bg-gray-900 p-6">
        <h2 className="text-xs font-semibold uppercase tracking-widest text-gray-500 mb-4">
          System Parameters
        </h2>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          {SYSTEM_PARAMS.map(({ label, value }) => (
            <div
              key={label}
              className="rounded-lg border border-gray-800 bg-gray-950 px-4 py-3"
            >
              <div className="text-xs text-gray-600 mb-1">{label}</div>
              <div className="font-mono text-hud-accent font-semibold text-sm">{value}</div>
            </div>
          ))}
        </div>
      </div>

      {/* ── Key Insights ───────────────────────────────────────────────── */}
      <div>
        <h2 className="text-xs font-semibold uppercase tracking-widest text-gray-500 mb-3">
          Key Insights — Before You Start
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {KEY_INSIGHTS.map(({ borderClass, tagClass, tag, title, body }) => (
            <div
              key={tag}
              className={`rounded-lg border border-gray-800 border-l-2 ${borderClass} bg-gray-900 px-4 py-4`}
            >
              <span className={`text-xs font-mono uppercase tracking-wider ${tagClass} mb-1.5 block`}>
                {tag}
              </span>
              <p className="text-gray-200 text-sm font-medium mb-1.5 leading-snug">{title}</p>
              <p className="text-gray-500 text-xs leading-relaxed">{body}</p>
            </div>
          ))}
        </div>
      </div>

      {/* ── Chart 01: Monthly Demand ────────────────────────────────────── */}
      <SectionCard title="Monthly Demand — Historical Year" label="01">
        <ChartInsight>
          Demand is lowest in Jan–Feb (~770 requests) and peaks in Jul–Aug (~1,100+).
          A smart policy should account for this seasonality — peak months stress capacity most.
        </ChartInsight>
        <ResponsiveContainer width="100%" height={240}>
          <BarChart data={byMonth} margin={{ top: 4, right: 8, left: -10, bottom: 0 }}>
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
            />
            <Tooltip
              {...TOOLTIP}
              labelFormatter={(m: number) => MONTH_LABELS[m - 1]}
            />
            <Bar
              dataKey="total_requests"
              name="Requests"
              fill="#60a5fa"
              radius={[3, 3, 0, 0]}
            />
          </BarChart>
        </ResponsiveContainer>
      </SectionCard>

      {/* ── Chart 02: Type Breakdown ─────────────────────────────────────── */}
      <SectionCard title="Request Type Breakdown by Month" label="02">
        <ChartInsight>
          Standard jobs account for ~50–55% of arrivals; VIP only ~12–15%. Yet VIP earns
          $125 per job on average — 3× more than Standard. <em>Volume ≠ value.</em> A good
          policy protects VIP slots even during high-volume months.
        </ChartInsight>
        <ResponsiveContainer width="100%" height={240}>
          <BarChart
            data={monthlyTypeBreakdown}
            margin={{ top: 4, right: 8, left: -10, bottom: 0 }}
          >
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
            />
            <Tooltip
              {...TOOLTIP}
              labelFormatter={(m: number) => MONTH_LABELS[m - 1]}
            />
            <Legend
              wrapperStyle={{ fontSize: '12px', paddingTop: '10px', color: '#9ca3af' }}
            />
            <Bar dataKey="VIP"      fill={COLORS.VIP}      radius={[2, 2, 0, 0]} />
            <Bar dataKey="Standard" fill={COLORS.Standard}  radius={[2, 2, 0, 0]} />
            <Bar dataKey="Economy"  fill={COLORS.Economy}   radius={[2, 2, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </SectionCard>

      {/* ── Charts 03 & 04: Duration + Completion ───────────────────────── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
        <SectionCard title="Avg Service Duration by Type" label="03">
          <ChartInsight>
            Economy averages ~9 h vs. VIP's ~4 h. Every server-unit held by a long Economy
            job is unavailable to the next VIP arrival.
          </ChartInsight>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={durationData} margin={{ top: 4, right: 8, left: -10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" vertical={false} />
              <XAxis
                dataKey="type"
                tick={{ fill: '#6b7280', fontSize: 11 }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                tick={{ fill: '#6b7280', fontSize: 11 }}
                axisLine={false}
                tickLine={false}
                unit="h"
              />
              <Tooltip {...TOOLTIP} />
              <Bar dataKey="Avg Hours" radius={[3, 3, 0, 0]}>
                {durationData.map((entry, i) => (
                  <Cell key={i} fill={entry.fill} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </SectionCard>

        <SectionCard title="Completion Rate by Type" label="04">
          <ChartInsight>
            VIP completes 95% of the time; Economy only 85%. Longer jobs are more likely
            to run past month-end — consuming capacity but earning zero revenue.
          </ChartInsight>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={completionData} margin={{ top: 4, right: 8, left: -10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" vertical={false} />
              <XAxis
                dataKey="type"
                tick={{ fill: '#6b7280', fontSize: 11 }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                tick={{ fill: '#6b7280', fontSize: 11 }}
                axisLine={false}
                tickLine={false}
                unit="%"
                domain={[80, 100]}
              />
              <Tooltip {...TOOLTIP} />
              <Bar dataKey="Rate %" radius={[3, 3, 0, 0]}>
                {completionData.map((entry, i) => (
                  <Cell key={i} fill={entry.fill} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </SectionCard>
      </div>

      {/* ── CTA ────────────────────────────────────────────────────────── */}
      <button
        type="button"
        onClick={() => onNavigate(2)}
        className="w-full text-left rounded-xl border border-hud-accent/20 bg-gradient-to-r from-blue-950/30 to-gray-900 p-6 flex items-center justify-between gap-6 hover:border-hud-accent/50 hover:from-blue-950/50 transition-colors cursor-pointer"
      >
        <div>
          <p className="text-xs font-mono uppercase tracking-widest text-hud-accent mb-2">
            Next Step
          </p>
          <h3 className="text-gray-100 font-semibold text-base mb-1.5">
            Ready to design your policy?
          </h3>
          <p className="text-gray-500 text-sm max-w-lg">
            Head to <strong className="text-gray-300">02 Policy &amp; AI</strong> to
            configure an admission and routing policy, get AI-generated suggestions, and
            run your first simulation.
          </p>
        </div>
        <div className="shrink-0 text-hud-accent text-4xl font-thin opacity-50 select-none">
          →
        </div>
      </button>

    </div>
  )
}
