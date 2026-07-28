import { useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthProvider'

function navigationClass({ isActive }: { isActive: boolean }) {
  return [
    'rounded-md px-3 py-2 text-sm font-semibold transition-colors',
    'focus:outline-none focus-visible:ring-2 focus-visible:ring-hud-accent/30',
    isActive
      ? 'bg-hud-accent text-white'
      : 'text-ink-dim hover:bg-well hover:text-ink',
  ].join(' ')
}

export default function InstructorLayout() {
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
    <div className="min-h-screen bg-paper text-ink">
      <header className="border-b border-line bg-white">
        <div className="mx-auto flex w-full max-w-6xl flex-col gap-5 px-6 py-5 sm:px-10 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <p className="font-mono text-xs uppercase tracking-[0.2em] text-hud-accent">
              Resource Allocation Simulator
            </p>
            <p className="mt-1 text-sm text-ink-dim">
              Signed in as{' '}
              <span className="font-semibold text-ink">{user?.username}</span>
            </p>
          </div>

          <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
            <nav
              className="flex flex-wrap gap-1"
              aria-label="Instructor navigation"
            >
              <NavLink to="/instructor" end className={navigationClass}>
                Dashboard
              </NavLink>
              <NavLink to="/instructor/courses" end className={navigationClass}>
                My Courses
              </NavLink>
              <NavLink to="/instructor/courses/new" className={navigationClass}>
                Create Course
              </NavLink>
            </nav>
            <button
              type="button"
              onClick={() => void handleSignOut()}
              disabled={signingOut}
              className="rounded-md border border-line-strong px-4 py-2 text-sm font-semibold text-ink transition-colors hover:bg-well focus:outline-none focus-visible:ring-2 focus-visible:ring-hud-accent/30 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {signingOut ? 'Signing out…' : 'Sign Out'}
            </button>
          </div>
        </div>
      </header>

      {logoutError && (
        <div className="mx-auto w-full max-w-6xl px-6 pt-5 sm:px-10">
          <p
            className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800"
            role="alert"
          >
            {logoutError}
          </p>
        </div>
      )}

      <Outlet />
    </div>
  )
}
