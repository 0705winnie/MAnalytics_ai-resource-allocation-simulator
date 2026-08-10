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

export interface SimulationResponse {
  monthly: SimulationMonthResult[]
  by_type: SimulationTypeResult[]
  total_revenue: number
  total_unfinished_requests: number
  total_unfinished_value: number
  warnings: string[]
  benchmark_comparison: BenchmarkResult[]
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

export interface SimulateRequest {
  policy_code: string
  params: PolicyParams
  // No `seed` field: the backend rejects it (422) and always tests policies
  // against its own DEFAULT_SEED so every run is fair and comparable.
}

// Response shape for POST /simulate/month — one month's full detail,
// including the pieces the full-year SimulationMonthResult doesn't carry
// (this month's own by_type breakdown, warnings, and end-of-month capacity).
export interface MonthDetailResult extends SimulationMonthResult {
  by_type: SimulationTypeResult[]
  warnings: string[]
  benchmark_comparison: BenchmarkResult[]
  // Keyed by cluster id; JSON object keys arrive as strings.
  remaining_capacity: Record<string, number>
}

export interface SimulateMonthRequest {
  month: number
  policy_code: string
  params: PolicyParams
  // Prior completed months, echoed back from earlier /simulate/month
  // responses, so the policy's `history["previous_months"]` isn't always
  // empty — the backend has no session storage, so the client (which
  // already holds these) is the source of truth here.
  previous_months: MonthDetailResult[]
  // No `seed` field, same reasoning as SimulateRequest above.
}

// POST /submissions — separate, authenticated from POST /simulate. The
// server independently recomputes the result from policy_code + params
// rather than trusting any client-supplied numbers, so this request only
// carries the inputs.
export interface SubmitResultRequest {
  policy_code: string
  params: PolicyParams
}

export interface SubmitResultResponse {
  id: string
  total_revenue: number
  total_unfinished_requests: number
  total_unfinished_value: number
  warnings_count: number
  submitted_at: string
}
