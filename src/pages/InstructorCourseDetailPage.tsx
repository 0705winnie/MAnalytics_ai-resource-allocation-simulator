import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useAuth } from '../auth/AuthProvider'
import {
  getInstructorCourse,
  InstructorCourseApiError,
} from '../instructor/api'
import type { InstructorCourse } from '../instructor/types'

export default function InstructorCourseDetailPage() {
  const { courseId = '' } = useParams()
  const { refreshAuth } = useAuth()
  const [course, setCourse] = useState<InstructorCourse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [requestVersion, setRequestVersion] = useState(0)

  const retry = useCallback(() => {
    setRequestVersion((current) => current + 1)
  }, [])

  useEffect(() => {
    const controller = new AbortController()

    async function loadCourse() {
      setLoading(true)
      setError(null)
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
          setError('Course management is temporarily unavailable.')
          return
        }
        setError(
          requestError instanceof InstructorCourseApiError
          && requestError.code === 'not_found'
            ? 'Course not found.'
            : requestError instanceof InstructorCourseApiError
              && requestError.code === 'forbidden'
              ? 'You do not have permission to manage this course.'
              : 'Course management is temporarily unavailable.',
        )
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false)
        }
      }
    }

    void loadCourse()
    return () => controller.abort()
  }, [courseId, refreshAuth, requestVersion])

  return (
    <main className="mx-auto w-full max-w-5xl px-6 py-10 sm:px-10">
      <Link
        to="/instructor/courses"
        className="text-sm font-semibold text-hud-accent hover:text-hud-accent-hover"
      >
        ← Back to My Courses
      </Link>

      {loading && (
        <section
          className="mt-6 rounded-xl border border-line bg-white p-6 shadow-card"
          aria-live="polite"
        >
          <p className="text-sm font-medium">Loading course…</p>
        </section>
      )}

      {!loading && error && (
        <section className="mt-6 rounded-xl border border-red-200 bg-red-50 p-6">
          <p className="text-sm text-red-800" role="alert">{error}</p>
          <button
            type="button"
            onClick={retry}
            className="mt-4 rounded-md border border-red-300 bg-white px-4 py-2 text-sm font-semibold text-red-800 hover:bg-red-50"
          >
            Retry
          </button>
        </section>
      )}

      {!loading && !error && course && (
        <>
          <section className="mt-6 rounded-xl border border-line bg-white p-6 shadow-card sm:p-8">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <p className="font-mono text-xs uppercase tracking-wider text-hud-accent">
                  {course.course_code}
                </p>
                <h1 className="mt-2 text-3xl font-bold tracking-tight">
                  {course.course_name}
                </h1>
                <p className="mt-3 text-sm text-ink-dim">{course.semester}</p>
              </div>
              <span
                className={[
                  'w-fit rounded-full px-3 py-1 text-xs font-semibold',
                  course.is_active
                    ? 'bg-emerald-50 text-emerald-700'
                    : 'bg-slate-100 text-slate-600',
                ].join(' ')}
              >
                {course.is_active ? 'Active' : 'Inactive'}
              </span>
            </div>
          </section>

          <section className="mt-6 rounded-xl border border-line bg-white p-6 shadow-card sm:p-8">
            <p className="font-mono text-xs uppercase tracking-wider text-ink-faint">
              Course administration
            </p>
            <h2 className="mt-2 text-xl font-semibold">Roster management</h2>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-ink-dim">
              View enrolled students, search or filter activation status,
              import a roster CSV, and regenerate activation codes for eligible
              pending enrollments.
            </p>
            <Link
              to={`/instructor/courses/${course.id}/roster`}
              className="mt-5 inline-flex rounded-md bg-hud-accent px-4 py-2.5 text-sm font-semibold text-white hover:bg-hud-accent-hover focus:outline-none focus-visible:ring-2 focus-visible:ring-hud-accent/40 focus-visible:ring-offset-2"
            >
              Manage Roster
            </Link>
          </section>
        </>
      )}
    </main>
  )
}
