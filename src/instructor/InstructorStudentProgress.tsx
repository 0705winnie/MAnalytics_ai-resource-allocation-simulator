import { useEffect, useState } from 'react'
import { useAuth } from '../auth/AuthProvider'
import { getInstructorCourseProgress, InstructorCourseApiError } from './api'
import type { InstructorCourse, StudentProgressListResponse } from './types'

const PAGE_SIZE = 20

function formatTimestamp(value: string | null): string {
  if (value === null) return '—'
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}

function formatRevenue(value: number): string {
  return `$${Math.round(value).toLocaleString()}`
}

interface InstructorStudentProgressProps {
  course: InstructorCourse
}

export default function InstructorStudentProgress({
  course,
}: InstructorStudentProgressProps) {
  const { refreshAuth } = useAuth()
  const [progress, setProgress] = useState<StudentProgressListResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [requestVersion, setRequestVersion] = useState(0)
  const [offset, setOffset] = useState(0)

  useEffect(() => {
    setProgress(null)
    setError(null)
    setOffset(0)
    setLoading(true)
  }, [course.id])

  useEffect(() => {
    const controller = new AbortController()

    async function loadProgress() {
      setLoading(true)
      setError(null)
      try {
        setProgress(
          await getInstructorCourseProgress(
            course.id,
            offset,
            PAGE_SIZE,
            controller.signal,
          ),
        )
      } catch (requestError) {
        if (controller.signal.aborted) return

        setProgress(null)
        if (
          requestError instanceof InstructorCourseApiError
          && requestError.code === 'unauthorized'
        ) {
          await refreshAuth()
          setError('Student progress is temporarily unavailable.')
          return
        }
        setError(
          requestError instanceof InstructorCourseApiError
          && requestError.code === 'not_found'
            ? 'Course not found.'
            : requestError instanceof InstructorCourseApiError
              && requestError.code === 'forbidden'
              ? 'You do not have permission to view this course.'
              : 'Student progress is temporarily unavailable.',
        )
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false)
        }
      }
    }

    void loadProgress()
    return () => controller.abort()
  }, [course.id, offset, refreshAuth, requestVersion])

  return (
    <section className="mt-6">
      {loading && (
        <div
          className="rounded-xl border border-line bg-white p-6 shadow-card"
          aria-live="polite"
        >
          <p className="text-sm font-medium">Loading student progress…</p>
        </div>
      )}

      {!loading && error && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-6">
          <p className="text-sm text-red-800" role="alert">{error}</p>
          <button
            type="button"
            onClick={() => setRequestVersion((current) => current + 1)}
            className="mt-4 rounded-md border border-red-300 bg-white px-4 py-2 text-sm font-semibold text-red-800 hover:bg-red-50"
          >
            Retry
          </button>
        </div>
      )}

      {!loading && !error && progress && (
        <>
          {progress.items.length === 0 ? (
            <div className="rounded-xl border border-line bg-white p-6 shadow-card">
              <p className="text-sm text-ink-faint">
                No students are enrolled in this course yet.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto rounded-xl border border-line bg-white shadow-card">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-line text-left text-ink-faint">
                    <th className="px-5 py-3 font-medium">Student</th>
                    <th className="px-5 py-3 font-medium">Status</th>
                    <th className="px-5 py-3 font-medium">Progress</th>
                    <th className="px-5 py-3 font-medium">Cumulative Revenue</th>
                    <th className="px-5 py-3 font-medium">Warnings</th>
                    <th className="px-5 py-3 font-medium">Last Activity</th>
                  </tr>
                </thead>
                <tbody>
                  {progress.items.map((student) => (
                    <tr
                      key={student.enrollment_id}
                      className="border-b border-line last:border-b-0"
                    >
                      <td className="px-5 py-3">
                        <div className="font-medium">{student.berkeley_username}</div>
                        {student.nickname && (
                          <div className="text-xs text-ink-faint">{student.nickname}</div>
                        )}
                      </td>
                      <td className="px-5 py-3">
                        <div className="capitalize">{student.enrollment_status}</div>
                        {!student.user_is_active && (
                          <div className="text-xs text-red-700">Account inactive</div>
                        )}
                      </td>
                      <td className="px-5 py-3 font-mono">
                        {student.completed_months}/12
                        <div className="font-sans text-xs capitalize text-ink-faint">
                          {student.simulation_status.replace('_', ' ')}
                        </div>
                      </td>
                      <td className="px-5 py-3 font-mono">
                        {formatRevenue(student.cumulative_revenue)}
                      </td>
                      <td className="px-5 py-3 font-mono">{student.warnings_count}</td>
                      <td className="px-5 py-3">{formatTimestamp(student.last_activity)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <nav
            className="mt-6 flex items-center justify-between gap-4"
            aria-label="Student progress pagination"
          >
            <button
              type="button"
              onClick={() => setOffset((current) => Math.max(0, current - PAGE_SIZE))}
              disabled={offset === 0 || loading}
              className="rounded-md border border-line-strong px-4 py-2 text-sm font-semibold text-ink hover:bg-well disabled:cursor-not-allowed disabled:opacity-50"
            >
              Previous
            </button>
            <button
              type="button"
              onClick={() => setOffset((current) => current + PAGE_SIZE)}
              disabled={offset + progress.limit >= progress.total || loading}
              className="rounded-md border border-line-strong px-4 py-2 text-sm font-semibold text-ink hover:bg-well disabled:cursor-not-allowed disabled:opacity-50"
            >
              Next
            </button>
          </nav>
        </>
      )}
    </section>
  )
}
