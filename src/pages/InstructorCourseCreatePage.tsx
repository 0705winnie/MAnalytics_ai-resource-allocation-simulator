import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthProvider'
import {
  createInstructorCourse,
  InstructorCourseApiError,
} from '../instructor/api'

interface FieldErrors {
  courseCode?: string
  courseName?: string
  semester?: string
}

function validateRequired(
  value: string,
  label: string,
  maximum: number,
): string | undefined {
  const normalized = value.trim()
  if (!normalized) return `${label} is required.`
  if (normalized.length > maximum) {
    return `${label} must be ${maximum} characters or fewer.`
  }
  return undefined
}

export default function InstructorCourseCreatePage() {
  const navigate = useNavigate()
  const { refreshAuth } = useAuth()
  const [courseCode, setCourseCode] = useState('')
  const [courseName, setCourseName] = useState('')
  const [semester, setSemester] = useState('')
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (submitting) return

    const nextFieldErrors: FieldErrors = {
      courseCode: validateRequired(courseCode, 'Course code', 64),
      courseName: validateRequired(courseName, 'Course name', 255),
      semester: validateRequired(semester, 'Semester', 64),
    }
    setFieldErrors(nextFieldErrors)
    setFormError(null)
    if (Object.values(nextFieldErrors).some(Boolean)) return

    setSubmitting(true)
    try {
      const course = await createInstructorCourse({
        course_code: courseCode.trim(),
        course_name: courseName.trim(),
        semester: semester.trim(),
      })
      navigate(`/instructor/courses/${course.id}`, { replace: true })
    } catch (requestError) {
      if (requestError instanceof InstructorCourseApiError) {
        if (requestError.code === 'unauthorized') {
          await refreshAuth()
          setFormError('Course management is temporarily unavailable.')
          return
        }
        if (requestError.code === 'conflict') {
          setFormError('This course code is already in use.')
          return
        }
        if (requestError.code === 'invalid_input') {
          setFormError('Please check the course information and try again.')
          return
        }
        if (requestError.code === 'forbidden') {
          setFormError('You do not have permission to manage this course.')
          return
        }
      }
      setFormError('Course management is temporarily unavailable.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="mx-auto w-full max-w-3xl px-6 py-10 sm:px-10">
      <p className="font-mono text-xs uppercase tracking-[0.18em] text-hud-accent">
        Course management
      </p>
      <h1 className="mt-2 text-3xl font-bold tracking-tight">Create Course</h1>
      <p className="mt-2 text-sm leading-6 text-ink-dim">
        Course codes are unique across the system, ignoring capitalization and
        surrounding spaces.
      </p>

      <form
        onSubmit={(event) => void handleSubmit(event)}
        className="mt-8 rounded-xl border border-line bg-white p-6 shadow-card sm:p-8"
        noValidate
      >
        <div className="space-y-6">
          <div>
            <label htmlFor="course-code" className="block text-sm font-medium">
              Course Code
            </label>
            <input
              id="course-code"
              name="course_code"
              type="text"
              required
              maxLength={64}
              value={courseCode}
              onChange={(event) => setCourseCode(event.target.value)}
              disabled={submitting}
              aria-describedby={fieldErrors.courseCode ? 'course-code-error' : undefined}
              aria-invalid={Boolean(fieldErrors.courseCode)}
              className="mt-2 w-full rounded-md border border-line-strong bg-white px-3 py-2.5 text-sm outline-none focus:border-hud-accent focus:ring-2 focus:ring-hud-accent/15 disabled:opacity-60"
            />
            {fieldErrors.courseCode && (
              <p id="course-code-error" className="mt-2 text-sm text-red-700">
                {fieldErrors.courseCode}
              </p>
            )}
          </div>

          <div>
            <label htmlFor="course-name" className="block text-sm font-medium">
              Course Name
            </label>
            <input
              id="course-name"
              name="course_name"
              type="text"
              required
              maxLength={255}
              value={courseName}
              onChange={(event) => setCourseName(event.target.value)}
              disabled={submitting}
              aria-describedby={fieldErrors.courseName ? 'course-name-error' : undefined}
              aria-invalid={Boolean(fieldErrors.courseName)}
              className="mt-2 w-full rounded-md border border-line-strong bg-white px-3 py-2.5 text-sm outline-none focus:border-hud-accent focus:ring-2 focus:ring-hud-accent/15 disabled:opacity-60"
            />
            {fieldErrors.courseName && (
              <p id="course-name-error" className="mt-2 text-sm text-red-700">
                {fieldErrors.courseName}
              </p>
            )}
          </div>

          <div>
            <label htmlFor="course-semester" className="block text-sm font-medium">
              Semester
            </label>
            <input
              id="course-semester"
              name="semester"
              type="text"
              required
              maxLength={64}
              value={semester}
              onChange={(event) => setSemester(event.target.value)}
              disabled={submitting}
              aria-describedby={fieldErrors.semester ? 'course-semester-error' : undefined}
              aria-invalid={Boolean(fieldErrors.semester)}
              className="mt-2 w-full rounded-md border border-line-strong bg-white px-3 py-2.5 text-sm outline-none focus:border-hud-accent focus:ring-2 focus:ring-hud-accent/15 disabled:opacity-60"
            />
            {fieldErrors.semester && (
              <p id="course-semester-error" className="mt-2 text-sm text-red-700">
                {fieldErrors.semester}
              </p>
            )}
          </div>
        </div>

        {formError && (
          <p
            className="mt-6 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800"
            role="alert"
          >
            {formError}
          </p>
        )}

        <div className="mt-8 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
          <Link
            to="/instructor/courses"
            aria-disabled={submitting}
            className={[
              'rounded-md border border-line-strong px-4 py-2.5 text-center text-sm font-semibold text-ink hover:bg-well',
              submitting ? 'pointer-events-none opacity-60' : '',
            ].join(' ')}
          >
            Cancel
          </Link>
          <button
            type="submit"
            disabled={submitting}
            className="rounded-md bg-hud-accent px-4 py-2.5 text-sm font-semibold text-white hover:bg-hud-accent-hover focus:outline-none focus-visible:ring-2 focus-visible:ring-hud-accent/40 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {submitting ? 'Creating…' : 'Create Course'}
          </button>
        </div>
      </form>
    </main>
  )
}
