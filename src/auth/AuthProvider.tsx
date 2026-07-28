import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import {
  AuthApiError,
  getCurrentAuthentication,
  loginStudent as requestStudentLogin,
  logoutCurrentSession,
} from './api'
import type {
  AuthenticatedCourse,
  AuthenticatedUser,
  AuthenticationResponse,
  AuthStatus,
  StudentLoginRequest,
} from './types'

export const AUTH_SERVICE_UNAVAILABLE_MESSAGE =
  'Authentication service is temporarily unavailable.'

interface AuthContextValue {
  status: AuthStatus
  user: AuthenticatedUser | null
  course: AuthenticatedCourse | null
  nickname: string | null
  error: string | null
  loginStudent: (request: StudentLoginRequest) => Promise<void>
  logout: () => Promise<void>
  refreshAuth: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError'
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>('loading')
  const [session, setSession] = useState<AuthenticationResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  const applySession = useCallback((nextSession: AuthenticationResponse | null) => {
    setSession(nextSession)
    setStatus(nextSession ? 'authenticated' : 'unauthenticated')
    setError(null)
  }, [])

  const runRefresh = useCallback(async (signal?: AbortSignal) => {
    setStatus('loading')
    setError(null)
    try {
      const nextSession = await getCurrentAuthentication(signal)
      if (!signal?.aborted) {
        applySession(nextSession)
      }
    } catch (refreshError) {
      if (signal?.aborted || isAbortError(refreshError)) {
        return
      }
      setSession(null)
      setStatus('error')
      setError(AUTH_SERVICE_UNAVAILABLE_MESSAGE)
    }
  }, [applySession])

  useEffect(() => {
    const controller = new AbortController()
    void runRefresh(controller.signal)
    return () => controller.abort()
  }, [runRefresh])

  const refreshAuth = useCallback(async () => {
    await runRefresh()
  }, [runRefresh])

  const loginStudent = useCallback(async (request: StudentLoginRequest) => {
    try {
      const nextSession = await requestStudentLogin(request)
      applySession(nextSession)
    } catch (loginError) {
      setError(
        loginError instanceof AuthApiError && loginError.code === 'invalid_credentials'
          ? null
          : AUTH_SERVICE_UNAVAILABLE_MESSAGE,
      )
      throw loginError
    }
  }, [applySession])

  const logout = useCallback(async () => {
    try {
      await logoutCurrentSession()
      applySession(null)
    } catch (logoutError) {
      setError(AUTH_SERVICE_UNAVAILABLE_MESSAGE)
      throw logoutError
    }
  }, [applySession])

  const value = useMemo<AuthContextValue>(() => ({
    status,
    user: session?.user ?? null,
    course: session?.course ?? null,
    nickname: session?.nickname ?? null,
    error,
    loginStudent,
    logout,
    refreshAuth,
  }), [error, loginStudent, logout, refreshAuth, session, status])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider')
  }
  return context
}
