import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { AuthApiError } from '../auth/api'
import {
  AUTH_SERVICE_UNAVAILABLE_MESSAGE,
  useAuth,
} from '../auth/AuthProvider'

const INVALID_INSTRUCTOR_CREDENTIALS_MESSAGE = 'Invalid username or password.'

export default function InstructorLoginPage() {
  const navigate = useNavigate()
  const { loginInstructor } = useAuth()
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
      await loginInstructor({ username, password })
      navigate('/instructor', { replace: true })
    } catch (error) {
      setFormError(
        error instanceof AuthApiError
        && error.code === 'invalid_instructor_credentials'
          ? INVALID_INSTRUCTOR_CREDENTIALS_MESSAGE
          : AUTH_SERVICE_UNAVAILABLE_MESSAGE,
      )
    } finally {
      setPassword('')
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
              Manage your course environment.
            </h1>
            <p className="mt-4 max-w-md text-sm leading-6 text-white/80">
              Instructor access connects securely to the account system.
              Course and roster tools will arrive in the next phase.
            </p>
          </section>

          <section className="p-8 sm:p-12" aria-labelledby="instructor-login-title">
            <p className="font-mono text-xs uppercase tracking-widest text-ink-faint">
              Instructor access
            </p>
            <h2
              id="instructor-login-title"
              className="mt-2 text-2xl font-bold tracking-tight"
            >
              Sign in
            </h2>

            <form
              className="mt-7 space-y-5"
              onSubmit={(event) => void handleSubmit(event)}
            >
              <div>
                <label
                  htmlFor="instructor-username"
                  className="block text-sm font-medium text-ink-dim"
                >
                  Instructor Username
                </label>
                <input
                  id="instructor-username"
                  name="username"
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
                <label
                  htmlFor="instructor-password"
                  className="block text-sm font-medium text-ink-dim"
                >
                  Password
                </label>
                <input
                  id="instructor-password"
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
                <p
                  className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800"
                  role="alert"
                >
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
                onClick={() => navigate('/login')}
                disabled={submitting}
                className="w-full rounded-md border border-line-strong px-4 py-2.5 text-sm font-semibold text-ink-dim transition-colors hover:bg-well focus:outline-none focus-visible:ring-2 focus-visible:ring-hud-accent/30 disabled:cursor-not-allowed disabled:opacity-60"
              >
                Back to Student Sign In
              </button>
            </form>
          </section>
        </div>
      </div>
    </main>
  )
}
