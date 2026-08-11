import type {
  ActivationCompleteRequest,
  ActivationVerificationResponse,
  ActivationVerifyRequest,
  AuthenticationResponse,
  InstructorAuthenticationResponse,
  InstructorLoginRequest,
  StudentAuthenticationResponse,
  StudentLoginRequest,
} from './types'

export type AuthApiErrorCode =
  | 'invalid_credentials'
  | 'invalid_instructor_credentials'
  | 'invalid_activation'
  | 'activation_session_expired'
  | 'nickname_conflict'
  | 'invalid_nickname'
  | 'unavailable'

export class AuthApiError extends Error {
  readonly code: AuthApiErrorCode

  constructor(code: AuthApiErrorCode) {
    super(code)
    this.name = 'AuthApiError'
    this.code = code
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function parseAuthenticationResponse(value: unknown): AuthenticationResponse {
  if (!isRecord(value) || value.authenticated !== true || !isRecord(value.user)) {
    throw new AuthApiError('unavailable')
  }

  const { user } = value
  if (
    typeof user.id !== 'string'
    || typeof user.username !== 'string'
    || (user.role !== 'student' && user.role !== 'instructor')
  ) {
    throw new AuthApiError('unavailable')
  }

  const course = value.course
  if (
    course !== undefined
    && course !== null
    && (
      !isRecord(course)
      || typeof course.id !== 'string'
      || typeof course.course_code !== 'string'
      || typeof course.semester !== 'string'
      || typeof course.course_identifier !== 'string'
    )
  ) {
    throw new AuthApiError('unavailable')
  }
  if (
    value.nickname !== undefined
    && value.nickname !== null
    && typeof value.nickname !== 'string'
  ) {
    throw new AuthApiError('unavailable')
  }

  return {
    authenticated: true,
    user: {
      id: user.id,
      username: user.username,
      role: user.role,
    },
    course: course as AuthenticationResponse['course'],
    nickname: value.nickname as AuthenticationResponse['nickname'],
  }
}

function requireStudentSession(
  value: AuthenticationResponse,
): StudentAuthenticationResponse {
  if (
    value.user.role !== 'student'
    || !value.course
    || typeof value.nickname !== 'string'
    || value.nickname.length === 0
  ) {
    throw new AuthApiError('unavailable')
  }
  return value as StudentAuthenticationResponse
}

function requireInstructorSession(
  value: AuthenticationResponse,
): InstructorAuthenticationResponse {
  if (
    value.user.role !== 'instructor'
    || (value.course !== undefined && value.course !== null)
    || (value.nickname !== undefined && value.nickname !== null)
  ) {
    throw new AuthApiError('unavailable')
  }
  return value as InstructorAuthenticationResponse
}

function parseActivationVerificationResponse(
  value: unknown,
): ActivationVerificationResponse {
  if (
    !isRecord(value)
    || value.verified !== true
    || !Number.isInteger(value.expires_in_seconds)
    || (value.expires_in_seconds as number) <= 0
  ) {
    throw new AuthApiError('unavailable')
  }

  return {
    verified: true,
    expires_in_seconds: value.expires_in_seconds as number,
  }
}

async function safeJson(response: Response): Promise<unknown> {
  try {
    return await response.json()
  } catch {
    throw new AuthApiError('unavailable')
  }
}

function unavailableUnlessAborted(error: unknown): never {
  if (error instanceof DOMException && error.name === 'AbortError') {
    throw error
  }
  if (error instanceof AuthApiError) {
    throw error
  }
  throw new AuthApiError('unavailable')
}

export async function getCurrentAuthentication(
  signal?: AbortSignal,
): Promise<AuthenticationResponse | null> {
  try {
    const response = await fetch('/api/auth/me', {
      credentials: 'include',
      signal,
    })
    if (response.status === 401) {
      return null
    }
    if (!response.ok) {
      throw new AuthApiError('unavailable')
    }
    const session = parseAuthenticationResponse(await safeJson(response))
    return session.user.role === 'student'
      ? requireStudentSession(session)
      : requireInstructorSession(session)
  } catch (error) {
    return unavailableUnlessAborted(error)
  }
}

export async function loginStudent(
  request: StudentLoginRequest,
): Promise<StudentAuthenticationResponse> {
  try {
    const response = await fetch('/api/auth/student/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify(request),
    })
    if (response.status === 401 || (response.status >= 400 && response.status < 500)) {
      throw new AuthApiError('invalid_credentials')
    }
    if (!response.ok) {
      throw new AuthApiError('unavailable')
    }
    return requireStudentSession(
      parseAuthenticationResponse(await safeJson(response)),
    )
  } catch (error) {
    return unavailableUnlessAborted(error)
  }
}

export async function loginInstructor(
  request: InstructorLoginRequest,
): Promise<InstructorAuthenticationResponse> {
  try {
    const response = await fetch('/api/auth/instructor/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify(request),
    })
    if (response.status >= 400 && response.status < 500) {
      throw new AuthApiError('invalid_instructor_credentials')
    }
    if (!response.ok) {
      throw new AuthApiError('unavailable')
    }
    return requireInstructorSession(
      parseAuthenticationResponse(await safeJson(response)),
    )
  } catch (error) {
    return unavailableUnlessAborted(error)
  }
}

export async function verifyStudentActivation(
  request: ActivationVerifyRequest,
): Promise<ActivationVerificationResponse> {
  try {
    const response = await fetch('/api/auth/activate/verify', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify(request),
    })
    if (response.status >= 400 && response.status < 500) {
      throw new AuthApiError('invalid_activation')
    }
    if (!response.ok) {
      throw new AuthApiError('unavailable')
    }
    return parseActivationVerificationResponse(await safeJson(response))
  } catch (error) {
    return unavailableUnlessAborted(error)
  }
}

export async function completeStudentActivation(
  request: ActivationCompleteRequest,
): Promise<StudentAuthenticationResponse> {
  try {
    const response = await fetch('/api/auth/activate/complete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify(request),
    })
    if (response.status === 401) {
      throw new AuthApiError('activation_session_expired')
    }
    if (response.status === 409) {
      throw new AuthApiError('nickname_conflict')
    }
    if (response.status === 422) {
      throw new AuthApiError('invalid_nickname')
    }
    if (response.status >= 400 && response.status < 500) {
      throw new AuthApiError('activation_session_expired')
    }
    if (!response.ok) {
      throw new AuthApiError('unavailable')
    }
    return requireStudentSession(
      parseAuthenticationResponse(await safeJson(response)),
    )
  } catch (error) {
    return unavailableUnlessAborted(error)
  }
}

export async function logoutCurrentSession(): Promise<void> {
  try {
    const response = await fetch('/api/auth/logout', {
      method: 'POST',
      credentials: 'include',
    })
    if (!response.ok) {
      throw new AuthApiError('unavailable')
    }
    const body = await safeJson(response)
    if (!isRecord(body) || body.authenticated !== false) {
      throw new AuthApiError('unavailable')
    }
  } catch (error) {
    unavailableUnlessAborted(error)
  }
}
