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

// Monthly totals (12 rows) — from data/generated/summary_by_month.csv
export const byMonth: MonthSummary[] = [
  { month: 1,  total_requests: 780,  completed_requests: 695,  total_revenue: 33486, avg_required_units: 6.09, avg_duration: 6.66 },
  { month: 2,  total_requests: 762,  completed_requests: 688,  total_revenue: 32548, avg_required_units: 5.95, avg_duration: 7.09 },
  { month: 3,  total_requests: 881,  completed_requests: 797,  total_revenue: 37400, avg_required_units: 5.99, avg_duration: 6.45 },
  { month: 4,  total_requests: 877,  completed_requests: 774,  total_revenue: 38388, avg_required_units: 6.09, avg_duration: 7.24 },
  { month: 5,  total_requests: 965,  completed_requests: 860,  total_revenue: 40650, avg_required_units: 6.03, avg_duration: 6.78 },
  { month: 6,  total_requests: 1078, completed_requests: 964,  total_revenue: 44580, avg_required_units: 6.01, avg_duration: 6.94 },
  { month: 7,  total_requests: 1154, completed_requests: 1027, total_revenue: 47394, avg_required_units: 5.94, avg_duration: 6.44 },
  { month: 8,  total_requests: 1104, completed_requests: 982,  total_revenue: 49096, avg_required_units: 6.24, avg_duration: 6.58 },
  { month: 9,  total_requests: 953,  completed_requests: 858,  total_revenue: 40978, avg_required_units: 6.04, avg_duration: 6.83 },
  { month: 10, total_requests: 851,  completed_requests: 764,  total_revenue: 35700, avg_required_units: 5.95, avg_duration: 6.65 },
  { month: 11, total_requests: 988,  completed_requests: 884,  total_revenue: 41034, avg_required_units: 5.93, avg_duration: 6.93 },
  { month: 12, total_requests: 1092, completed_requests: 972,  total_revenue: 44818, avg_required_units: 5.97, avg_duration: 6.80 },
]

