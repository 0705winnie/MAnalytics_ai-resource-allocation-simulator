export interface MonthSummary {
  month: number
  total_requests: number
  completed_requests: number
  total_revenue: number
  avg_required_units: number
  avg_duration: number
}

export interface MonthTypeSummary {
  month: number
  type: 'VIP' | 'standard' | 'economy'
  total_requests: number
  completed_requests: number
  total_revenue: number
  avg_required_units: number
  avg_duration: number
}

export interface TypeSummary {
  type: 'VIP' | 'standard' | 'economy'
  total_requests: number
  completed_requests: number
  completion_rate: number
  total_revenue: number
  avg_revenue: number
  avg_required_units: number
  avg_duration: number
}

// Monthly totals from data/generated/summary_by_month.csv
export const byMonth: MonthSummary[] = [
  { month: 1, total_requests: 804, completed_requests: 672, total_revenue: 40114, avg_required_units: 7.23, avg_duration: 13.22 },
  { month: 2, total_requests: 803, completed_requests: 693, total_revenue: 39810, avg_required_units: 7.1, avg_duration: 14.17 },
  { month: 3, total_requests: 879, completed_requests: 759, total_revenue: 45516, avg_required_units: 7.24, avg_duration: 12.65 },
  { month: 4, total_requests: 973, completed_requests: 824, total_revenue: 51692, avg_required_units: 7.42, avg_duration: 13.83 },
  { month: 5, total_requests: 961, completed_requests: 820, total_revenue: 51552, avg_required_units: 7.39, avg_duration: 13.24 },
  { month: 6, total_requests: 1070, completed_requests: 898, total_revenue: 58814, avg_required_units: 7.48, avg_duration: 13.23 },
  { month: 7, total_requests: 1208, completed_requests: 1040, total_revenue: 73572, avg_required_units: 7.74, avg_duration: 12.34 },
  { month: 8, total_requests: 1172, completed_requests: 993, total_revenue: 66654, avg_required_units: 7.65, avg_duration: 12.7 },
  { month: 9, total_requests: 983, completed_requests: 845, total_revenue: 50730, avg_required_units: 7.36, avg_duration: 13.48 },
  { month: 10, total_requests: 894, completed_requests: 730, total_revenue: 44278, avg_required_units: 7.3, avg_duration: 13.63 },
  { month: 11, total_requests: 1077, completed_requests: 911, total_revenue: 57856, avg_required_units: 7.47, avg_duration: 12.87 },
  { month: 12, total_requests: 1221, completed_requests: 1025, total_revenue: 71438, avg_required_units: 7.72, avg_duration: 13.1 },
]

