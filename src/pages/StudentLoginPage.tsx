import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { AuthApiError } from '../auth/api'
import {
  AUTH_SERVICE_UNAVAILABLE_MESSAGE,
  useAuth,
} from '../auth/AuthProvider'

const INVALID_CREDENTIALS_MESSAGE = 'Invalid course, username, or password.'

export default function StudentLoginPage() {
  const navigate = useNavigate()
  const { status, error: authError, loginStudent, refreshAuth } = useAuth()
  const [courseCode, setCourseCode] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (submitting) return

    setSubmitting(true)
    setFormError(null)
    try {
      await loginStudent({
        course_code: courseCode,
        berkeley_username: username,
        password,
      })
      setPassword('')
      navigate('/app', { replace: true })
    } catch (error) {
      setFormError(
        error instanceof AuthApiError && error.code === 'invalid_credentials'
          ? INVALID_CREDENTIALS_MESSAGE
          : AUTH_SERVICE_UNAVAILABLE_MESSAGE,
      )
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="min-h-screen bg-paper text-ink">
      <div className="mx-auto flex min-h-screen w-full max-w-6xl items-center px-6 py-12">
        <div className="grid w-full overflow-hidden rounded-2xl border border-line bg-white shadow-card lg:grid-cols-[1.05fr_0.95fr]">
          <section className="bg-gradient-to-br from-hud-accent to-hud-accent-hover p-8 text-white sm:p-12">
            <p className="font-mono text-xs uppercase tracking-[0.22em] text-white/70">
              Resource Allocation Simulator
            </p>
            <h1 className="mt-8 max-w-lg text-3xl font-bold tracking-tight sm:text-4xl">
              Continue your course simulation.
            </h1>
            <p className="mt-4 max-w-md text-sm leading-6 text-white/80">
              Sign in with the course and credentials established during roster activation.
              Your authenticated nickname identifies this course session.
            </p>
          </section>

          <section className="p-8 sm:p-12" aria-labelledby="student-login-title">
            <p className="text-xs font-mono uppercase tracking-widest text-ink-faint">
              Student access
            </p>
            <h2 id="student-login-title" className="mt-2 text-2xl font-bold tracking-tight">
              Sign in
            </h2>

            {status === 'error' && authError && (
              <div className="mt-5 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800" role="alert">
                <p>{AUTH_SERVICE_UNAVAILABLE_MESSAGE}</p>
                <button
                  type="button"
                  onClick={() => void refreshAuth()}
                  className="mt-2 font-semibold underline underline-offset-2"
                >
                  Retry session check
                </button>
              </div>
            )}

            <form className="mt-7 space-y-5" onSubmit={(event) => void handleSubmit(event)}>
              <div>
                <label htmlFor="course-code" className="block text-sm font-medium text-ink-dim">
                  Course Code
                </label>
                <input
                  id="course-code"
                  name="course_code"
                  type="text"
                  autoComplete="organization"
                  required
                  maxLength={64}
                  value={courseCode}
                  onChange={(event) => setCourseCode(event.target.value)}
                  disabled={submitting}
                  className="mt-2 w-full rounded-md border border-line-strong bg-white px-3 py-2.5 text-sm text-ink outline-none transition focus:border-hud-accent focus:ring-2 focus:ring-hud-accent/15 disabled:opacity-60"
                />
              </div>

              <div>
                <label htmlFor="berkeley-username" className="block text-sm font-medium text-ink-dim">
                  Berkeley Username
                </label>
                <input
                  id="berkeley-username"
                  name="berkeley_username"
                  type="text"
                  autoComplete="username"
                  required
                  maxLength={64}
                  value={username}
                  onChange={(event) => setUsername(event.target.value)}
                  disabled={submitting}
                  className="mt-2 w-full rounded-md border border-line-strong bg-white px-3 py-2.5 text-sm text-ink outline-none transition focus:border-hud-accent focus:ring-2 focus:ring-hud-accent/15 disabled:opacity-60"
                />
              </div>

              <div>
                <label htmlFor="student-password" className="block text-sm font-medium text-ink-dim">
                  Password
                </label>
                <input
                  id="student-password"
                  name="password"
                  type="password"
                  autoComplete="current-password"
                  required
                  maxLength={128}
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  disabled={submitting}
                  className="mt-2 w-full rounded-md border border-line-strong bg-white px-3 py-2.5 text-sm text-ink outline-none transition focus:border-hud-accent focus:ring-2 focus:ring-hud-accent/15 disabled:opacity-60"
                />
              </div>

              {formError && (
                <p className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800" role="alert">
                  {formError}
                </p>
              )}

              <button
                type="submit"
                disabled={submitting}
                className="w-full rounded-md bg-hud-accent px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-hud-accent-hover focus:outline-none focus-visible:ring-2 focus-visible:ring-hud-accent/40 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {submitting ? 'Signing in…' : 'Sign In'}
              </button>

              <button
                type="button"
                onClick={() => navigate('/activate')}
                disabled={submitting}
                className="w-full rounded-md border border-line-strong px-4 py-2.5 text-sm font-semibold text-ink-dim transition-colors hover:bg-well focus:outline-none focus-visible:ring-2 focus-visible:ring-hud-accent/30 disabled:cursor-not-allowed disabled:opacity-60"
              >
                First-time activation
              </button>

              <button
                type="button"
                onClick={() => navigate('/instructor/login')}
                disabled={submitting}
                className="w-full px-4 py-2 text-sm font-semibold text-ink-faint underline decoration-line-strong underline-offset-4 transition-colors hover:text-ink focus:outline-none focus-visible:ring-2 focus-visible:ring-hud-accent/30 disabled:cursor-not-allowed disabled:opacity-60"
              >
                Instructor sign in
              </button>
            </form>
          </section>
        </div>
      </div>
    </main>
  )
}
