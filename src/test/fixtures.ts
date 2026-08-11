import type {
  OfficialMonthlyResult,
  OfficialSimulationSession,
} from '../types/simulation'

export function officialMonth(
  month: number,
  overrides: Partial<OfficialMonthlyResult> = {},
): OfficialMonthlyResult {
  return {
    month,
    policy_code: `def admission_policy(request, state, history, params):\n    return ${month}`,
    params: { threshold: month },
    policy_hash: `hash-${month}`,
    total_requests: 100 + month,
    admitted_requests: 80,
    completed_requests: 70,
    rejected_requests: 21,
    total_revenue: 1000 * month,
    unfinished_requests: 10,
    unfinished_value: 250,
    avg_utilization: { '1': 0.5 },
    peak_utilization: { '1': 0.8 },
    by_type: [{
      type: 'VIP',
      total_revenue: 500,
    }],
    warnings: [],
    benchmark_comparison: [],
    completed_at: `2026-0${Math.min(month, 9)}-01T12:00:00Z`,
    ...overrides,
  }
}

export function officialSession(
  completedMonths = 0,
  overrides: Partial<OfficialSimulationSession> = {},
): OfficialSimulationSession {
  const monthlyResults = Array.from(
    { length: completedMonths },
    (_, index) => officialMonth(index + 1),
  )
  return {
    session_id: '11111111-1111-4111-8111-111111111111',
    completed_months: completedMonths,
    next_month: completedMonths < 12 ? completedMonths + 1 : null,
    status: completedMonths === 0
      ? 'not_started'
      : completedMonths === 12
        ? 'completed'
        : 'in_progress',
    cumulative: {
      total_requests: monthlyResults.reduce((sum, row) => sum + row.total_requests, 0),
      admitted_requests: monthlyResults.reduce((sum, row) => sum + row.admitted_requests, 0),
      completed_requests: monthlyResults.reduce((sum, row) => sum + row.completed_requests, 0),
      rejected_requests: monthlyResults.reduce((sum, row) => sum + row.rejected_requests, 0),
      total_revenue: monthlyResults.reduce((sum, row) => sum + row.total_revenue, 0),
      total_unfinished_requests: monthlyResults.reduce((sum, row) => sum + row.unfinished_requests, 0),
      total_unfinished_value: monthlyResults.reduce((sum, row) => sum + row.unfinished_value, 0),
      warnings_count: monthlyResults.reduce((sum, row) => sum + row.warnings.length, 0),
      by_type: [],
      benchmark_comparison: [],
    },
    monthly_results: monthlyResults,
    latest_policy: monthlyResults.length > 0
      ? {
          policy_code: monthlyResults.at(-1)!.policy_code,
          params: monthlyResults.at(-1)!.params,
          policy_hash: monthlyResults.at(-1)!.policy_hash,
        }
      : null,
    ...overrides,
  }
}
