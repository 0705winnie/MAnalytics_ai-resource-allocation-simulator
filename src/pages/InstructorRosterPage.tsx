import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type FormEvent,
} from 'react'
import { Link, useParams } from 'react-router-dom'
import { useAuth } from '../auth/AuthProvider'
import CourseSectionNavigation from '../instructor/CourseSectionNavigation'
import {
  getInstructorCourse,
  getInstructorEnrollments,
  InstructorCourseApiError,
  regenerateInstructorActivationCode,
} from '../instructor/api'
import InstructorBreadcrumbs, {
  courseBreadcrumbLabel,
} from '../instructor/InstructorBreadcrumbs'
import type {
  ActivationCodeReissueResult,
  EnrollmentActivationFilter,
  InstructorCourse,
  InstructorEnrollment,
  InstructorEnrollmentListResponse,
} from '../instructor/types'

const PAGE_SIZE = 20
const REISSUE_FILENAME = 'regenerated-activation-code.csv'

function formatTimestamp(value: string | null): string {
  if (value === null) return '—'
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}

function enrollmentStatusLabel(status: InstructorEnrollment['status']): string {
  if (status === 'active') return 'Active'
  if (status === 'disabled') return 'Disabled'
  return 'Pending'
}

export default function InstructorRosterPage() {
  const { courseId = '' } = useParams()
  const { refreshAuth } = useAuth()
  const objectUrls = useRef(new Set<string>())
  const [course, setCourse] = useState<InstructorCourse | null>(null)
  const [courseLoading, setCourseLoading] = useState(true)
  const [courseError, setCourseError] = useState<string | null>(null)
  const [courseRequestVersion, setCourseRequestVersion] = useState(0)
  const [roster, setRoster] = useState<InstructorEnrollmentListResponse | null>(null)
  const [rosterLoading, setRosterLoading] = useState(true)
  const [rosterError, setRosterError] = useState<string | null>(null)
  const [rosterRequestVersion, setRosterRequestVersion] = useState(0)
  const [searchInput, setSearchInput] = useState('')
  const [appliedSearch, setAppliedSearch] = useState('')
  const [activationFilter, setActivationFilter] = useState<
    EnrollmentActivationFilter | 'all'
  >('all')
  const [offset, setOffset] = useState(0)
  const [confirmingEnrollmentId, setConfirmingEnrollmentId] = useState<
    string | null
  >(null)
  const [regenerating, setRegenerating] = useState(false)
  const [regenerationError, setRegenerationError] = useState<string | null>(null)
  const [reissueResult, setReissueResult] = useState<
    ActivationCodeReissueResult | null
  >(null)
  const [reissueDownloaded, setReissueDownloaded] = useState(false)
  const hasUndownloadedReissue = reissueResult !== null && !reissueDownloaded

  const revokeObjectUrls = useCallback(() => {
    for (const url of objectUrls.current) {
      URL.revokeObjectURL(url)
    }
    objectUrls.current.clear()
  }, [])

  useEffect(() => revokeObjectUrls, [revokeObjectUrls])

  useEffect(() => {
    revokeObjectUrls()
    setCourse(null)
    setCourseLoading(true)
    setCourseError(null)
    setReissueResult(null)
    setReissueDownloaded(false)
    setConfirmingEnrollmentId(null)
    setRegenerationError(null)
    setRoster(null)
    setRosterError(null)
    setSearchInput('')
    setAppliedSearch('')
    setActivationFilter('all')
    setOffset(0)
  }, [courseId, revokeObjectUrls])

  useEffect(() => {
    const controller = new AbortController()

    async function loadCourse() {
      setCourseLoading(true)
      setCourseError(null)
      try {
        setCourse(await getInstructorCourse(courseId, controller.signal))
      } catch (requestError) {
        if (controller.signal.aborted) return

        setCourse(null)
        if (
          requestError instanceof InstructorCourseApiError
          && requestError.code === 'unauthorized'
        ) {
          await refreshAuth()
          setCourseError('Roster management is temporarily unavailable.')
          return
        }
        setCourseError(
          requestError instanceof InstructorCourseApiError
          && requestError.code === 'not_found'
            ? 'Course not found.'
            : requestError instanceof InstructorCourseApiError
              && requestError.code === 'forbidden'
              ? 'You do not have permission to manage this course.'
              : 'Roster management is temporarily unavailable.',
        )
      } finally {
        if (!controller.signal.aborted) {
          setCourseLoading(false)
        }
      }
    }

    void loadCourse()
    return () => controller.abort()
  }, [courseId, courseRequestVersion, refreshAuth])

  useEffect(() => {
    if (!course || course.id !== courseId) {
      setRosterLoading(false)
      return
    }
    const controller = new AbortController()

    async function loadRoster() {
      setRosterLoading(true)
      setRosterError(null)
      try {
        setRoster(await getInstructorEnrollments(
          courseId,
          {
            offset,
            limit: PAGE_SIZE,
            search: appliedSearch || undefined,
            activation_status: (
              activationFilter === 'all' ? undefined : activationFilter
            ),
          },
          controller.signal,
        ))
      } catch (requestError) {
        if (controller.signal.aborted) return

        setRoster(null)
        if (
          requestError instanceof InstructorCourseApiError
          && requestError.code === 'unauthorized'
        ) {
          await refreshAuth()
          setRosterError('Roster management is temporarily unavailable.')
          return
        }
        setRosterError(
          requestError instanceof InstructorCourseApiError
          && requestError.code === 'not_found'
            ? 'Course not found.'
            : requestError instanceof InstructorCourseApiError
              && requestError.code === 'forbidden'
              ? 'You do not have permission to manage this course.'
              : 'Roster management is temporarily unavailable.',
        )
      } finally {
        if (!controller.signal.aborted) {
          setRosterLoading(false)
        }
      }
    }

    void loadRoster()
    return () => controller.abort()
  }, [
    activationFilter,
    appliedSearch,
    course,
    courseId,
    offset,
    refreshAuth,
    rosterRequestVersion,
  ])

  useEffect(() => {
    if (
      roster
      && roster.total > 0
      && roster.items.length === 0
      && offset > 0
      && offset >= roster.total
    ) {
      const lastPageOffset = (
        Math.floor((roster.total - 1) / PAGE_SIZE) * PAGE_SIZE
      )
      if (lastPageOffset !== offset) {
        setOffset(lastPageOffset)
      }
    }
  }, [offset, roster])

  function handleSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setAppliedSearch(searchInput.trim())
    setOffset(0)
  }

  function beginRegeneration(enrollmentId: string) {
    if (regenerating || hasUndownloadedReissue) return
    if (reissueResult) {
      revokeObjectUrls()
      setReissueResult(null)
      setReissueDownloaded(false)
    }
    setRegenerationError(null)
    setConfirmingEnrollmentId(enrollmentId)
  }

  async function confirmRegeneration() {
    if (
      regenerating
      || hasUndownloadedReissue
      || !course
      || !roster
      || confirmingEnrollmentId === null
    ) {
      return
    }
    const enrollment = roster.items.find(
      (item) => item.enrollment_id === confirmingEnrollmentId,
    )
    if (!enrollment) return

    setRegenerating(true)
    setRegenerationError(null)
    try {
      const result = await regenerateInstructorActivationCode(course, enrollment)
      setReissueResult(result)
      setReissueDownloaded(false)
      setConfirmingEnrollmentId(null)
      setRosterRequestVersion((current) => current + 1)
    } catch (requestError) {
      if (requestError instanceof InstructorCourseApiError) {
        if (requestError.code === 'unauthorized') {
          await refreshAuth()
          setRegenerationError('Activation code service is temporarily unavailable.')
          return
        }
        if (requestError.code === 'forbidden') {
          setRegenerationError(
            'You do not have permission to manage this course.',
          )
          return
        }
        if (requestError.code === 'not_found') {
          setRegenerationError('Course or enrollment not found.')
          return
        }
        if (requestError.code === 'conflict') {
          setRegenerationError(
            'A new activation code cannot be generated for this enrollment.',
          )
          setRosterRequestVersion((current) => current + 1)
          return
        }
        if (requestError.code === 'invalid_input') {
          setRegenerationError('The activation code request is invalid.')
          return
        }
      }
      setRegenerationError('Activation code service is temporarily unavailable.')
    } finally {
      setRegenerating(false)
    }
  }

  function downloadReissue() {
    if (!reissueResult) return

    const url = URL.createObjectURL(reissueResult.csv)
    objectUrls.current.add(url)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = REISSUE_FILENAME
    anchor.click()
    setReissueDownloaded(true)
    window.setTimeout(() => {
      URL.revokeObjectURL(url)
      objectUrls.current.delete(url)
    }, 0)
  }

  function closeReissue() {
    if (!reissueDownloaded) return
    revokeObjectUrls()
    setReissueResult(null)
    setReissueDownloaded(false)
  }

  const noResultsFromFilter = (
    roster?.total === 0
    && (Boolean(appliedSearch) || activationFilter !== 'all')
  )
  const visibleCourse = course?.id === courseId ? course : null

  return (
    <main className="mx-auto w-full max-w-6xl px-6 py-10 sm:px-10">
      <InstructorBreadcrumbs
        items={[
          {
            label: 'My Courses',
            to: '/instructor/courses',
            disabled: regenerating,
          },
          ...(visibleCourse
            ? [{
              label: courseBreadcrumbLabel(
                visibleCourse.course_code,
                visibleCourse.semester,
              ),
              to: `/instructor/courses/${visibleCourse.id}`,
              disabled: regenerating,
            }]
            : []),
          { label: 'Roster', current: true },
        ]}
      />

      {(courseLoading || (course !== null && course.id !== courseId)) && (
        <section
          className="mt-6 rounded-xl border border-line bg-white p-6 shadow-card"
          aria-live="polite"
        >
          <p className="text-sm font-medium">Loading course…</p>
        </section>
      )}

      {!courseLoading && course === null && courseError && (
        <section className="mt-6 rounded-xl border border-red-200 bg-red-50 p-6">
          <p className="text-sm text-red-800" role="alert">{courseError}</p>
          <button
            type="button"
            onClick={() => setCourseRequestVersion((current) => current + 1)}
            className="mt-4 rounded-md border border-red-300 bg-white px-4 py-2 text-sm font-semibold text-red-800 hover:bg-red-50"
          >
            Retry
          </button>
        </section>
      )}

      {!courseLoading && !courseError && course?.id === courseId && (
        <>
          <header className="mt-6 flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="font-mono text-xs uppercase tracking-wider text-hud-accent">
                {course.course_code}
              </p>
              <h1 className="mt-2 text-3xl font-bold tracking-tight">
                Roster Management
              </h1>
              <p className="mt-2 text-sm text-ink-dim">{course.course_name}</p>
            </div>
            {course.is_active ? (
              <Link
                to={`/instructor/courses/${course.id}/roster/import`}
                className="inline-flex justify-center rounded-md bg-hud-accent px-4 py-2.5 text-sm font-semibold text-white hover:bg-hud-accent-hover focus:outline-none focus-visible:ring-2 focus-visible:ring-hud-accent/40 focus-visible:ring-offset-2"
              >
                Import Roster
              </Link>
            ) : (
              <span className="rounded-md border border-line bg-well px-4 py-2.5 text-sm font-semibold text-ink-faint">
                Course is inactive
              </span>
            )}
          </header>

          <CourseSectionNavigation
            courseId={course.id}
            currentSection="roster"
            navigationDisabled={regenerating}
          />

          <section className="mt-8 rounded-xl border border-line bg-white p-5 shadow-card sm:p-6">
            <form
              onSubmit={handleSearch}
              className="grid gap-4 md:grid-cols-[minmax(0,1fr)_220px_auto]"
            >
              <div>
                <label htmlFor="roster-search" className="block text-sm font-medium">
                  Search Berkeley Username
                </label>
                <input
                  id="roster-search"
                  type="search"
                  maxLength={64}
                  value={searchInput}
                  onChange={(event) => setSearchInput(event.target.value)}
                  className="mt-2 w-full rounded-md border border-line-strong px-3 py-2.5 text-sm outline-none focus:border-hud-accent focus:ring-2 focus:ring-hud-accent/15"
                />
              </div>
              <div>
                <label htmlFor="activation-filter" className="block text-sm font-medium">
                  Activation Status
                </label>
                <select
                  id="activation-filter"
                  value={activationFilter}
                  onChange={(event) => {
                    setActivationFilter(
                      event.target.value as EnrollmentActivationFilter | 'all',
                    )
                    setOffset(0)
                  }}
                  className="mt-2 w-full rounded-md border border-line-strong bg-white px-3 py-2.5 text-sm outline-none focus:border-hud-accent focus:ring-2 focus:ring-hud-accent/15"
                >
                  <option value="all">All</option>
                  <option value="pending">Pending activation</option>
                  <option value="activated">Activated</option>
                </select>
              </div>
              <button
                type="submit"
                className="self-end rounded-md border border-line-strong px-4 py-2.5 text-sm font-semibold text-ink hover:bg-well focus:outline-none focus-visible:ring-2 focus-visible:ring-hud-accent/30"
              >
                Search
              </button>
            </form>
          </section>

          {regenerationError && (
            <p
              className="mt-5 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800"
              role="alert"
            >
              {regenerationError}
            </p>
          )}

          {reissueResult && (
            <section className="mt-5 rounded-xl border border-amber-300 bg-amber-50 p-5">
              <h2 className="font-semibold text-amber-950">
                Download the new activation code now
              </h2>
              <p className="mt-2 text-sm leading-6 text-amber-900">
                The previous code no longer works. This one-time CSV cannot be
                recovered after refresh or navigation and must be distributed
                securely to the intended student.
              </p>
              <div className="mt-4 flex flex-col gap-3 sm:flex-row">
                <button
                  type="button"
                  onClick={downloadReissue}
                  className="rounded-md bg-hud-accent px-4 py-2.5 text-sm font-semibold text-white hover:bg-hud-accent-hover"
                >
                  Download New Activation Code CSV
                </button>
                {reissueDownloaded && (
                  <button
                    type="button"
                    onClick={closeReissue}
                    className="rounded-md border border-line-strong bg-white px-4 py-2.5 text-sm font-semibold text-ink hover:bg-well"
                  >
                    Close Download Result
                  </button>
                )}
              </div>
              {reissueDownloaded && (
                <p className="mt-3 text-sm font-medium text-amber-900" role="status">
                  Download started. Keep the file secure.
                </p>
              )}
            </section>
          )}

          {rosterLoading && (
            <section
              className="mt-6 rounded-xl border border-line bg-white p-6 shadow-card"
              aria-live="polite"
            >
              <p className="text-sm font-medium">Loading course roster…</p>
            </section>
          )}

          {!rosterLoading && rosterError && (
            <section className="mt-6 rounded-xl border border-red-200 bg-red-50 p-6">
              <p className="text-sm text-red-800" role="alert">{rosterError}</p>
              <button
                type="button"
                onClick={() => setRosterRequestVersion((current) => current + 1)}
                className="mt-4 rounded-md border border-red-300 bg-white px-4 py-2 text-sm font-semibold text-red-800 hover:bg-red-50"
              >
                Retry
              </button>
            </section>
          )}

          {!rosterLoading && !rosterError && roster?.total === 0 && (
            <section className="mt-6 rounded-xl border border-dashed border-line-strong bg-white p-8 text-center shadow-card">
              <h2 className="text-xl font-semibold">
                {noResultsFromFilter
                  ? 'No students match this search'
                  : 'No students are enrolled in this course yet'}
              </h2>
              <p className="mt-2 text-sm text-ink-dim">
                {noResultsFromFilter
                  ? 'Adjust the username search or activation filter and try again.'
                  : 'Import a roster to add students.'}
              </p>
            </section>
          )}

          {!rosterLoading && !rosterError && roster && roster.items.length > 0 && (
            <section className="mt-6" aria-label="Course roster">
              <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                <p className="text-sm text-ink-dim">
                  Showing {roster.offset + 1}–
                  {roster.offset + roster.items.length} of {roster.total}
                </p>
                {hasUndownloadedReissue && (
                  <p className="text-sm font-medium text-amber-800">
                    Download the current code before generating another.
                  </p>
                )}
              </div>

              <div className="grid gap-4 lg:grid-cols-2">
                {roster.items.map((enrollment) => {
                  const eligibleForRegeneration = (
                    course.is_active
                    && enrollment.status === 'pending'
                    && !enrollment.activated
                    && enrollment.user_is_active
                  )
                  const isConfirming = (
                    confirmingEnrollmentId === enrollment.enrollment_id
                  )
                  return (
                    <article
                      key={enrollment.enrollment_id}
                      className="rounded-xl border border-line bg-white p-5 shadow-card"
                    >
                      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                        <div className="min-w-0">
                          <h2 className="break-words font-semibold">
                            {enrollment.berkeley_username}
                          </h2>
                          <p className="mt-1 break-words text-sm text-ink-dim">
                            Course nickname: {enrollment.nickname ?? 'Not set'}
                          </p>
                        </div>
                        <span
                          className={[
                            'w-fit rounded-full px-2.5 py-1 text-xs font-semibold',
                            enrollment.activated
                              ? 'bg-emerald-50 text-emerald-700'
                              : 'bg-amber-50 text-amber-800',
                          ].join(' ')}
                        >
                          {enrollment.activated
                            ? 'Activated'
                            : 'Pending activation'}
                        </span>
                      </div>

                      <dl className="mt-5 grid grid-cols-2 gap-3 text-sm">
                        <div>
                          <dt className="text-ink-faint">Enrollment status</dt>
                          <dd className="mt-1 font-medium">
                            {enrollmentStatusLabel(enrollment.status)}
                          </dd>
                        </div>
                        <div>
                          <dt className="text-ink-faint">Account status</dt>
                          <dd className="mt-1 font-medium">
                            {enrollment.user_is_active ? 'Active' : 'Inactive'}
                          </dd>
                        </div>
                        <div className="col-span-2">
                          <dt className="text-ink-faint">Activated at</dt>
                          <dd className="mt-1 font-medium">
                            {formatTimestamp(enrollment.activation_used_at)}
                          </dd>
                        </div>
                      </dl>

                      {eligibleForRegeneration && !isConfirming && (
                        <button
                          type="button"
                          onClick={() => beginRegeneration(enrollment.enrollment_id)}
                          disabled={regenerating || hasUndownloadedReissue}
                          className="mt-5 w-full rounded-md border border-line-strong px-4 py-2.5 text-sm font-semibold text-ink hover:bg-well focus:outline-none focus-visible:ring-2 focus-visible:ring-hud-accent/30 disabled:cursor-not-allowed disabled:opacity-60 sm:w-auto"
                        >
                          Generate New Activation Code
                        </button>
                      )}

                      {isConfirming && (
                        <div className="mt-5 rounded-md border border-amber-200 bg-amber-50 p-4">
                          <p className="text-sm leading-6 text-amber-950">
                            The previous activation code will stop working. The
                            new code must be downloaded immediately. The
                            Student&apos;s existing password is not changed, and
                            this affects only this course enrollment.
                          </p>
                          <div className="mt-4 flex flex-col gap-2 sm:flex-row">
                            <button
                              type="button"
                              onClick={() => void confirmRegeneration()}
                              disabled={regenerating}
                              className="rounded-md bg-hud-accent px-4 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
                            >
                              {regenerating ? 'Generating…' : 'Confirm New Code'}
                            </button>
                            <button
                              type="button"
                              onClick={() => setConfirmingEnrollmentId(null)}
                              disabled={regenerating}
                              className="rounded-md border border-line-strong bg-white px-4 py-2 text-sm font-semibold text-ink disabled:cursor-not-allowed disabled:opacity-60"
                            >
                              Cancel
                            </button>
                          </div>
                        </div>
                      )}
                    </article>
                  )
                })}
              </div>

              <nav
                className="mt-6 flex items-center justify-between gap-4"
                aria-label="Roster pagination"
              >
                <button
                  type="button"
                  onClick={() => setOffset((current) => Math.max(0, current - PAGE_SIZE))}
                  disabled={offset === 0 || rosterLoading}
                  className="rounded-md border border-line-strong px-4 py-2 text-sm font-semibold text-ink hover:bg-well disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Previous
                </button>
                <button
                  type="button"
                  onClick={() => setOffset((current) => current + PAGE_SIZE)}
                  disabled={offset + roster.limit >= roster.total || rosterLoading}
                  className="rounded-md border border-line-strong px-4 py-2 text-sm font-semibold text-ink hover:bg-well disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Next
                </button>
              </nav>
            </section>
          )}
        </>
      )}
    </main>
  )
}
