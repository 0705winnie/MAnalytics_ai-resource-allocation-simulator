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
  warnings: string[]
}

export interface SimulateRequest {
  policy_code: string
  params: PolicyParams
  seed?: number
}
