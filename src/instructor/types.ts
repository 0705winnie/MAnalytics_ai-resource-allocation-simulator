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
