export interface InstructorCourse {
  id: string
  course_code: string
  course_name: string
  semester: string
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
