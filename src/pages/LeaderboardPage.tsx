import type { ReactNode } from 'react'
import type { CurrentUser, Submission } from '../types/user'

// ── Mock data ────────────────────────────────────────────────────────────────
// Phase 1 prototype only — there is no shared backend, so "classmates" are
// hardcoded and the leaderboard only ever reflects this one browser's user.
// See the Phase 2 notes in the chat response for what real cross-student
// data would require.

interface MockClassmate {
  anonymousName: string
  bestRunRevenue: number
  monthsCompleted: number
  vipCompletionRate: number | null
  lastSubmission: string
}

const MOCK_CLASSMATES: MockClassmate[] = [
  { anonymousName: 'Bright Comet 41', bestRunRevenue: 612430, monthsCompleted: 12, vipCompletionRate: 0.97, lastSubmission: '2026-07-02T10:00:00.000Z' },
  { anonymousName: 'Steady Ridge 18', bestRunRevenue: 574210, monthsCompleted: 12, vipCompletionRate: 0.93, lastSubmission: '2026-07-03T15:30:00.000Z' },
  { anonymousName: 'Keen Atlas 77',   bestRunRevenue: 498650, monthsCompleted: 11, vipCompletionRate: 0.89, lastSubmission: '2026-07-01T09:15:00.000Z' },
  { anonymousName: 'Calm Harbor 23',  bestRunRevenue: 441200, monthsCompleted: 12, vipCompletionRate: 0.91, lastSubmission: '2026-06-30T18:45:00.000Z' },
]

interface MockSubmissionRow {
  id: string
  timestamp: string
  total_revenue: number
  warningsCount: number
}

const MOCK_PAST_SUBMISSIONS: MockSubmissionRow[] = [
  { id: 'sample-1', timestamp: '2026-06-28T14:20:00.000Z', total_revenue: 402100, warningsCount: 3 },
  { id: 'sample-2', timestamp: '2026-06-30T09:05:00.000Z', total_revenue: 455800, warningsCount: 0 },
]

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

function SampleDataBanner() {
  return (
    <p className="mb-3 text-xs text-amber-700/90 italic">
      Showing sample data — run a simulation on 03 Simulation and save it here to replace this.
    </p>
  )
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
}

function formatMoney(n: number): string {
  return `$${Math.round(n).toLocaleString()}`
}

// ── Page ─────────────────────────────────────────────────────────────────────

interface Props {
  currentUser: CurrentUser
  submissionHistory: Submission[]
}

