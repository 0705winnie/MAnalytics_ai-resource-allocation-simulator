import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../auth/AuthProvider'
import {
  getInstructorCourses,
  InstructorCourseApiError,
} from '../instructor/api'
import InstructorBreadcrumbs from '../instructor/InstructorBreadcrumbs'
import type { InstructorCourseListResponse } from '../instructor/types'

const COURSE_SERVICE_ERROR = 'Course management is temporarily unavailable.'

export default function InstructorCoursesPage() {
  const { refreshAuth } = useAuth()
  const [courses, setCourses] = useState<InstructorCourseListResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [requestVersion, setRequestVersion] = useState(0)

  const retry = useCallback(() => {
    setRequestVersion((current) => current + 1)
  }, [])

  useEffect(() => {
    const controller = new AbortController()

    async function loadCourses() {
      setLoading(true)
      setError(null)
      try {
        setCourses(await getInstructorCourses(controller.signal))
      } catch (requestError) {
        if (controller.signal.aborted) return

        setCourses(null)
        if (
          requestError instanceof InstructorCourseApiError
          && requestError.code === 'unauthorized'
        ) {
          await refreshAuth()
          setError(COURSE_SERVICE_ERROR)
          return
        }
        setError(
          requestError instanceof InstructorCourseApiError
          && requestError.code === 'forbidden'
            ? 'You do not have permission to view Instructor courses.'
            : COURSE_SERVICE_ERROR,
        )
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false)
        }
      }
    }

    void loadCourses()
    return () => controller.abort()
  }, [refreshAuth, requestVersion])

  return (
    <main className="mx-auto w-full max-w-6xl px-6 py-10 sm:px-10">
      <InstructorBreadcrumbs
        items={[{ label: 'My Courses', current: true }]}
      />

      <div className="mt-6 flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.18em] text-hud-accent">
            Course management
          </p>
          <h1 className="mt-2 text-3xl font-bold tracking-tight">My Courses</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-ink-dim">
            Open a course to manage its roster and access course-level tools.
          </p>
        </div>
        <Link
          to="/instructor/courses/new"
          className="inline-flex justify-center rounded-md bg-hud-accent px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-hud-accent-hover focus:outline-none focus-visible:ring-2 focus-visible:ring-hud-accent/40 focus-visible:ring-offset-2"
        >
          Create Course
        </Link>
      </div>

      {loading && (
        <section
          className="mt-8 rounded-xl border border-line bg-white p-6 shadow-card"
          aria-live="polite"
        >
          <p className="text-sm font-medium">Loading your courses…</p>
        </section>
      )}

      {!loading && error && (
        <section className="mt-8 rounded-xl border border-red-200 bg-red-50 p-6">
          <p className="text-sm text-red-800" role="alert">{error}</p>
          <button
            type="button"
            onClick={retry}
            className="mt-4 rounded-md border border-red-300 bg-white px-4 py-2 text-sm font-semibold text-red-800 hover:bg-red-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-red-300"
          >
            Retry
          </button>
        </section>
      )}

      {!loading && !error && courses?.items.length === 0 && (
        <section className="mt-8 rounded-xl border border-dashed border-line-strong bg-white p-8 text-center shadow-card">
          <h2 className="text-xl font-semibold">No courses yet</h2>
          <p className="mx-auto mt-2 max-w-lg text-sm leading-6 text-ink-dim">
            Create your first course instance before importing a roster or
            managing student enrollments.
          </p>
          <Link
            to="/instructor/courses/new"
            className="mt-5 inline-flex rounded-md bg-hud-accent px-4 py-2.5 text-sm font-semibold text-white hover:bg-hud-accent-hover"
          >
            Create your first course
          </Link>
        </section>
      )}

      {!loading && !error && courses && courses.items.length > 0 && (
        <section className="mt-8" aria-label="Instructor courses">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm text-ink-dim">
              {courses.total} {courses.total === 1 ? 'course' : 'courses'}
            </p>
            {courses.total > courses.items.length && (
              <p className="text-xs text-ink-faint">
                Showing the first {courses.items.length} courses.
              </p>
            )}
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            {courses.items.map((course) => (
              <article
                key={course.id}
                className="flex flex-col rounded-xl border border-line bg-white p-6 shadow-card"
              >
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className="font-mono text-xs uppercase tracking-wider text-hud-accent">
                      {course.course_code}
                    </p>
                    <h2 className="mt-2 text-xl font-semibold">{course.course_name}</h2>
                  </div>
                  <span
                    className={[
                      'rounded-full px-2.5 py-1 text-xs font-semibold',
                      course.is_active
                        ? 'bg-emerald-50 text-emerald-700'
                        : 'bg-slate-100 text-slate-600',
                    ].join(' ')}
                  >
                    {course.is_active ? 'Active' : 'Inactive'}
                  </span>
                </div>
                <p className="mt-3 text-sm text-ink-dim">{course.semester}</p>
                <div className="mt-auto pt-6">
                  <Link
                    to={`/instructor/courses/${course.id}`}
                    className="inline-flex rounded-md border border-line-strong px-4 py-2 text-sm font-semibold text-ink hover:bg-well focus:outline-none focus-visible:ring-2 focus-visible:ring-hud-accent/30"
                  >
                    Open Course
                  </Link>
                </div>
              </article>
            ))}
          </div>
        </section>
      )}
    </main>
  )
}
