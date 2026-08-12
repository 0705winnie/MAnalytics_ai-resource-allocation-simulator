import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthProvider'

export type Page = 1 | 2 | 3 | 4

interface Props {
  currentPage: Page
  onNavigate: (page: Page) => void
}

export const TABS: { page: Page; label: string }[] = [
  { page: 1, label: '01  Introduction' },
  { page: 2, label: '02  Policy' },
  { page: 3, label: '03  Simulation' },
  { page: 4, label: '04  History & Leaderboards' },
]

export default function NavBar({ currentPage, onNavigate }: Props) {
  const navigate = useNavigate()
  const { course, nickname, logout } = useAuth()
  const [signingOut, setSigningOut] = useState(false)
  const [signOutError, setSignOutError] = useState<string | null>(null)

  async function handleSignOut() {
    if (signingOut) return
    setSigningOut(true)
    setSignOutError(null)
    try {
      await logout()
      navigate('/login', { replace: true })
    } catch {
      setSignOutError('Sign out could not be completed. Please try again.')
    } finally {
      setSigningOut(false)
    }
  }

  return (
    <header className="border-b border-line bg-white shadow-card">
      <div className="mx-auto max-w-7xl px-4 sm:px-6">
        <div className="flex min-h-14 items-center gap-3">
          <span className="hidden shrink-0 font-mono text-xs uppercase tracking-widest text-ink-faintest xl:inline">
            Resource Allocation Simulator
          </span>
          <nav aria-label="Student pages" className="hidden min-w-0 flex-1 self-stretch overflow-x-auto md:flex">
            {TABS.map(({ page, label }) => (
              <button
                key={page}
                onClick={() => onNavigate(page)}
                className={[
                  'h-full shrink-0 whitespace-nowrap border-b-2 px-2.5 text-xs font-medium tracking-wide transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-hud-accent/50 focus-visible:ring-inset lg:px-4 lg:text-sm',
                  currentPage === page
                    ? 'border-hud-accent text-hud-accent'
                    : 'border-transparent text-ink-faint hover:text-ink-dim',
                ].join(' ')}
              >
                {label}
              </button>
            ))}
          </nav>
          <div className="ml-auto flex min-w-0 shrink-0 items-center gap-2 sm:gap-3">
            <div className="min-w-0 max-w-44 text-right">
              <p className="truncate text-sm font-semibold text-ink">{nickname}</p>
              <p className="truncate font-mono text-[11px] text-ink-faint">{course?.course_identifier}</p>
            </div>
            <button
              type="button"
              onClick={() => void handleSignOut()}
              disabled={signingOut}
              className="shrink-0 rounded-md border border-line-strong px-3 py-1.5 text-xs font-semibold text-ink-dim transition-colors hover:bg-well focus:outline-none focus-visible:ring-2 focus-visible:ring-hud-accent/30 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {signingOut ? 'Signing out…' : 'Sign Out'}
            </button>
          </div>
        </div>
        <nav aria-label="Student pages" className="flex h-11 overflow-x-auto border-t border-line md:hidden">
          {TABS.map(({ page, label }) => (
            <button
              key={page}
              onClick={() => onNavigate(page)}
              className={[
                'h-full shrink-0 whitespace-nowrap border-b-2 px-3 text-xs font-medium tracking-wide transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-hud-accent/50 focus-visible:ring-inset',
                currentPage === page
                  ? 'border-hud-accent text-hud-accent'
                  : 'border-transparent text-ink-faint hover:text-ink-dim',
              ].join(' ')}
            >
              {label}
            </button>
          ))}
        </nav>
      </div>
      {signOutError && (
        <p className="mx-auto max-w-7xl px-4 pb-2 text-right text-xs text-red-700 sm:px-6" role="alert">
          {signOutError}
        </p>
      )}
    </header>
  )
}
