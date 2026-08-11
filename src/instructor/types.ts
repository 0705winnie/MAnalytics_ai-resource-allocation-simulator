export interface InstructorCourse {
  id: string
  course_code: string
  course_name: string
  semester: string
  course_identifier: string
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface InstructorCourseListResponse {
  items: InstructorCourse[]
  total: number
  offset: number
  limit: number
}

export interface CreateInstructorCourseRequest {
  course_code: string
  course_name: string
  semester: string
}

export interface RosterImportSummary {
  processed: number
  created: number
  already_enrolled: number
  duplicate_input: number
  invalid: number
  conflicts: number
}

export interface RosterImportResult {
  csv: Blob
  summary: RosterImportSummary
}

export type EnrollmentActivationFilter = 'pending' | 'activated'
export type InstructorEnrollmentStatus = 'pending' | 'active' | 'disabled'

export interface InstructorEnrollment {
  enrollment_id: string
  berkeley_username: string
  nickname: string | null
  status: InstructorEnrollmentStatus
  user_is_active: boolean
  activated: boolean
  activation_expires_at: string | null
  activation_used_at: string | null
  created_at: string
}

export interface InstructorEnrollmentListResponse {
  items: InstructorEnrollment[]
  total: number
  offset: number
  limit: number
}

export interface InstructorEnrollmentListQuery {
  offset: number
  limit: number
  search?: string
  activation_status?: EnrollmentActivationFilter
}

export interface ActivationCodeReissueResult {
  csv: Blob
}

export interface StudentProgress {
  enrollment_id: string
  berkeley_username: string
  nickname: string | null
  enrollment_status: InstructorEnrollmentStatus
  user_is_active: boolean
  completed_months: number
  cumulative_revenue: number
  last_activity: string | null
  simulation_status: 'not_started' | 'in_progress' | 'completed'
  warnings_count: number
}

export interface InstructorLeaderboardEntry {
  rank: number
  nickname: string
  completed_months: number
  cumulative_revenue: number
  last_activity: string | null
  is_current_user: boolean
}

export interface InstructorLeaderboardResponse {
  stage: number
  current_user_eligible: boolean | null
  items: InstructorLeaderboardEntry[]
}

export interface StudentProgressListResponse {
  items: StudentProgress[]
  total: number
  offset: number
  limit: number
}
