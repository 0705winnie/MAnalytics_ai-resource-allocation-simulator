import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthProvider'

const UPCOMING_TOOLS = [
  ['Course management', 'Coming next'],
  ['Roster management', 'Coming next'],
  ['Student progress', 'Coming later'],
] as const

export default function InstructorLandingPage() {
  const navigate = useNavigate()
  const { user, logout } = useAuth()
  const [signingOut, setSigningOut] = useState(false)
  const [logoutError, setLogoutError] = useState<string | null>(null)

  async function handleSignOut() {
    if (signingOut) return

    setSigningOut(true)
    setLogoutError(null)
    try {
      await logout()
      navigate('/instructor/login', { replace: true })
    } catch {
      setLogoutError('Sign out could not be completed. Please try again.')
    } finally {
      setSigningOut(false)
    }
  }

  return (
    <main className="min-h-screen bg-paper px-6 py-10 text-ink sm:px-10">
      <div className="mx-auto w-full max-w-5xl">
        <header className="flex flex-col gap-5 rounded-2xl border border-line bg-white p-6 shadow-card sm:flex-row sm:items-center sm:justify-between sm:p-8">
          <div>
            <p className="font-mono text-xs uppercase tracking-[0.2em] text-hud-accent">
              Resource Allocation Simulator
            </p>
            <h1 className="mt-3 text-3xl font-bold tracking-tight">
              Instructor Dashboard
            </h1>
            <p className="mt-2 text-sm text-ink-dim">
              Signed in as <span className="font-semibold text-ink">{user?.username}</span>
            </p>
          </div>
          <button
            type="button"
            onClick={() => void handleSignOut()}
            disabled={signingOut}
            className="w-full rounded-md border border-line-strong px-4 py-2.5 text-sm font-semibold text-ink transition-colors hover:bg-well focus:outline-none focus-visible:ring-2 focus-visible:ring-hud-accent/30 disabled:cursor-not-allowed disabled:opacity-60 sm:w-auto"
          >
            {signingOut ? 'Signing out…' : 'Sign Out'}
          </button>
        </header>

        {logoutError && (
          <p
            className="mt-5 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800"
            role="alert"
          >
            {logoutError}
          </p>
        )}

        <section className="mt-8 rounded-2xl border border-line bg-white p-6 shadow-card sm:p-8">
          <div className="flex items-center gap-3">
            <span className="h-2.5 w-2.5 rounded-full bg-emerald-500" aria-hidden="true" />
            <h2 className="text-lg font-semibold">Account system is connected</h2>
          </div>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-ink-dim">
            Your Instructor session is active. This page is a secure placeholder
            while course administration tools are prepared.
          </p>

          <div className="mt-8 grid gap-4 md:grid-cols-3">
            {UPCOMING_TOOLS.map(([title, status]) => (
              <article key={title} className="rounded-xl border border-line bg-well p-5">
                <h3 className="font-semibold">{title}</h3>
                <p className="mt-2 font-mono text-xs uppercase tracking-wider text-ink-faint">
                  {status}
                </p>
              </article>
            ))}
          </div>
        </section>
      </div>
    </main>
  )
}