export default function LeaderboardPage({ currentUser, submissionHistory }: Props) {
  const hasSubmissions = submissionHistory.length > 0

  // submissionHistory is prepended-newest-first by App.tsx.
  const latestSubmission = hasSubmissions ? submissionHistory[0] : null
  const bestSubmission = hasSubmissions
    ? submissionHistory.reduce((best, s) => (s.total_revenue > best.total_revenue ? s : best))
    : null

  const totalSubmissions = submissionHistory.length
  const avgRevenue = hasSubmissions
    ? submissionHistory.reduce((sum, s) => sum + s.total_revenue, 0) / totalSubmissions
    : 0

  const bestVip = bestSubmission?.by_type.find((t) => t.type === 'VIP') ?? null
  const currentUserVipRate =
    bestVip && bestVip.total_requests > 0 ? bestVip.completed_requests / bestVip.total_requests : null

  const leaderboardRows = [
    ...MOCK_CLASSMATES.map((c) => ({ ...c, isCurrentUser: false })),
    {
      anonymousName: `${currentUser.anonymousName} (you)`,
      bestRunRevenue: bestSubmission?.total_revenue ?? 0,
      monthsCompleted: bestSubmission?.monthly.length ?? 0,
      vipCompletionRate: currentUserVipRate,
      lastSubmission: latestSubmission?.timestamp ?? currentUser.createdAt,
      isCurrentUser: true,
    },
  ].sort((a, b) => b.bestRunRevenue - a.bestRunRevenue)

  const pastSubmissionRows: MockSubmissionRow[] = hasSubmissions
    ? submissionHistory.map((s) => ({
        id: s.id,
        timestamp: s.timestamp,
        total_revenue: s.total_revenue,
        warningsCount: s.warnings.length,
      }))
    : MOCK_PAST_SUBMISSIONS

  return (
    <div className="space-y-8">

      {/* ── Hero ───────────────────────────────────────────────────────── */}
      <div className="rounded-xl border border-line bg-gradient-to-br from-white via-white to-hud-accent/6 p-8 shadow-card">
        <div className="flex items-center gap-2 mb-5">
          <span className="text-xs font-mono px-2.5 py-1 rounded-full border border-line-strong text-ink-faint tracking-widest uppercase">
            04  History
          </span>
        </div>
        <h1 className="text-2xl font-bold text-ink tracking-tight mb-3">
          Your History &amp; the Class Leaderboard
        </h1>
        <p className="text-ink-dim leading-relaxed max-w-3xl">
          A prototype personal record: an anonymous identifier generated for this browser, your
          saved simulation runs, and how your best run compares to a few sample classmates. This is
          a local-only Phase 1 preview — see the chat response for what a real account/leaderboard
          system would still need.
        </p>
      </div>

      {/* ── Current Student + Personal Performance ───────────────────────── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
        <SectionCard title="Current Student" label="Identity">
          <div className="space-y-3">
            <div>
              <div className="text-xs text-ink-faint mb-1">Anonymous Name</div>
              <div className="font-mono text-hud-accent font-semibold text-sm">{currentUser.anonymousName}</div>
            </div>
            <div>
              <div className="text-xs text-ink-faint mb-1">User ID</div>
              <div className="font-mono text-ink-faint text-xs">{currentUser.userId}</div>
            </div>
            <div>
              <div className="text-xs text-ink-faint mb-1">Account Created</div>
              <div className="font-mono text-ink-dim text-xs">{formatDate(currentUser.createdAt)}</div>
            </div>
          </div>
        </SectionCard>

        <SectionCard title="Personal Performance Summary" label="Stats">
          {hasSubmissions ? (
            <div className="grid grid-cols-2 gap-3">
              <StatTile label="Saved Runs" value={String(totalSubmissions)} />
              <StatTile label="Best Run Revenue" value={formatMoney(bestSubmission!.total_revenue)} accent />
              <StatTile label="Average Revenue" value={formatMoney(avgRevenue)} />
              <StatTile
                label="Latest Save"
                value={latestSubmission ? formatDate(latestSubmission.timestamp) : '—'}
              />
            </div>
          ) : (
            <p className="text-ink-faint text-xs leading-relaxed">
              No saved runs yet. Go to <strong className="text-ink-dim">03 Simulation</strong>, run
              your policy, and click <strong className="text-ink-dim">Save to My History</strong> to
              start building your record.
            </p>
          )}
        </SectionCard>
      </div>

      {/* ── Monthly Results ───────────────────────────────────────────────── */}
      <SectionCard title="Monthly Results — Latest Saved Run" label="01">
        {latestSubmission ? (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-ink-faint border-b border-line">
                  <th className="py-2 pr-4 font-medium">Month</th>
                  <th className="py-2 pr-4 font-medium">Requests</th>
                  <th className="py-2 pr-4 font-medium">Admitted</th>
                  <th className="py-2 pr-4 font-medium">Completed</th>
                  <th className="py-2 pr-4 font-medium">Rejected</th>
                  <th className="py-2 pr-4 font-medium">Revenue</th>
                </tr>
              </thead>
              <tbody className="font-mono text-ink-dim">
                {latestSubmission.monthly.map((m) => (
                  <tr key={m.month} className="border-b border-line">
                    <td className="py-2 pr-4">{m.month}</td>
                    <td className="py-2 pr-4">{m.total_requests}</td>
                    <td className="py-2 pr-4">{m.admitted_requests}</td>
                    <td className="py-2 pr-4">{m.completed_requests}</td>
                    <td className="py-2 pr-4">{m.rejected_requests}</td>
                    <td className="py-2 pr-4 text-ink">{formatMoney(m.total_revenue)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-ink-faint text-xs leading-relaxed">
            No saved runs yet — this table will populate once you save a simulation from Page 3.
          </p>
        )}
      </SectionCard>

      {/* ── Past Submissions ──────────────────────────────────────────────── */}
      <SectionCard title="Past Submissions" label="02">
        {!hasSubmissions && <SampleDataBanner />}
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-ink-faint border-b border-line">
                <th className="py-2 pr-4 font-medium">Saved</th>
                <th className="py-2 pr-4 font-medium">Total Revenue</th>
                <th className="py-2 pr-4 font-medium">Warnings</th>
              </tr>
            </thead>
            <tbody className="font-mono text-ink-dim">
              {pastSubmissionRows.map((s) => (
                <tr key={s.id} className="border-b border-line">
                  <td className="py-2 pr-4">{formatDate(s.timestamp)}</td>
                  <td className="py-2 pr-4 text-ink">{formatMoney(s.total_revenue)}</td>
                  <td className="py-2 pr-4">{s.warningsCount}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </SectionCard>

      {/* ── Anonymous Leaderboard ─────────────────────────────────────────── */}
      <SectionCard title="Anonymous Leaderboard" label="03">
        <p className="text-ink-faint text-xs leading-relaxed mb-4">
          Ranked by best single-run revenue. Classmate rows are sample data for this prototype —
          there is no shared backend yet, so only your own row reflects real saved runs.
        </p>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-ink-faint border-b border-line">
                <th className="py-2 pr-4 font-medium">Rank</th>
                <th className="py-2 pr-4 font-medium">Student</th>
                <th className="py-2 pr-4 font-medium">Best Run Revenue</th>
                <th className="py-2 pr-4 font-medium">Months Completed</th>
                <th className="py-2 pr-4 font-medium">VIP Completion</th>
                <th className="py-2 pr-4 font-medium">Last Submission</th>
              </tr>
            </thead>
            <tbody className="font-mono text-ink-dim">
              {leaderboardRows.map((row, i) => (
                <tr
                  key={row.anonymousName}
                  className={`border-b border-line ${row.isCurrentUser ? 'bg-hud-accent/6 text-ink' : ''}`}
                >
                  <td className="py-2 pr-4">{i + 1}</td>
                  <td className={`py-2 pr-4 ${row.isCurrentUser ? 'text-hud-accent font-semibold' : ''}`}>
                    {row.anonymousName}
                  </td>
                  <td className="py-2 pr-4">{formatMoney(row.bestRunRevenue)}</td>
                  <td className="py-2 pr-4">{row.monthsCompleted}</td>
                  <td className="py-2 pr-4">
                    {row.vipCompletionRate === null ? '—' : `${Math.round(row.vipCompletionRate * 100)}%`}
                  </td>
                  <td className="py-2 pr-4">{formatDate(row.lastSubmission)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </SectionCard>

    </div>
  )
}