// Monthly breakdown by type from data/generated/summary_by_month_type.csv
export const byMonthType: MonthTypeSummary[] = [
  { month: 1, type: 'VIP', total_requests: 76, completed_requests: 74, total_revenue: 14014, avg_required_units: 13.53, avg_duration: 5.24 },
  { month: 1, type: 'economy', total_requests: 371, completed_requests: 281, total_revenue: 6028, avg_required_units: 5.29, avg_duration: 19.29 },
  { month: 1, type: 'standard', total_requests: 357, completed_requests: 317, total_revenue: 20072, avg_required_units: 7.92, avg_duration: 8.61 },
  { month: 2, type: 'VIP', total_requests: 73, completed_requests: 68, total_revenue: 12950, avg_required_units: 13.47, avg_duration: 5.31 },
  { month: 2, type: 'economy', total_requests: 347, completed_requests: 277, total_revenue: 5796, avg_required_units: 5.25, avg_duration: 21.11 },
  { month: 2, type: 'standard', total_requests: 383, completed_requests: 348, total_revenue: 21064, avg_required_units: 7.56, avg_duration: 9.57 },
  { month: 3, type: 'VIP', total_requests: 78, completed_requests: 75, total_revenue: 14616, avg_required_units: 13.82, avg_duration: 5.46 },
  { month: 3, type: 'economy', total_requests: 355, completed_requests: 277, total_revenue: 5964, avg_required_units: 5.26, avg_duration: 19.08 },
  { month: 3, type: 'standard', total_requests: 446, completed_requests: 407, total_revenue: 24936, avg_required_units: 7.65, avg_duration: 8.78 },
  { month: 4, type: 'VIP', total_requests: 110, completed_requests: 105, total_revenue: 19908, avg_required_units: 13.49, avg_duration: 5.5 },
  { month: 4, type: 'economy', total_requests: 403, completed_requests: 316, total_revenue: 6720, avg_required_units: 5.36, avg_duration: 21.18 },
  { month: 4, type: 'standard', total_requests: 460, completed_requests: 403, total_revenue: 25064, avg_required_units: 7.78, avg_duration: 9.38 },
  { month: 5, type: 'VIP', total_requests: 112, completed_requests: 108, total_revenue: 20748, avg_required_units: 13.71, avg_duration: 5.6 },
  { month: 5, type: 'economy', total_requests: 404, completed_requests: 321, total_revenue: 6788, avg_required_units: 5.28, avg_duration: 20.21 },
  { month: 5, type: 'standard', total_requests: 445, completed_requests: 391, total_revenue: 24016, avg_required_units: 7.7, avg_duration: 8.83 },
  { month: 6, type: 'VIP', total_requests: 126, completed_requests: 125, total_revenue: 23758, avg_required_units: 13.59, avg_duration: 5.4 },
  { month: 6, type: 'economy', total_requests: 435, completed_requests: 316, total_revenue: 6888, avg_required_units: 5.42, avg_duration: 19.64 },
  { month: 6, type: 'standard', total_requests: 509, completed_requests: 457, total_revenue: 28168, avg_required_units: 7.73, avg_duration: 9.69 },
  { month: 7, type: 'VIP', total_requests: 188, completed_requests: 179, total_revenue: 33628, avg_required_units: 13.44, avg_duration: 5.92 },
  { month: 7, type: 'economy', total_requests: 420, completed_requests: 324, total_revenue: 6824, avg_required_units: 5.23, avg_duration: 20.01 },
  { month: 7, type: 'standard', total_requests: 600, completed_requests: 537, total_revenue: 33120, avg_required_units: 7.71, avg_duration: 8.99 },
  { month: 8, type: 'VIP', total_requests: 146, completed_requests: 143, total_revenue: 27818, avg_required_units: 13.94, avg_duration: 4.63 },
  { month: 8, type: 'economy', total_requests: 466, completed_requests: 355, total_revenue: 7580, avg_required_units: 5.36, avg_duration: 19.76 },
  { month: 8, type: 'standard', total_requests: 560, completed_requests: 495, total_revenue: 31256, avg_required_units: 7.91, avg_duration: 8.92 },
  { month: 9, type: 'VIP', total_requests: 95, completed_requests: 89, total_revenue: 17290, avg_required_units: 13.92, avg_duration: 5.16 },
  { month: 9, type: 'economy', total_requests: 413, completed_requests: 332, total_revenue: 6976, avg_required_units: 5.31, avg_duration: 20.26 },
  { month: 9, type: 'standard', total_requests: 475, completed_requests: 424, total_revenue: 26464, avg_required_units: 7.82, avg_duration: 9.25 },
  { month: 10, type: 'VIP', total_requests: 80, completed_requests: 76, total_revenue: 15414, avg_required_units: 14.55, avg_duration: 4.83 },
  { month: 10, type: 'economy', total_requests: 391, completed_requests: 290, total_revenue: 6056, avg_required_units: 5.19, avg_duration: 20.31 },
  { month: 10, type: 'standard', total_requests: 423, completed_requests: 364, total_revenue: 22808, avg_required_units: 7.87, avg_duration: 9.12 },
  { month: 11, type: 'VIP', total_requests: 110, completed_requests: 108, total_revenue: 20468, avg_required_units: 13.51, avg_duration: 4.46 },
  { month: 11, type: 'economy', total_requests: 422, completed_requests: 313, total_revenue: 6908, avg_required_units: 5.47, avg_duration: 20.14 },
  { month: 11, type: 'standard', total_requests: 545, completed_requests: 490, total_revenue: 30480, avg_required_units: 7.79, avg_duration: 8.94 },
  { month: 12, type: 'VIP', total_requests: 161, completed_requests: 155, total_revenue: 30422, avg_required_units: 14.07, avg_duration: 5.18 },
  { month: 12, type: 'economy', total_requests: 468, completed_requests: 342, total_revenue: 7240, avg_required_units: 5.19, avg_duration: 20.59 },
  { month: 12, type: 'standard', total_requests: 592, completed_requests: 528, total_revenue: 33776, avg_required_units: 7.98, avg_duration: 9.33 },
]

// Per-type totals from data/generated/summary_by_type.csv
export const byType: TypeSummary[] = [
  { type: 'VIP', total_requests: 1355, completed_requests: 1305, completion_rate: 0.963, total_revenue: 251034, avg_revenue: 185.26, avg_required_units: 13.74, avg_duration: 5.25 },
  { type: 'economy', total_requests: 4895, completed_requests: 3744, completion_rate: 0.765, total_revenue: 79768, avg_revenue: 16.3, avg_required_units: 5.3, avg_duration: 20.13 },
  { type: 'standard', total_requests: 5795, completed_requests: 5161, completion_rate: 0.891, total_revenue: 321224, avg_revenue: 55.43, avg_required_units: 7.79, avg_duration: 9.12 },
]

// Pre-pivoted for Recharts grouped bar chart: one row per month, columns by request type
export const monthlyTypeBreakdown = byMonth.map((m) => {
  const rows = byMonthType.filter((r) => r.month === m.month)
  const get = (t: MonthTypeSummary['type']) =>
    rows.find((r) => r.type === t)?.total_requests ?? 0
  return {
    month: m.month,
    VIP: get('VIP'),
    Standard: get('standard'),
    Economy: get('economy'),
  }
})
