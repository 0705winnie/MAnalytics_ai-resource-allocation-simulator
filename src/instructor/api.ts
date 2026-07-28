import type {
  ActivationCodeReissueResult,
  CreateInstructorCourseRequest,
  InstructorEnrollment,
  InstructorEnrollmentListQuery,
  InstructorEnrollmentListResponse,
  InstructorCourse,
  InstructorCourseListResponse,
  RosterImportResult,
  RosterImportSummary,
} from './types'

export type InstructorCourseApiErrorCode =
  | 'invalid_input'
  | 'file_too_large'
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
  if (response.status === 413) {
    throw new InstructorCourseApiError('file_too_large')
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

export const MAX_ROSTER_FILE_BYTES = 1024 * 1024
const MAX_ROSTER_ROWS = 1000
const MAX_ROSTER_RESPONSE_BYTES = 2 * 1024 * 1024
const ROSTER_DOWNLOAD_FILENAME = 'roster-activation-codes.csv'
const ROSTER_HEADER = [
  'berkeley_username',
  'course_code',
  'activation_code',
  'status',
  'message',
] as const
const ROSTER_STATUSES = new Set([
  'created',
  'already_enrolled',
  'duplicate_input',
  'invalid',
  'role_conflict',
  'user_inactive',
])
const ACTIVATION_CODE_PATTERN = /^[A-Z2-9]{4}(?:-[A-Z2-9]{4}){2}$/
const FORMULA_PREFIX_PATTERN = /^[=+\-@]/
const USERNAME_PATTERN = /^[a-z0-9][a-z0-9._-]{0,63}$/
const ENROLLMENT_STATUSES = new Set(['pending', 'active', 'disabled'])

function parseNonnegativeCount(response: Response, name: string): number {
  const value = response.headers.get(name)
  if (value === null || !/^(?:0|[1-9]\d*)$/.test(value)) {
    throw new InstructorCourseApiError('unavailable')
  }
  const parsed = Number(value)
  if (!Number.isSafeInteger(parsed) || parsed > MAX_ROSTER_ROWS) {
    throw new InstructorCourseApiError('unavailable')
  }
  return parsed
}

function parseCsvRecords(text: string): string[][] {
  const records: string[][] = []
  let record: string[] = []
  let field = ''
  let inQuotes = false
  let afterQuote = false

  function finishField() {
    record.push(field)
    field = ''
    afterQuote = false
  }

  function finishRecord() {
    finishField()
    records.push(record)
    record = []
  }

  for (let index = 0; index < text.length; index += 1) {
    const character = text[index]
    if (inQuotes) {
      if (character === '"') {
        if (text[index + 1] === '"') {
          field += '"'
          index += 1
        } else {
          inQuotes = false
          afterQuote = true
        }
      } else {
        field += character
      }
      continue
    }

    if (afterQuote && character !== ',' && character !== '\r' && character !== '\n') {
      throw new InstructorCourseApiError('unavailable')
    }
    if (character === '"' && field.length === 0 && !afterQuote) {
      inQuotes = true
    } else if (character === '"') {
      throw new InstructorCourseApiError('unavailable')
    } else if (character === ',') {
      finishField()
    } else if (character === '\r' || character === '\n') {
      if (character === '\r' && text[index + 1] === '\n') {
        index += 1
      }
      finishRecord()
    } else {
      field += character
    }
  }

  if (inQuotes) {
    throw new InstructorCourseApiError('unavailable')
  }
  if (field || record.length > 0 || afterQuote) {
    finishRecord()
  }
  return records
}

function spreadsheetSafeValue(value: string): string {
  return FORMULA_PREFIX_PATTERN.test(value) ? `'${value}` : value
}

function validateRosterCsv(
  text: string,
  expectedCourseCode: string,
  headerSummary: Omit<RosterImportSummary, 'processed' | 'duplicate_input'>,
): RosterImportSummary {
  const records = parseCsvRecords(text)
  const header = records.shift()
  if (
    !header
    || header.length !== ROSTER_HEADER.length
    || header.some((value, index) => value !== ROSTER_HEADER[index])
    || records.length < 1
    || records.length > MAX_ROSTER_ROWS
  ) {
    throw new InstructorCourseApiError('unavailable')
  }

  const statusCounts = {
    created: 0,
    already_enrolled: 0,
    duplicate_input: 0,
    invalid: 0,
    role_conflict: 0,
    user_inactive: 0,
  }
  const safeCourseCode = spreadsheetSafeValue(expectedCourseCode)

  for (const record of records) {
    if (
      record.length !== ROSTER_HEADER.length
      || !record[0]
      || record[1] !== safeCourseCode
      || !ROSTER_STATUSES.has(record[3])
      || !record[4]
      || [record[0], record[1], record[3], record[4]]
        .some((value) => FORMULA_PREFIX_PATTERN.test(value))
    ) {
      throw new InstructorCourseApiError('unavailable')
    }

    const status = record[3] as keyof typeof statusCounts
    statusCounts[status] += 1
    if (
      (status === 'created' && !ACTIVATION_CODE_PATTERN.test(record[2]))
      || (status !== 'created' && record[2] !== '')
    ) {
      throw new InstructorCourseApiError('unavailable')
    }
  }

  const conflicts = statusCounts.role_conflict + statusCounts.user_inactive
  if (
    headerSummary.created !== statusCounts.created
    || headerSummary.already_enrolled !== statusCounts.already_enrolled
    || headerSummary.invalid !== statusCounts.invalid
    || headerSummary.conflicts !== conflicts
  ) {
    throw new InstructorCourseApiError('unavailable')
  }

  return {
    processed: records.length,
    created: statusCounts.created,
    already_enrolled: statusCounts.already_enrolled,
    duplicate_input: statusCounts.duplicate_input,
    invalid: statusCounts.invalid,
    conflicts,
  }
}

async function parseRosterImportResponse(
  response: Response,
  expectedCourseCode: string,
): Promise<RosterImportResult> {
  const contentType = response.headers.get('content-type')?.toLowerCase() ?? ''
  const disposition = response.headers.get('content-disposition')
  const cacheControl = response.headers.get('cache-control')?.toLowerCase() ?? ''
  const pragma = response.headers.get('pragma')?.toLowerCase() ?? ''
  if (
    !contentType.startsWith('text/csv')
    || disposition !== `attachment; filename="${ROSTER_DOWNLOAD_FILENAME}"`
    || !cacheControl.includes('no-store')
    || pragma !== 'no-cache'
  ) {
    throw new InstructorCourseApiError('unavailable')
  }

  const headerSummary = {
    created: parseNonnegativeCount(response, 'x-roster-created'),
    already_enrolled: parseNonnegativeCount(
      response,
      'x-roster-already-enrolled',
    ),
    invalid: parseNonnegativeCount(response, 'x-roster-invalid'),
    conflicts: parseNonnegativeCount(response, 'x-roster-conflicts'),
  }
  const bytes = await response.arrayBuffer()
  if (bytes.byteLength === 0 || bytes.byteLength > MAX_ROSTER_RESPONSE_BYTES) {
    throw new InstructorCourseApiError('unavailable')
  }

  let text: string
  try {
    text = new TextDecoder('utf-8', { fatal: true }).decode(bytes)
  } catch {
    throw new InstructorCourseApiError('unavailable')
  }
  const summary = validateRosterCsv(text, expectedCourseCode, headerSummary)
  return {
    csv: new Blob([bytes], { type: 'text/csv;charset=utf-8' }),
    summary,
  }
}

export async function importInstructorRoster(
  course: InstructorCourse,
  file: File,
): Promise<RosterImportResult> {
  if (file.size > MAX_ROSTER_FILE_BYTES) {
    throw new InstructorCourseApiError('file_too_large')
  }

  const body = new FormData()
  body.append('file', file)
  try {
    const response = await fetch(
      `/api/instructor/courses/${encodeURIComponent(course.id)}/roster/import`,
      {
        method: 'POST',
        credentials: 'include',
        body,
      },
    )
    throwForCourseResponse(response)
    return await parseRosterImportResponse(response, course.course_code)
  } catch (error) {
    return unavailableUnlessAborted(error)
  }
}

function isNullableTimestamp(value: unknown): value is string | null {
  return value === null || (typeof value === 'string' && isIsoTimestamp(value))
}

function parseInstructorEnrollment(value: unknown): InstructorEnrollment {
  if (
    !isRecord(value)
    || 'password_hash' in value
    || 'activation_code_hash' in value
    || 'user_id' in value
    || typeof value.enrollment_id !== 'string'
    || !isUuid(value.enrollment_id)
    || typeof value.berkeley_username !== 'string'
    || !USERNAME_PATTERN.test(value.berkeley_username)
    || (
      value.nickname !== null
      && (
        typeof value.nickname !== 'string'
        || value.nickname.length < 3
        || value.nickname.length > 30
        || value.nickname.trim() !== value.nickname
      )
    )
    || typeof value.status !== 'string'
    || !ENROLLMENT_STATUSES.has(value.status)
    || typeof value.user_is_active !== 'boolean'
    || typeof value.activated !== 'boolean'
    || !isNullableTimestamp(value.activation_expires_at)
    || !isNullableTimestamp(value.activation_used_at)
    || typeof value.created_at !== 'string'
    || !isIsoTimestamp(value.created_at)
    || value.activated !== (value.activation_used_at !== null)
    || (value.status === 'pending' && value.activated)
    || (value.status === 'active' && !value.activated)
  ) {
    throw new InstructorCourseApiError('unavailable')
  }

  return {
    enrollment_id: value.enrollment_id,
    berkeley_username: value.berkeley_username,
    nickname: value.nickname as string | null,
    status: value.status as InstructorEnrollment['status'],
    user_is_active: value.user_is_active,
    activated: value.activated,
    activation_expires_at: value.activation_expires_at,
    activation_used_at: value.activation_used_at,
    created_at: value.created_at,
  }
}

function parseEnrollmentList(value: unknown): InstructorEnrollmentListResponse {
  if (
    !isRecord(value)
    || !Array.isArray(value.items)
    || !Number.isInteger(value.total)
    || (value.total as number) < 0
    || !Number.isInteger(value.offset)
    || (value.offset as number) < 0
    || !Number.isInteger(value.limit)
    || (value.limit as number) < 1
    || (value.limit as number) > 100
  ) {
    throw new InstructorCourseApiError('unavailable')
  }

  const items = value.items.map(parseInstructorEnrollment)
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

export async function getInstructorEnrollments(
  courseId: string,
  query: InstructorEnrollmentListQuery,
  signal?: AbortSignal,
): Promise<InstructorEnrollmentListResponse> {
  const parameters = new URLSearchParams({
    offset: String(query.offset),
    limit: String(query.limit),
  })
  const search = query.search?.trim()
  if (search) {
    parameters.set('search', search)
  }
  if (query.activation_status) {
    parameters.set('activation_status', query.activation_status)
  }

  try {
    const response = await fetch(
      `/api/instructor/courses/${encodeURIComponent(courseId)}/students?${parameters}`,
      {
        credentials: 'include',
        signal,
      },
    )
    throwForCourseResponse(response)
    const result = parseEnrollmentList(await safeJson(response))
    if (result.offset !== query.offset || result.limit !== query.limit) {
      throw new InstructorCourseApiError('unavailable')
    }
    return result
  } catch (error) {
    return unavailableUnlessAborted(error)
  }
}

const REISSUE_DOWNLOAD_FILENAME = 'regenerated-activation-code.csv'
const MAX_REISSUE_RESPONSE_BYTES = 64 * 1024

async function parseActivationReissueResponse(
  response: Response,
  course: InstructorCourse,
  enrollment: InstructorEnrollment,
): Promise<ActivationCodeReissueResult> {
  const contentType = response.headers.get('content-type')?.toLowerCase() ?? ''
  const disposition = response.headers.get('content-disposition')
  const cacheControl = response.headers.get('cache-control')?.toLowerCase() ?? ''
  const pragma = response.headers.get('pragma')?.toLowerCase() ?? ''
  if (
    !contentType.startsWith('text/csv')
    || disposition !== `attachment; filename="${REISSUE_DOWNLOAD_FILENAME}"`
    || !cacheControl.includes('no-store')
    || pragma !== 'no-cache'
  ) {
    throw new InstructorCourseApiError('unavailable')
  }

  const bytes = await response.arrayBuffer()
  if (bytes.byteLength === 0 || bytes.byteLength > MAX_REISSUE_RESPONSE_BYTES) {
    throw new InstructorCourseApiError('unavailable')
  }

  let text: string
  try {
    text = new TextDecoder('utf-8', { fatal: true }).decode(bytes)
  } catch {
    throw new InstructorCourseApiError('unavailable')
  }
  const records = parseCsvRecords(text)
  if (
    records.length !== 2
    || records[0].length !== ROSTER_HEADER.length
    || records[0].some((value, index) => value !== ROSTER_HEADER[index])
    || records[1].length !== ROSTER_HEADER.length
  ) {
    throw new InstructorCourseApiError('unavailable')
  }

  const row = records[1]
  if (
    row[0] !== spreadsheetSafeValue(enrollment.berkeley_username)
    || row[1] !== spreadsheetSafeValue(course.course_code)
    || !ACTIVATION_CODE_PATTERN.test(row[2])
    || row[3] !== 'regenerated'
    || !row[4]
    || [row[0], row[1], row[3], row[4]]
      .some((value) => FORMULA_PREFIX_PATTERN.test(value))
  ) {
    throw new InstructorCourseApiError('unavailable')
  }

  return {
    csv: new Blob([bytes], { type: 'text/csv;charset=utf-8' }),
  }
}

export async function regenerateInstructorActivationCode(
  course: InstructorCourse,
  enrollment: InstructorEnrollment,
): Promise<ActivationCodeReissueResult> {
  try {
    const response = await fetch(
      `/api/instructor/courses/${encodeURIComponent(course.id)}`
      + `/enrollments/${encodeURIComponent(enrollment.enrollment_id)}`
      + '/activation/regenerate',
      {
        method: 'POST',
        credentials: 'include',
      },
    )
    throwForCourseResponse(response)
    return await parseActivationReissueResponse(response, course, enrollment)
  } catch (error) {
    return unavailableUnlessAborted(error)
  }
}
