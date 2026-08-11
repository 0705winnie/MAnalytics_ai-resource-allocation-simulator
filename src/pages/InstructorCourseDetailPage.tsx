import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useAuth } from '../auth/AuthProvider'
import CourseSectionNavigation, {
  type CourseSection,
} from '../instructor/CourseSectionNavigation'
import {
  getInstructorCourse,
  deleteInstructorCourse,
  InstructorCourseApiError,
} from '../instructor/api'
import InstructorBreadcrumbs, {
  courseBreadcrumbLabel,
} from '../instructor/InstructorBreadcrumbs'
import InstructorRosterManagement from '../instructor/InstructorRosterManagement'
import InstructorStudentProgress from '../instructor/InstructorStudentProgress'
import InstructorLeaderboards from '../instructor/InstructorLeaderboards'
import type { InstructorCourse } from '../instructor/types'

export default function InstructorCourseDetailPage() {
  const { courseId = '' } = useParams()
  const navigate = useNavigate()
  const { refreshAuth } = useAuth()
  const [course, setCourse] = useState<InstructorCourse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [requestVersion, setRequestVersion] = useState(0)
  const [rosterNavigationLocked, setRosterNavigationLocked] = useState(false)
  const [activeSection, setActiveSection] = useState<CourseSection>('roster')
  const [showDeleteConfirmation, setShowDeleteConfirmation] = useState(false)
  const [deleteConfirmation, setDeleteConfirmation] = useState('')
  const [deletingCourse, setDeletingCourse] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)

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

  const visibleCourse = course?.id === courseId ? course : null

  async function confirmCourseDeletion() {
    if (!visibleCourse || deleteConfirmation !== 'DELETE' || deletingCourse) return
    setDeletingCourse(true)
    setDeleteError(null)
    try {
      await deleteInstructorCourse(visibleCourse.id)
      navigate('/instructor/courses', { replace: true })
    } catch (requestError) {
      if (
        requestError instanceof InstructorCourseApiError
        && requestError.code === 'unauthorized'
      ) {
        await refreshAuth()
      }
      setDeleteError(
        requestError instanceof InstructorCourseApiError
        && requestError.code === 'not_found'
          ? 'Course not found.'
          : 'The course could not be deleted.',
      )
      setDeletingCourse(false)
    }
  }

  return (
    <main className="mx-auto w-full max-w-6xl px-6 py-10 sm:px-10">
      <InstructorBreadcrumbs
        items={[
          {
            label: '← My Courses',
            to: '/instructor/courses',
            disabled: rosterNavigationLocked,
            back: true,
          },
          {
            label: visibleCourse
              ? courseBreadcrumbLabel(
                visibleCourse.course_code,
                visibleCourse.semester,
              )
              : 'Course',
            current: true,
          },
        ]}
      />

      {(loading || (course !== null && course.id !== courseId)) && (
        <section
          className="mt-6 rounded-xl border border-line bg-white p-6 shadow-card"
          aria-live="polite"
        >
          <p className="text-sm font-medium">Loading course…</p>
        </section>
      )}

      {!loading && !visibleCourse && error && (
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

      {!loading && !error && visibleCourse && (
        <>
          <section className="mt-6 rounded-xl border border-line bg-white p-6 shadow-card sm:p-8">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <p className="font-mono text-xs uppercase tracking-wider text-hud-accent">
                  {visibleCourse.course_code}
                </p>
                <h1 className="mt-2 text-3xl font-bold tracking-tight">
                  {visibleCourse.course_name}
                </h1>
                <p className="mt-3 text-sm text-ink-dim">
                  {visibleCourse.semester}
                </p>
              </div>
              <span
                className={[
                  'w-fit rounded-full px-3 py-1 text-xs font-semibold',
                  visibleCourse.is_active
                    ? 'bg-emerald-50 text-emerald-700'
                    : 'bg-slate-100 text-slate-600',
                ].join(' ')}
              >
                {visibleCourse.is_active ? 'Active' : 'Inactive'}
              </span>
            </div>
          </section>

          <CourseSectionNavigation
            activeSection={activeSection}
            onSectionChange={setActiveSection}
            navigationDisabled={rosterNavigationLocked || deletingCourse}
          />

          {activeSection === 'roster' && (
            <InstructorRosterManagement
              course={visibleCourse}
              onNavigationLockChange={setRosterNavigationLocked}
            />
          )}

          {activeSection === 'progress' && (
            <InstructorStudentProgress course={visibleCourse} />
          )}

          {activeSection === 'leaderboards' && (
            <InstructorLeaderboards course={visibleCourse} />
          )}

          <section className="mt-10 rounded-xl border border-red-200 bg-red-50 p-6">
            <h2 className="text-lg font-semibold text-red-950">Danger Zone</h2>
            <p className="mt-2 text-sm leading-6 text-red-900">
              Delete this course only if it was created by mistake. This action cannot be undone.
            </p>
            {!showDeleteConfirmation ? (
              <button
                type="button"
                onClick={() => {
                  setShowDeleteConfirmation(true)
                  setDeleteConfirmation('')
                  setDeleteError(null)
                }}
                disabled={rosterNavigationLocked}
                className="mt-4 rounded-md border border-red-300 bg-white px-4 py-2 text-sm font-semibold text-red-700 hover:bg-red-100 disabled:opacity-60"
              >
                Delete Course…
              </button>
            ) : (
              <div className="mt-4 rounded-md border border-red-300 bg-white p-5">
                <p className="font-semibold text-red-950">
                  Delete {visibleCourse.course_code} {visibleCourse.semester}?
                </p>
                <p className="mt-2 text-sm leading-6 text-red-900">
                  This permanently deletes this course, all course enrollments, all simulation progress, and all monthly results. Student user accounts will NOT be deleted.
                </p>
                <label htmlFor="delete-course-confirmation" className="mt-4 block text-sm font-medium text-red-950">
                  Type DELETE to confirm
                </label>
                <input
                  id="delete-course-confirmation"
                  value={deleteConfirmation}
                  onChange={(event) => setDeleteConfirmation(event.target.value)}
                  disabled={deletingCourse}
                  autoComplete="off"
                  className="mt-2 w-full max-w-xs rounded-md border border-red-300 px-3 py-2 font-mono text-sm"
                />
                {deleteError && <p className="mt-3 text-sm text-red-800" role="alert">{deleteError}</p>}
                <div className="mt-4 flex flex-wrap gap-3">
                  <button
                    type="button"
                    onClick={() => void confirmCourseDeletion()}
                    disabled={deleteConfirmation !== 'DELETE' || deletingCourse}
                    className="rounded-md bg-red-700 px-4 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {deletingCourse ? 'Deleting…' : 'Delete Course'}
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowDeleteConfirmation(false)}
                    disabled={deletingCourse}
                    className="rounded-md border border-line-strong px-4 py-2 text-sm font-semibold text-ink disabled:opacity-60"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}
          </section>
        </>
      )}
    </main>
  )
}
