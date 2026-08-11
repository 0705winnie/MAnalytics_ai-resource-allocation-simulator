import { type ReactNode } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer, Cell,
} from 'recharts'
import { byMonth, byType, monthlyTypeBreakdown } from '../data/historicalData'
import type { Page } from '../components/NavBar'

// ── Constants ────────────────────────────────────────────────────────────────

const MONTH_LABELS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']

const COLORS = { VIP: '#002676', Standard: '#2E7D32', Economy: '#8598AF' }

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

export const SYSTEM_PARAMS = [
  { label: 'Server Clusters',    value: '10'          },
  { label: 'Cluster Capacity',   value: '12-20 units' },
  { label: 'Simulation Horizon', value: '12 months'   },
  { label: 'VIP Price',          value: '$14 / unit'  },
  { label: 'Standard Price',     value: '$8 / unit'   },
  { label: 'Economy Price',      value: '$4 / unit'   },
]

const KEY_INSIGHTS = [
  {
    borderClass: 'border-l-hud-accent',
    tagClass:    'text-hud-accent',
    tag:   'Demand',
    title: 'Seasonal peak in summer',
    body:  'Requests jump ~48% from Jan to Jul. Policies that ignore seasonality will underperform during peak months.',
  },
  {
    borderClass: 'border-l-hud-positive',
    tagClass:    'text-hud-positive',
    tag:   'Revenue',
    title: 'Standard dominates volume; VIP earns the most per unit',
    body:  'VIP jobs earn the highest unit price, while Standard jobs dominate request volume. Prioritising valuable capacity use has high upside.',
  },
  {
    borderClass: 'border-l-amber-500',
    tagClass:    'text-amber-700',
    tag:   'Duration',
    title: 'Economy jobs hold capacity longer',
    body:  'Economy requests tend to last longer than VIP requests. Admitting a cheap long job now can block several high-value arrivals.',
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

// ── Page ─────────────────────────────────────────────────────────────────────

interface Props {
  onNavigate: (page: Page) => void
}

export default function IntroDataPage({ onNavigate }: Props) {
  const vipType = byType.find((t) => t.type === 'VIP')
  const standardType = byType.find((t) => t.type === 'standard')
  const economyType = byType.find((t) => t.type === 'economy')
  const vipAvgRevenue = vipType ? Math.round(vipType.avg_revenue) : 0
  const standardAvgRevenue = standardType ? Math.round(standardType.avg_revenue) : 0
  const vipDuration = vipType ? vipType.avg_duration.toFixed(1) : '0.0'
  const economyDuration = economyType ? economyType.avg_duration.toFixed(1) : '0.0'
  const vipCompletion = vipType ? (vipType.completion_rate * 100).toFixed(1) : '0.0'
  const economyCompletion = economyType ? (economyType.completion_rate * 100).toFixed(1) : '0.0'

  const durationData = byType.map((t) => {
    const label = t.type === 'VIP' ? 'VIP'
      : t.type.charAt(0).toUpperCase() + t.type.slice(1)
    return {
      type:        label,
      'Avg Hours': parseFloat(t.avg_duration.toFixed(1)),
      fill:        COLORS[label as keyof typeof COLORS] ?? '#5B7290',
    }
  })

  const completionData = byType.map((t) => {
    const label = t.type === 'VIP' ? 'VIP'
      : t.type.charAt(0).toUpperCase() + t.type.slice(1)
    return {
      type:    label,
      'Rate %': parseFloat((t.completion_rate * 100).toFixed(1)),
      fill:    COLORS[label as keyof typeof COLORS] ?? '#5B7290',
    }
  })

  return (
    <div className="space-y-8">

      {/* ── Hero ───────────────────────────────────────────────────────── */}
      <div className="rounded-xl border border-line bg-gradient-to-br from-white via-white to-hud-accent/6 p-8 shadow-card">
        <div className="flex items-center gap-2 mb-5">
          <span className="text-xs font-mono px-2.5 py-1 rounded-full border border-line-strong text-ink-faint tracking-widest uppercase">
            Case Study
          </span>
          <span className="text-ink-faintest text-xs">·</span>
          <span className="text-xs font-mono text-ink-faint">Cloud Resource Allocation</span>
        </div>

        <h1 className="text-2xl font-bold text-ink tracking-tight mb-3">
          Allocate Servers. Maximize Revenue.
        </h1>

        <p className="text-ink-dim leading-relaxed max-w-3xl mb-5">
          You are the operations lead of a cloud provider managing{' '}
          <span className="text-hud-accent font-medium">10 server clusters</span> with
          heterogeneous <span className="text-hud-accent font-medium">12-20 server-units</span> of
          reusable capacity. Incoming customer requests are one of three types —{' '}
          <span className="text-hud-accent font-medium">VIP</span>,{' '}
          <span className="text-hud-positive font-medium">Standard</span>, or{' '}
          <span className="text-ink-dim font-medium">Economy</span> — each with different
          revenue rates and service durations. When a job completes within the month,
          revenue is collected and capacity is released for reuse.
        </p>

        <div className="inline-flex flex-wrap items-center gap-3 rounded-lg border border-hud-accent/30 bg-hud-accent/8 px-4 py-3">
          <span className="text-hud-accent font-semibold text-sm shrink-0">Your Task</span>
          <span className="w-px h-4 bg-line-strong shrink-0" />
          <span className="text-ink-dim text-sm">
            Design an <strong>admission &amp; routing policy</strong> — for each arriving
            request, decide: <em>admit or reject?</em> If admitted, <em>which cluster?</em>
          </span>
        </div>

        <p className="text-ink-faint text-xs mt-4 leading-relaxed max-w-2xl">
          The core tension: admitting a low-value, long-duration Economy job now may block a
          higher-value VIP job that arrives later. Use the data below to understand the
          trade-offs before you design your policy.
        </p>
      </div>

      {/* ── System Parameters ──────────────────────────────────────────── */}
      <div className="rounded-lg border border-line bg-white p-6 shadow-card">
        <h2 className="text-xs font-semibold uppercase tracking-widest text-ink-faint mb-4">
          System Parameters
        </h2>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          {SYSTEM_PARAMS.map(({ label, value }) => (
            <div
              key={label}
              className="rounded-lg border border-line bg-well px-4 py-3"
            >
              <div className="text-xs text-ink-faint mb-1">{label}</div>
              <div className="font-mono text-hud-accent font-semibold text-sm">{value}</div>
            </div>
          ))}
        </div>
      </div>

      {/* ── Key Insights ───────────────────────────────────────────────── */}
      <div>
        <h2 className="text-xs font-semibold uppercase tracking-widest text-ink-faint mb-3">
          Key Insights — Before You Start
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {KEY_INSIGHTS.map(({ borderClass, tagClass, tag, title, body }) => (
            <div
              key={tag}
              className={`rounded-lg border border-line border-l-2 ${borderClass} bg-white px-4 py-4`}
            >
              <span className={`text-xs font-mono uppercase tracking-wider ${tagClass} mb-1.5 block`}>
                {tag}
              </span>
              <p className="text-ink text-sm font-medium mb-1.5 leading-snug">{title}</p>
              <p className="text-ink-faint text-xs leading-relaxed">{body}</p>
            </div>
          ))}
        </div>
      </div>

      {/* ── Chart 01: Monthly Demand ────────────────────────────────────── */}
      <SectionCard title="Monthly Demand — Historical Year" label="01">
        <ChartInsight>
          Demand is lowest early in the year and peaks in the summer. A smart policy should
          account for this seasonality because peak months stress capacity most.
        </ChartInsight>
        <ResponsiveContainer width="100%" height={240}>
          <BarChart data={byMonth} margin={{ top: 4, right: 8, left: -10, bottom: 0 }}>
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
            />
            <Tooltip
              {...TOOLTIP}
              labelFormatter={(m: number) => MONTH_LABELS[m - 1]}
            />
            <Bar
              dataKey="total_requests"
              name="Requests"
              fill="#002676"
              radius={[3, 3, 0, 0]}
            />
          </BarChart>
        </ResponsiveContainer>
      </SectionCard>

      {/* ── Chart 02: Type Breakdown ─────────────────────────────────────── */}
      <SectionCard title="Request Type Breakdown by Month" label="02">
        <ChartInsight>
          Standard jobs account for the largest share of arrivals, while VIP jobs are less
          frequent but earn about {vipAvgRevenue} per completed job on average, compared
          with about {standardAvgRevenue} for Standard. A good policy should balance volume,
          value, and future capacity.
        </ChartInsight>
        <ResponsiveContainer width="100%" height={240}>
          <BarChart
            data={monthlyTypeBreakdown}
            margin={{ top: 4, right: 8, left: -10, bottom: 0 }}
          >
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
            />
            <Tooltip
              {...TOOLTIP}
              labelFormatter={(m: number) => MONTH_LABELS[m - 1]}
            />
            <Legend
              wrapperStyle={{ fontSize: '12px', paddingTop: '10px', color: '#3E5872' }}
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
            Economy averages about {economyDuration} h vs. VIP's about {vipDuration} h.
            Every server-unit held by a long Economy job is unavailable to future arrivals.
          </ChartInsight>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={durationData} margin={{ top: 4, right: 8, left: -10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#DCE3EC" vertical={false} />
              <XAxis
                dataKey="type"
                tick={{ fill: '#5B7290', fontSize: 11 }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                tick={{ fill: '#5B7290', fontSize: 11 }}
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
            VIP completes about {vipCompletion}% of the time; Economy completes about{' '}
            {economyCompletion}%. Longer jobs are more likely to run past month-end,
            consuming capacity but earning zero revenue.
          </ChartInsight>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={completionData} margin={{ top: 4, right: 8, left: -10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#DCE3EC" vertical={false} />
              <XAxis
                dataKey="type"
                tick={{ fill: '#5B7290', fontSize: 11 }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                tick={{ fill: '#5B7290', fontSize: 11 }}
                axisLine={false}
                tickLine={false}
                unit="%"
                domain={[0, 100]}
                ticks={[0, 25, 50, 75, 100]}
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
        className="w-full text-left rounded-xl border border-hud-accent/20 bg-gradient-to-r from-hud-accent/8 to-white p-6 flex items-center justify-between gap-6 hover:border-hud-accent/50 hover:from-hud-accent/12 transition-colors cursor-pointer shadow-card"
      >
        <div>
          <p className="text-xs font-mono uppercase tracking-widest text-hud-accent mb-2">
            Next Step
          </p>
          <h3 className="text-ink font-semibold text-base mb-1.5">
            Ready to design your policy?
          </h3>
          <p className="text-ink-faint text-sm max-w-lg">
            Head to <strong className="text-ink-dim">02 Policy &amp; AI</strong> to
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
