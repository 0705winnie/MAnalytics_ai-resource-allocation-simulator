// Shared types for the Page 2 (Policy & AI) <-> Page 3 (Simulation) workflow.
// Kept in one place because both pages, and the state lifted into App.tsx,
// need to agree on the same shapes.

export type RequestType = 'VIP' | 'standard' | 'economy'

// Free-form tunable values the student's policy code can read via its
// `params` argument. Values are numbers so they can double as thresholds,
// multipliers, etc. without over-specifying the policy's design space.
export type PolicyParams = Record<string, number>

export interface SimulationMonthResult {
  month: number
  total_requests: number
  admitted_requests: number
  completed_requests: number
  rejected_requests: number
  total_revenue: number
  unfinished_requests: number
  unfinished_value: number
  // Keyed by cluster id; JSON object keys arrive as strings.
  avg_utilization: Record<string, number>
  peak_utilization: Record<string, number>
}

export interface SimulationTypeResult {
  type: RequestType
  total_requests: number
  admitted_requests: number
  completed_requests: number
  total_revenue: number
}

export interface BenchmarkResult {
  policy: string
  total_revenue: number
  total_unfinished_requests: number
  total_unfinished_value: number
  admitted_requests: number
  completed_requests: number
  rejected_requests: number
  warnings_count: number
}

// Response shape for POST /simulate/month — one month's full detail,
// including the pieces the full-year SimulationMonthResult doesn't carry
// (this month's own by_type breakdown, warnings, and end-of-month capacity).
export interface MonthDetailResult extends SimulationMonthResult {
  by_type: SimulationTypeResult[]
  warnings: string[]
  benchmark_comparison: BenchmarkResult[]
  // Legacy non-persisting simulation response only; official History omits it.
  remaining_capacity: Record<string, number>
}

export interface RevenueByTypeResult {
  type: string
  total_revenue: number
}

export interface OfficialMonthlyResult extends Omit<MonthDetailResult, 'by_type' | 'remaining_capacity'> {
  by_type: RevenueByTypeResult[]
  policy_code: string
  params: PolicyParams
  policy_hash: string
  completed_at: string
}

export interface OfficialCumulativeResult {
  total_requests: number
  admitted_requests: number
  completed_requests: number
  rejected_requests: number
  total_revenue: number
  total_unfinished_requests: number
  total_unfinished_value: number
  warnings_count: number
  by_type: RevenueByTypeResult[]
  benchmark_comparison: BenchmarkResult[]
}

export interface OfficialLatestPolicy {
  policy_code: string
  params: PolicyParams
  policy_hash: string
}

export interface OfficialSimulationSession {
  session_id: string
  completed_months: number
  next_month: number | null
  status: 'not_started' | 'in_progress' | 'completed'
  cumulative: OfficialCumulativeResult
  monthly_results: OfficialMonthlyResult[]
  latest_policy: OfficialLatestPolicy | null
}

export interface RunNextMonthRequest {
  expected_month: number
  idempotency_key: string
  policy_code: string
  params: PolicyParams
}

export interface RunNextMonthResponse {
  replayed: boolean
  executed_month: number
  session: OfficialSimulationSession
}

export interface StructuredApiErrorDetail {
  code: string
  message: string
  context?: Record<string, unknown>
}

export interface LeaderboardEntry {
  rank: number
  nickname: string
  completed_months: number
  cumulative_revenue: number
  last_activity: string | null
  is_current_user: boolean
}

export interface LeaderboardResponse {
  stage: number
  current_user_eligible: boolean | null
  items: LeaderboardEntry[]
}
