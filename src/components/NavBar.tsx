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
  { page: 2, label: '02  Policy & AI' },
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
      <div className="max-w-6xl mx-auto px-6 flex min-h-14 flex-wrap items-center gap-x-6 gap-y-2 py-2 lg:flex-nowrap lg:py-0">
        <span className="text-xs font-mono tracking-widest text-ink-faintest uppercase shrink-0">
          Resource Allocation Simulator
        </span>
        <nav className="order-3 flex h-12 w-full overflow-x-auto lg:order-none lg:w-auto lg:flex-1">
          {TABS.map(({ page, label }) => (
            <button
              key={page}
              onClick={() => onNavigate(page)}
              className={[
                'px-5 h-full text-sm font-medium tracking-wide border-b-2 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-hud-accent/50 focus-visible:ring-inset',
                currentPage === page
                  ? 'border-hud-accent text-hud-accent'
                  : 'border-transparent text-ink-faint hover:text-ink-dim',
              ].join(' ')}
            >
              {label}
            </button>
          ))}
        </nav>
        <div className="ml-auto flex min-w-0 items-center gap-3">
          <div className="min-w-0 text-right">
            <p className="truncate text-sm font-semibold text-ink">{nickname}</p>
            <p className="truncate font-mono text-[11px] text-ink-faint">{course?.course_code}</p>
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
      {signOutError && (
        <p className="max-w-6xl mx-auto px-6 pb-2 text-right text-xs text-red-700" role="alert">
          {signOutError}
        </p>
      )}
    </header>
  )
}