// Monthly breakdown by type (36 rows) — from data/generated/summary_by_month_type.csv
export const byMonthType: MonthTypeSummary[] = [
  { month: 1,  type: 'VIP',      total_requests: 111, completed_requests: 106, total_revenue: 13752, avg_required_units: 10.77, avg_duration: 4.06 },
  { month: 1,  type: 'economy',  total_requests: 268, completed_requests: 235, total_revenue: 3032,  avg_required_units: 3.21,  avg_duration: 8.92 },
  { month: 1,  type: 'standard', total_requests: 401, completed_requests: 354, total_revenue: 16702, avg_required_units: 6.73,  avg_duration: 5.87 },
  { month: 2,  type: 'VIP',      total_requests: 109, completed_requests: 106, total_revenue: 13500, avg_required_units: 10.58, avg_duration: 3.55 },
  { month: 2,  type: 'economy',  total_requests: 265, completed_requests: 228, total_revenue: 2976,  avg_required_units: 3.31,  avg_duration: 9.50 },
  { month: 2,  type: 'standard', total_requests: 388, completed_requests: 354, total_revenue: 16072, avg_required_units: 6.46,  avg_duration: 6.44 },
  { month: 3,  type: 'VIP',      total_requests: 118, completed_requests: 111, total_revenue: 14436, avg_required_units: 10.88, avg_duration: 3.80 },
  { month: 3,  type: 'economy',  total_requests: 290, completed_requests: 251, total_revenue: 3196,  avg_required_units: 3.16,  avg_duration: 8.69 },
  { month: 3,  type: 'standard', total_requests: 473, completed_requests: 435, total_revenue: 19768, avg_required_units: 6.51,  avg_duration: 5.74 },
  { month: 4,  type: 'VIP',      total_requests: 133, completed_requests: 127, total_revenue: 17208, avg_required_units: 11.26, avg_duration: 3.94 },
  { month: 4,  type: 'economy',  total_requests: 317, completed_requests: 261, total_revenue: 3288,  avg_required_units: 3.19,  avg_duration: 9.67 },
  { month: 4,  type: 'standard', total_requests: 427, completed_requests: 386, total_revenue: 17892, avg_required_units: 6.64,  avg_duration: 6.46 },
  { month: 5,  type: 'VIP',      total_requests: 122, completed_requests: 120, total_revenue: 15636, avg_required_units: 10.88, avg_duration: 4.14 },
  { month: 5,  type: 'economy',  total_requests: 332, completed_requests: 284, total_revenue: 3748,  avg_required_units: 3.26,  avg_duration: 8.75 },
  { month: 5,  type: 'standard', total_requests: 511, completed_requests: 456, total_revenue: 21266, avg_required_units: 6.67,  avg_duration: 6.13 },
  { month: 6,  type: 'VIP',      total_requests: 134, completed_requests: 126, total_revenue: 16164, avg_required_units: 10.72, avg_duration: 4.20 },
  { month: 6,  type: 'economy',  total_requests: 366, completed_requests: 315, total_revenue: 4196,  avg_required_units: 3.34,  avg_duration: 8.85 },
  { month: 6,  type: 'standard', total_requests: 578, completed_requests: 523, total_revenue: 24220, avg_required_units: 6.62,  avg_duration: 6.36 },
  { month: 7,  type: 'VIP',      total_requests: 145, completed_requests: 135, total_revenue: 17688, avg_required_units: 10.89, avg_duration: 4.10 },
  { month: 7,  type: 'economy',  total_requests: 402, completed_requests: 343, total_revenue: 4296,  avg_required_units: 3.13,  avg_duration: 8.24 },
  { month: 7,  type: 'standard', total_requests: 607, completed_requests: 549, total_revenue: 25410, avg_required_units: 6.62,  avg_duration: 5.80 },
  { month: 8,  type: 'VIP',      total_requests: 167, completed_requests: 156, total_revenue: 20664, avg_required_units: 11.03, avg_duration: 4.11 },
  { month: 8,  type: 'economy',  total_requests: 347, completed_requests: 291, total_revenue: 3736,  avg_required_units: 3.25,  avg_duration: 8.79 },
  { month: 8,  type: 'standard', total_requests: 590, completed_requests: 535, total_revenue: 24696, avg_required_units: 6.64,  avg_duration: 5.99 },
  { month: 9,  type: 'VIP',      total_requests: 134, completed_requests: 127, total_revenue: 16764, avg_required_units: 10.96, avg_duration: 3.71 },
  { month: 9,  type: 'economy',  total_requests: 339, completed_requests: 289, total_revenue: 3732,  avg_required_units: 3.25,  avg_duration: 9.15 },
  { month: 9,  type: 'standard', total_requests: 480, completed_requests: 442, total_revenue: 20482, avg_required_units: 6.63,  avg_duration: 6.06 },
  { month: 10, type: 'VIP',      total_requests: 112, completed_requests: 109, total_revenue: 14244, avg_required_units: 10.87, avg_duration: 4.32 },
  { month: 10, type: 'economy',  total_requests: 302, completed_requests: 260, total_revenue: 3368,  avg_required_units: 3.25,  avg_duration: 8.67 },
  { month: 10, type: 'standard', total_requests: 437, completed_requests: 395, total_revenue: 18088, avg_required_units: 6.55,  avg_duration: 5.85 },
  { month: 11, type: 'VIP',      total_requests: 128, completed_requests: 124, total_revenue: 16116, avg_required_units: 10.84, avg_duration: 4.43 },
  { month: 11, type: 'economy',  total_requests: 359, completed_requests: 306, total_revenue: 3876,  avg_required_units: 3.18,  avg_duration: 9.16 },
  { month: 11, type: 'standard', total_requests: 501, completed_requests: 454, total_revenue: 21042, avg_required_units: 6.65,  avg_duration: 5.97 },
  { month: 12, type: 'VIP',      total_requests: 131, completed_requests: 122, total_revenue: 16476, avg_required_units: 11.18, avg_duration: 4.04 },
  { month: 12, type: 'economy',  total_requests: 382, completed_requests: 325, total_revenue: 4164,  avg_required_units: 3.26,  avg_duration: 9.18 },
  { month: 12, type: 'standard', total_requests: 579, completed_requests: 525, total_revenue: 24178, avg_required_units: 6.57,  avg_duration: 5.85 },
]

// Per-type totals (3 rows) — from data/generated/summary_by_type.csv
export const byType: TypeSummary[] = [
  { type: 'VIP',      total_requests: 1544, completed_requests: 1469, completion_rate: 0.951, total_revenue: 192648, avg_revenue: 124.77, avg_required_units: 10.92, avg_duration: 4.04 },
  { type: 'standard', total_requests: 5972, completed_requests: 5408, completion_rate: 0.906, total_revenue: 249816, avg_revenue:  41.83, avg_required_units:  6.61, avg_duration: 6.03 },
  { type: 'economy',  total_requests: 3969, completed_requests: 3388, completion_rate: 0.854, total_revenue:  43608, avg_revenue:  10.99, avg_required_units:  3.23, avg_duration: 8.95 },
]

// Pre-pivoted for Recharts grouped bar chart — one row per month, columns: VIP / Standard / Economy
export const monthlyTypeBreakdown = byMonth.map((m) => {
  const rows = byMonthType.filter((r) => r.month === m.month)
  const get = (t: MonthTypeSummary['type']) =>
    rows.find((r) => r.type === t)?.total_requests ?? 0
  return {
    month:    m.month,
    VIP:      get('VIP'),
    Standard: get('standard'),
    Economy:  get('economy'),
  }
})
