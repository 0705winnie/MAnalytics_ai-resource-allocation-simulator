import {
  useEffect,
  useState,
  type FormEvent,
} from 'react'
import { useNavigate } from 'react-router-dom'
import {
  AuthApiError,
  verifyStudentActivation,
} from '../auth/api'
import { useAuth } from '../auth/AuthProvider'

const INVALID_ACTIVATION_MESSAGE =
  'Invalid or expired activation credentials.'
const ACTIVATION_UNAVAILABLE_MESSAGE =
  'Activation service is temporarily unavailable.'
const ACTIVATION_SESSION_EXPIRED_MESSAGE =
  'Activation session expired. Please verify your activation code again.'

type ActivationStep = 'verify' | 'complete'

function formatRemainingTime(seconds: number): string {
  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = seconds % 60
  return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`
}

function normalizeNickname(value: string): string {
  return value.trim().replace(/ +/g, ' ')
}

function isValidNickname(value: string): boolean {
  const normalized = normalizeNickname(value)
  return (
    normalized.length >= 3
    && normalized.length <= 30
    && /^[\p{L}\p{N}](?:[\p{L}\p{N} _-]*[\p{L}\p{N}])?$/u.test(normalized)
  )
}

export default function StudentActivationPage() {
  const navigate = useNavigate()
  const { completeStudentActivation } = useAuth()
  const [step, setStep] = useState<ActivationStep>('verify')
  const [courseId, setCourseId] = useState('')
  const [username, setUsername] = useState('')
  const [activationCode, setActivationCode] = useState('')
  const [password, setPassword] = useState('')
  const [passwordConfirmation, setPasswordConfirmation] = useState('')
  const [nickname, setNickname] = useState('')
  const [expiresAt, setExpiresAt] = useState<number | null>(null)
  const [remainingSeconds, setRemainingSeconds] = useState(0)
  const [sessionExpired, setSessionExpired] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)

  useEffect(() => {
    if (step !== 'complete' || expiresAt === null) {
      return undefined
    }

    let timer: number | undefined
    const updateRemainingTime = () => {
      const nextRemaining = Math.max(
        0,
        Math.ceil((expiresAt - Date.now()) / 1000),
      )
      setRemainingSeconds(nextRemaining)
      if (nextRemaining === 0) {
        setExpiresAt(null)
        setRemainingSeconds(0)
        setPassword('')
        setPasswordConfirmation('')
        setSessionExpired(true)
        setFormError(ACTIVATION_SESSION_EXPIRED_MESSAGE)
        if (timer !== undefined) {
          window.clearInterval(timer)
        }
      }
    }

    updateRemainingTime()
    if (expiresAt > Date.now()) {
      timer = window.setInterval(updateRemainingTime, 1000)
    }
    return () => {
      if (timer !== undefined) {
        window.clearInterval(timer)
      }
    }
  }, [expiresAt, step])

  function clearSensitiveState() {
    setActivationCode('')
    setPassword('')
    setPasswordConfirmation('')
    setNickname('')
  }

  function startOver() {
    clearSensitiveState()
    setCourseId('')
    setUsername('')
    setStep('verify')
    setExpiresAt(null)
    setRemainingSeconds(0)
    setSessionExpired(false)
    setSubmitting(false)
    setFormError(null)
  }

  function backToSignIn() {
    clearSensitiveState()
    setExpiresAt(null)
    navigate('/login')
  }

  async function handleVerify(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (submitting) return

    setSubmitting(true)
    setFormError(null)
    try {
      const verification = await verifyStudentActivation({
        course_id: courseId,
        berkeley_username: username,
        activation_code: activationCode,
      })
      setRemainingSeconds(verification.expires_in_seconds)
      setExpiresAt(Date.now() + verification.expires_in_seconds * 1000)
      setSessionExpired(false)
      setStep('complete')
    } catch (error) {
      setFormError(
        error instanceof AuthApiError && error.code === 'invalid_activation'
          ? INVALID_ACTIVATION_MESSAGE
          : ACTIVATION_UNAVAILABLE_MESSAGE,
      )
    } finally {
      setActivationCode('')
      setSubmitting(false)
    }
  }

  async function handleComplete(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (submitting || sessionExpired) return

    if (password.length < 12 || password.length > 128) {
      setFormError('Password must be between 12 and 128 characters.')
      return
    }
    if (password !== passwordConfirmation) {
      setFormError('Passwords do not match.')
      return
    }
    if (!isValidNickname(nickname)) {
      setFormError('Please choose a valid leaderboard nickname.')
      return
    }

    setSubmitting(true)
    setFormError(null)
    try {
      await completeStudentActivation({
        password,
        password_confirmation: passwordConfirmation,
        nickname: normalizeNickname(nickname),
      })
      clearSensitiveState()
      navigate('/app', { replace: true })
    } catch (error) {
      setPassword('')
      setPasswordConfirmation('')
      if (error instanceof AuthApiError) {
        if (error.code === 'activation_session_expired') {
          setExpiresAt(null)
          setRemainingSeconds(0)
          setSessionExpired(true)
          setFormError(ACTIVATION_SESSION_EXPIRED_MESSAGE)
        } else if (error.code === 'nickname_conflict') {
          setFormError('This nickname is already in use for this course.')
        } else if (error.code === 'invalid_nickname') {
          setFormError('Please choose a valid leaderboard nickname.')
        } else {
          setFormError(ACTIVATION_UNAVAILABLE_MESSAGE)
        }
      } else {
        setFormError(ACTIVATION_UNAVAILABLE_MESSAGE)
      }
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
              Activate your course access.
            </h1>
            <p className="mt-4 max-w-md text-sm leading-6 text-white/80">
              Verify the one-time code from your instructor, then secure your
              account and choose the nickname shown in this course.
            </p>
          </section>

          <section className="p-8 sm:p-12" aria-labelledby="activation-title">
            <p className="font-mono text-xs uppercase tracking-widest text-ink-faint">
              Step {step === 'verify' ? '1' : '2'} of 2
            </p>
            <h2
              id="activation-title"
              className="mt-2 text-2xl font-bold tracking-tight"
            >
              {step === 'verify'
                ? 'Verify activation code'
                : 'Create your account'}
            </h2>

            {step === 'verify' ? (
              <form
                className="mt-7 space-y-5"
                onSubmit={(event) => void handleVerify(event)}
              >
                <div>
                  <label
                    htmlFor="activation-course-id"
                    className="block text-sm font-medium text-ink-dim"
                  >
                    Course ID
                  </label>
                  <input
                    id="activation-course-id"
                    name="course_id"
                    type="text"
                    autoComplete="organization"
                    required
                    maxLength={129}
                    value={courseId}
                    onChange={(event) => setCourseId(event.target.value)}
                    disabled={submitting}
                    className="mt-2 w-full rounded-md border border-line-strong bg-white px-3 py-2.5 text-sm text-ink outline-none transition focus:border-hud-accent focus:ring-2 focus:ring-hud-accent/15 disabled:opacity-60"
                  />
                  <p className="mt-2 text-xs leading-5 text-ink-faint">
                    Enter the course identifier in the format CourseCode-Semester, for example IEOR150-2026FALL.
                  </p>
                </div>

                <div>
                  <label
                    htmlFor="activation-username"
                    className="block text-sm font-medium text-ink-dim"
                  >
                    Berkeley Username
                  </label>
                  <input
                    id="activation-username"
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
                  <label
                    htmlFor="activation-code"
                    className="block text-sm font-medium text-ink-dim"
                  >
                    Activation Code
                  </label>
                  <input
                    id="activation-code"
                    name="activation_code"
                    type="text"
                    autoComplete="one-time-code"
                    autoCapitalize="characters"
                    spellCheck={false}
                    required
                    maxLength={32}
                    value={activationCode}
                    onChange={(event) => setActivationCode(event.target.value)}
                    disabled={submitting}
                    className="mt-2 w-full rounded-md border border-line-strong bg-white px-3 py-2.5 font-mono text-sm uppercase tracking-wider text-ink outline-none transition focus:border-hud-accent focus:ring-2 focus:ring-hud-accent/15 disabled:opacity-60"
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
                  {submitting ? 'Verifying…' : 'Continue'}
                </button>

                <button
                  type="button"
                  onClick={backToSignIn}
                  disabled={submitting}
                  className="w-full rounded-md border border-line-strong px-4 py-2.5 text-sm font-semibold text-ink-dim transition-colors hover:bg-well focus:outline-none focus-visible:ring-2 focus-visible:ring-hud-accent/30 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  Back to Sign In
                </button>
              </form>
            ) : (
              <form
                className="mt-7 space-y-5"
                onSubmit={(event) => void handleComplete(event)}
              >
                <p className="rounded-md border border-blue-200 bg-blue-50 p-3 text-sm text-blue-900" role="status">
                  {sessionExpired
                    ? 'This activation session has expired.'
                    : `Complete activation within ${formatRemainingTime(remainingSeconds)}`}
                </p>

                <div>
                  <label
                    htmlFor="activation-password"
                    className="block text-sm font-medium text-ink-dim"
                  >
                    New Password
                  </label>
                  <input
                    id="activation-password"
                    name="password"
                    type="password"
                    autoComplete="new-password"
                    required
                    minLength={12}
                    maxLength={128}
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    disabled={submitting || sessionExpired}
                    className="mt-2 w-full rounded-md border border-line-strong bg-white px-3 py-2.5 text-sm text-ink outline-none transition focus:border-hud-accent focus:ring-2 focus:ring-hud-accent/15 disabled:opacity-60"
                  />
                  <p className="mt-2 text-xs text-ink-faint">
                    Create a password for your student account in this course. It must contain 12–128 characters.
                  </p>
                </div>

                <div>
                    <label
                      htmlFor="activation-password-confirmation"
                      className="block text-sm font-medium text-ink-dim"
                    >
                      Confirm Password
                    </label>
                    <input
                      id="activation-password-confirmation"
                      name="password_confirmation"
                      type="password"
                      autoComplete="new-password"
                      required
                      minLength={12}
                      maxLength={128}
                      value={passwordConfirmation}
                      onChange={(event) => setPasswordConfirmation(event.target.value)}
                      disabled={submitting || sessionExpired}
                      className="mt-2 w-full rounded-md border border-line-strong bg-white px-3 py-2.5 text-sm text-ink outline-none transition focus:border-hud-accent focus:ring-2 focus:ring-hud-accent/15 disabled:opacity-60"
                    />
                </div>

                <div>
                  <label
                    htmlFor="activation-nickname"
                    className="block text-sm font-medium text-ink-dim"
                  >
                    Leaderboard Nickname
                  </label>
                  <input
                    id="activation-nickname"
                    name="nickname"
                    type="text"
                    autoComplete="off"
                    required
                    minLength={3}
                    maxLength={30}
                    value={nickname}
                    onChange={(event) => setNickname(event.target.value)}
                    disabled={submitting || sessionExpired}
                    aria-describedby="nickname-guidance"
                    className="mt-2 w-full rounded-md border border-line-strong bg-white px-3 py-2.5 text-sm text-ink outline-none transition focus:border-hud-accent focus:ring-2 focus:ring-hud-accent/15 disabled:opacity-60"
                  />
                  <p id="nickname-guidance" className="mt-2 text-xs leading-5 text-ink-faint">
                    This nickname appears on this course leaderboard. Use 3–30 letters,
                    numbers, spaces, hyphens, or underscores.
                  </p>
                </div>

                {formError && (
                  <p
                    className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800"
                    role="alert"
                  >
                    {formError}
                  </p>
                )}

                {!sessionExpired && (
                  <button
                    type="submit"
                    disabled={submitting}
                    className="w-full rounded-md bg-hud-accent px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-hud-accent-hover focus:outline-none focus-visible:ring-2 focus-visible:ring-hud-accent/40 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {submitting ? 'Activating…' : 'Complete Activation'}
                  </button>
                )}

                <div className="grid gap-3 sm:grid-cols-2">
                  <button
                    type="button"
                    onClick={startOver}
                    disabled={submitting}
                    className="rounded-md border border-line-strong px-4 py-2.5 text-sm font-semibold text-ink-dim transition-colors hover:bg-well focus:outline-none focus-visible:ring-2 focus-visible:ring-hud-accent/30 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    Start over
                  </button>
                  <button
                    type="button"
                    onClick={backToSignIn}
                    disabled={submitting}
                    className="rounded-md border border-line-strong px-4 py-2.5 text-sm font-semibold text-ink-dim transition-colors hover:bg-well focus:outline-none focus-visible:ring-2 focus-visible:ring-hud-accent/30 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    Back to Sign In
                  </button>
                </div>
              </form>
            )}
          </section>
        </div>
      </div>
    </main>
  )
}
