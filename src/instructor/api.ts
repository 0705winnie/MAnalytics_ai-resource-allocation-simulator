import type {
  CreateInstructorCourseRequest,
  InstructorCourse,
  InstructorCourseListResponse,
} from './types'

export type InstructorCourseApiErrorCode =
  | 'invalid_input'
  | 'unauthorized'
  | 'forbidden'
  | 'not_found'
  | 'conflict'
  | 'unavailable'

export class InstructorCourseApiError extends Error {
  readonly code: InstructorCourseApiErrorCode

  constructor(code: InstructorCourseApiErrorCode) {
    super(code)
    this.name = 'InstructorCourseApiError'
    this.code = code
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function isUuid(value: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i
    .test(value)
}

function isIsoTimestamp(value: string): boolean {
  return value.length > 0 && Number.isFinite(Date.parse(value))
}

function parseInstructorCourse(value: unknown): InstructorCourse {
  if (
    !isRecord(value)
    || typeof value.id !== 'string'
    || !isUuid(value.id)
    || typeof value.course_code !== 'string'
    || value.course_code.length === 0
    || typeof value.course_name !== 'string'
    || value.course_name.length === 0
    || typeof value.semester !== 'string'
    || value.semester.length === 0
    || typeof value.is_active !== 'boolean'
    || typeof value.created_at !== 'string'
    || !isIsoTimestamp(value.created_at)
    || typeof value.updated_at !== 'string'
    || !isIsoTimestamp(value.updated_at)
  ) {
    throw new InstructorCourseApiError('unavailable')
  }

  return {
    id: value.id,
    course_code: value.course_code,
    course_name: value.course_name,
    semester: value.semester,
    is_active: value.is_active,
    created_at: value.created_at,
    updated_at: value.updated_at,
  }
}

function parseCourseList(value: unknown): InstructorCourseListResponse {
  if (
    !isRecord(value)
    || !Array.isArray(value.items)
    || !Number.isInteger(value.total)
    || (value.total as number) < 0
    || !Number.isInteger(value.offset)
    || (value.offset as number) < 0
    || !Number.isInteger(value.limit)
    || (value.limit as number) < 1
  ) {
    throw new InstructorCourseApiError('unavailable')
  }

  const items = value.items.map(parseInstructorCourse)
  if (
    items.length > (value.limit as number)
    || items.length > (value.total as number)
  ) {
    throw new InstructorCourseApiError('unavailable')
  }

  return {
    items,
    total: value.total as number,
    offset: value.offset as number,
    limit: value.limit as number,
  }
}

async function safeJson(response: Response): Promise<unknown> {
  try {
    return await response.json()
  } catch {
    throw new InstructorCourseApiError('unavailable')
  }
}

function throwForCourseResponse(response: Response): void {
  if (response.status === 401) {
    throw new InstructorCourseApiError('unauthorized')
  }
  if (response.status === 403) {
    throw new InstructorCourseApiError('forbidden')
  }
  if (response.status === 404) {
    throw new InstructorCourseApiError('not_found')
  }
  if (response.status === 409) {
    throw new InstructorCourseApiError('conflict')
  }
  if (response.status === 400 || response.status === 422) {
    throw new InstructorCourseApiError('invalid_input')
  }
  if (!response.ok) {
    throw new InstructorCourseApiError('unavailable')
  }
}

function unavailableUnlessAborted(error: unknown): never {
  if (error instanceof DOMException && error.name === 'AbortError') {
    throw error
  }
  if (error instanceof InstructorCourseApiError) {
    throw error
  }
  throw new InstructorCourseApiError('unavailable')
}

export async function getInstructorCourses(
  signal?: AbortSignal,
): Promise<InstructorCourseListResponse> {
  try {
    const response = await fetch('/api/instructor/courses?offset=0&limit=100', {
      credentials: 'include',
      signal,
    })
    throwForCourseResponse(response)
    return parseCourseList(await safeJson(response))
  } catch (error) {
    return unavailableUnlessAborted(error)
  }
}

export async function getInstructorCourse(
  courseId: string,
  signal?: AbortSignal,
): Promise<InstructorCourse> {
  try {
    const response = await fetch(
      `/api/instructor/courses/${encodeURIComponent(courseId)}`,
      {
        credentials: 'include',
        signal,
      },
    )
    throwForCourseResponse(response)
    return parseInstructorCourse(await safeJson(response))
  } catch (error) {
    return unavailableUnlessAborted(error)
  }
}

export async function createInstructorCourse(
  request: CreateInstructorCourseRequest,
): Promise<InstructorCourse> {
  try {
    const response = await fetch('/api/instructor/courses', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify(request),
    })
    throwForCourseResponse(response)
    return parseInstructorCourse(await safeJson(response))
  } catch (error) {
    return unavailableUnlessAborted(error)
  }
}
