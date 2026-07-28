import { useState, type ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from './AuthProvider'
import type { AuthRole } from './types'

export function roleHomePath(role: AuthRole): '/app' | '/instructor/courses' {
  return role === 'student' ? '/app' : '/instructor/courses'
}

function PageShell({ children }: { children: ReactNode }) {
  return (
    <main className="min-h-screen bg-paper text-ink flex items-center justify-center px-6 py-12">
      <section className="w-full max-w-lg rounded-xl border border-line bg-white p-8 shadow-card">
        {children}
      </section>
    </main>
  )
}

export function AuthLoadingScreen() {
  return (
    <PageShell>
      <p className="text-sm font-medium text-ink" role="status">
        Restoring your secure session…
      </p>
      <p className="mt-2 text-sm text-ink-faint">
        Checking the server for your current course access.
      </p>
    </PageShell>
  )
}

export function AuthUnavailableScreen() {
  const { refreshAuth } = useAuth()
  const [retrying, setRetrying] = useState(false)

  async function handleRetry() {
    if (retrying) return
    setRetrying(true)
    await refreshAuth()
    setRetrying(false)
  }

  return (
    <PageShell>
      <h1 className="text-xl font-bold">Authentication unavailable</h1>
      <p className="mt-3 text-sm text-ink-dim" role="alert">
        Authentication service is temporarily unavailable.
      </p>
      <button
        type="button"
        onClick={() => void handleRetry()}
        disabled={retrying}
        className="mt-6 rounded-md bg-hud-accent px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-hud-accent-hover disabled:cursor-not-allowed disabled:opacity-60"
      >
        {retrying ? 'Retrying…' : 'Retry'}
      </button>
    </PageShell>
  )
}

interface RoleProtectedRouteProps {
  children: ReactNode
  requiredRole: AuthRole
  unauthenticatedPath: '/login' | '/instructor/login'
}

export default function RoleProtectedRoute({
  children,
  requiredRole,
  unauthenticatedPath,
}: RoleProtectedRouteProps) {
  const { status, user } = useAuth()

  if (status === 'loading') {
    return <AuthLoadingScreen />
  }
  if (status === 'error') {
    return <AuthUnavailableScreen />
  }
  if (status === 'unauthenticated' || !user) {
    return <Navigate to={unauthenticatedPath} replace />
  }
  if (user.role !== requiredRole) {
    return <Navigate to={roleHomePath(user.role)} replace />
  }
  return children
}
