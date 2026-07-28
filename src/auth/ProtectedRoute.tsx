import { useState, type ReactNode } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from './AuthProvider'

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

export function RoleMismatchScreen() {
  const { logout } = useAuth()
  const navigate = useNavigate()
  const [signingOut, setSigningOut] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSignOut() {
    if (signingOut) return
    setSigningOut(true)
    setError(null)
    try {
      await logout()
      navigate('/login', { replace: true })
    } catch {
      setError('Sign out could not be completed. Please try again.')
    } finally {
      setSigningOut(false)
    }
  }

  return (
    <PageShell>
      <h1 className="text-xl font-bold">Student dashboard unavailable</h1>
      <p className="mt-3 text-sm text-ink-dim">
        This session does not have Student access. Instructor tools will be added in a later phase.
      </p>
      {error && <p className="mt-3 text-sm text-red-700" role="alert">{error}</p>}
      <button
        type="button"
        onClick={() => void handleSignOut()}
        disabled={signingOut}
        className="mt-6 rounded-md border border-line-strong px-4 py-2 text-sm font-semibold text-ink transition-colors hover:bg-well disabled:cursor-not-allowed disabled:opacity-60"
      >
        {signingOut ? 'Signing out…' : 'Sign Out'}
      </button>
    </PageShell>
  )
}

export default function ProtectedRoute({ children }: { children: ReactNode }) {
  const { status, user } = useAuth()
  const location = useLocation()

  if (status === 'loading') {
    return <AuthLoadingScreen />
  }
  if (status === 'error') {
    return <AuthUnavailableScreen />
  }
  if (status === 'unauthenticated' || !user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }
  if (user.role !== 'student') {
    return <RoleMismatchScreen />
  }
  return children
}
