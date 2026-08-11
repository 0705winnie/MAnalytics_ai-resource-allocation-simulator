import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
  type FormEvent,
} from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useAuth } from '../auth/AuthProvider'
import CourseSectionNavigation from '../instructor/CourseSectionNavigation'
import {
  getInstructorCourse,
  importInstructorRoster,
  InstructorCourseApiError,
  MAX_ROSTER_FILE_BYTES,
} from '../instructor/api'
import InstructorBreadcrumbs, {
  courseBreadcrumbLabel,
} from '../instructor/InstructorBreadcrumbs'
import type {
  InstructorCourse,
  RosterImportResult,
} from '../instructor/types'

const ROSTER_FILENAME = 'roster-activation-codes.csv'

export default function InstructorRosterImportPage() {
  const { courseId = '' } = useParams()
  const navigate = useNavigate()
  const { refreshAuth } = useAuth()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const activeObjectUrls = useRef(new Set<string>())
  const [course, setCourse] = useState<InstructorCourse | null>(null)
  const [courseLoading, setCourseLoading] = useState(true)
  const [courseError, setCourseError] = useState<string | null>(null)
  const [courseRequestVersion, setCourseRequestVersion] = useState(0)
  const [file, setFile] = useState<File | null>(null)
  const [importing, setImporting] = useState(false)
  const [importError, setImportError] = useState<string | null>(null)
  const [result, setResult] = useState<RosterImportResult | null>(null)
  const [downloaded, setDownloaded] = useState(false)
  const hasUndownloadedCodes = (
    result !== null
    && result.summary.created > 0
    && !downloaded
  )

  const revokeObjectUrls = useCallback(() => {
    for (const url of activeObjectUrls.current) {
      URL.revokeObjectURL(url)
    }
    activeObjectUrls.current.clear()
  }, [])

  useEffect(() => revokeObjectUrls, [revokeObjectUrls])

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
          setCourseError('Roster import is temporarily unavailable.')
          return
        }
        setCourseError(
          requestError instanceof InstructorCourseApiError
          && requestError.code === 'not_found'
            ? 'Course not found.'
            : requestError instanceof InstructorCourseApiError
              && requestError.code === 'forbidden'
              ? 'You do not have permission to manage this course.'
              : 'Roster import is temporarily unavailable.',
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

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    if (hasUndownloadedCodes) {
      event.target.value = ''
      return
    }

    const selectedFile = event.target.files?.[0] ?? null
    setResult(null)
    setDownloaded(false)
    setImportError(null)
    if (selectedFile && selectedFile.size > MAX_ROSTER_FILE_BYTES) {
      setFile(null)
      setImportError('The roster file is too large.')
      event.target.value = ''
      return
    }
    setFile(selectedFile)
  }

  async function handleImport(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (importing || !file || !course || !course.is_active) return

    setImporting(true)
    setImportError(null)
    setResult(null)
    setDownloaded(false)
    try {
      const nextResult = await importInstructorRoster(course, file)
      setResult(nextResult)
      setFile(null)
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
    } catch (requestError) {
      if (requestError instanceof InstructorCourseApiError) {
        if (requestError.code === 'unauthorized') {
          await refreshAuth()
          setImportError('Roster import is temporarily unavailable.')
          return
        }
        if (requestError.code === 'file_too_large') {
          setImportError('The roster file is too large.')
          return
        }
        if (requestError.code === 'invalid_input') {
          setImportError('Please select a valid roster CSV.')
          return
        }
        if (requestError.code === 'forbidden') {
          setImportError('You do not have permission to manage this course.')
          return
        }
        if (requestError.code === 'not_found') {
          setImportError('Course not found.')
          return
        }
        if (requestError.code === 'conflict') {
          setImportError('The roster could not be imported in its current state.')
          return
        }
      }
      setImportError('Roster import is temporarily unavailable.')
    } finally {
      setImporting(false)
    }
  }

  function downloadRosterResult() {
    if (!result) return

    const url = URL.createObjectURL(result.csv)
    activeObjectUrls.current.add(url)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = ROSTER_FILENAME
    anchor.click()
    setDownloaded(true)
    window.setTimeout(() => {
      URL.revokeObjectURL(url)
      activeObjectUrls.current.delete(url)
    }, 0)
  }

  const issueCount = result
    ? (
      result.summary.invalid
      + result.summary.conflicts
      + result.summary.duplicate_input
    )
    : 0
  const visibleCourse = course?.id === courseId ? course : null

  return (
    <main className="mx-auto w-full max-w-6xl px-6 py-10 sm:px-10">
      <InstructorBreadcrumbs
        items={[
          {
            label: '← My Courses',
            to: '/instructor/courses',
            disabled: importing,
            back: true,
          },
          ...(visibleCourse
            ? [
              {
                label: courseBreadcrumbLabel(
                  visibleCourse.course_identifier,
                  '',
                ),
                to: `/instructor/courses/${visibleCourse.id}`,
                disabled: importing,
              },
            ]
            : []),
          { label: 'Import Roster', current: true },
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

      {!courseLoading && !visibleCourse && courseError && (
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

      {!courseLoading && !courseError && visibleCourse && (
        <>
          <header className="mt-6">
            <p className="font-mono text-xs uppercase tracking-wider text-hud-accent">
              Course ID: {visibleCourse.course_identifier}
            </p>
            <h1 className="mt-2 text-3xl font-bold tracking-tight">
              Import Roster
            </h1>
            <p className="mt-2 text-sm text-ink-dim">
              {visibleCourse.course_name}
            </p>
          </header>

          <CourseSectionNavigation
            activeSection="roster"
            onSectionChange={(section) => {
              if (section !== 'roster') {
                navigate(`/instructor/courses/${encodeURIComponent(courseId)}`)
              }
            }}
            navigationDisabled={importing}
          />

          {!visibleCourse.is_active && (
            <p
              className="mt-6 rounded-md border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900"
              role="alert"
            >
              Inactive courses cannot accept roster imports.
            </p>
          )}

          <section className="mt-8 rounded-xl border border-line bg-white p-6 shadow-card sm:p-8">
            <h2 className="text-xl font-semibold">Roster CSV</h2>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-ink-dim">
              Upload one UTF-8 CSV containing exactly one column named{' '}
              <code className="rounded bg-well px-1.5 py-0.5 font-mono text-xs text-ink">
                berkeley_username
              </code>
              . The file may contain at most 1,000 non-empty rows and must not
              exceed 1 MB.
            </p>
            <div className="mt-5 rounded-md border border-line bg-well p-4">
              <p className="font-mono text-xs text-ink-dim">
                berkeley_username
                <br />
                student-example
              </p>
            </div>

            <form
              className="mt-6"
              onSubmit={(event) => void handleImport(event)}
            >
              <label htmlFor="roster-file" className="block text-sm font-medium">
                Choose roster CSV
              </label>
              <input
                ref={fileInputRef}
                id="roster-file"
                name="file"
                type="file"
                accept=".csv,text/csv"
                onChange={handleFileChange}
                disabled={
                  importing
                  || !visibleCourse.is_active
                  || hasUndownloadedCodes
                }
                className="mt-2 block w-full rounded-md border border-line-strong bg-white text-sm text-ink file:mr-4 file:border-0 file:bg-well file:px-4 file:py-2.5 file:text-sm file:font-semibold file:text-ink hover:file:bg-line focus:outline-none focus-visible:ring-2 focus-visible:ring-hud-accent/30 disabled:opacity-60"
              />
              {hasUndownloadedCodes && (
                <p className="mt-2 text-sm font-medium text-amber-800">
                  Download the current activation codes before selecting another
                  roster.
                </p>
              )}
              {file && (
                <p className="mt-2 text-xs text-ink-dim">
                  Selected: {file.name}
                </p>
              )}

              {importError && (
                <p
                  className="mt-5 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800"
                  role="alert"
                >
                  {importError}
                </p>
              )}

              <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
                {importing ? (
                  <span
                    className="cursor-not-allowed rounded-md border border-line-strong px-4 py-2.5 text-center text-sm font-semibold text-ink opacity-60"
                    aria-disabled="true"
                  >
                    Cancel
                  </span>
                ) : (
                  <Link
                    to={`/instructor/courses/${visibleCourse.id}`}
                    className="rounded-md border border-line-strong px-4 py-2.5 text-center text-sm font-semibold text-ink hover:bg-well"
                  >
                    Cancel
                  </Link>
                )}
                <button
                  type="submit"
                  disabled={importing || !file || !visibleCourse.is_active}
                  className="rounded-md bg-hud-accent px-4 py-2.5 text-sm font-semibold text-white hover:bg-hud-accent-hover focus:outline-none focus-visible:ring-2 focus-visible:ring-hud-accent/40 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {importing ? 'Importing…' : 'Import Roster'}
                </button>
              </div>
            </form>
          </section>

          {result && (
            <section
              className="mt-6 rounded-xl border border-emerald-200 bg-emerald-50 p-6 sm:p-8"
              aria-live="polite"
            >
              <h2 className="text-xl font-semibold text-emerald-950">
                {issueCount > 0
                  ? 'Roster imported with row-level results'
                  : 'Roster imported successfully'}
              </h2>
              <p className="mt-2 text-sm leading-6 text-emerald-900">
                The server processed {result.summary.processed} roster rows.
                Download the result now; activation codes are provided only for
                newly created enrollments.
              </p>
              <p className="mt-2 text-sm font-semibold text-emerald-950">
                Send students their Berkeley Username, Course ID, and Activation Code together.
                Students need all three items to identify and activate the correct course-specific account.
              </p>

              <dl className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-3">
                {[
                  ['Created', result.summary.created],
                  ['Already enrolled', result.summary.already_enrolled],
                  ['Duplicate input', result.summary.duplicate_input],
                  ['Invalid', result.summary.invalid],
                  ['Account conflicts', result.summary.conflicts],
                  ['Activation codes', result.summary.created],
                ].map(([label, value]) => (
                  <div key={label} className="rounded-md bg-white/70 p-3">
                    <dt className="text-xs text-emerald-800">{label}</dt>
                    <dd className="mt-1 text-lg font-bold text-emerald-950">{value}</dd>
                  </div>
                ))}
              </dl>

              <div className="mt-6 rounded-md border border-amber-300 bg-amber-50 p-4 text-sm leading-6 text-amber-950">
                Codes will not be shown again after refresh or navigation.
                Store the downloaded file securely and distribute each code only
                to its intended student.
              </div>

              <button
                type="button"
                onClick={downloadRosterResult}
                className="mt-5 w-full rounded-md bg-hud-accent px-4 py-2.5 text-sm font-semibold text-white hover:bg-hud-accent-hover focus:outline-none focus-visible:ring-2 focus-visible:ring-hud-accent/40 focus-visible:ring-offset-2 sm:w-auto"
              >
                Download Activation Codes CSV
              </button>
              {downloaded && (
                <p className="mt-3 text-sm font-medium text-emerald-900" role="status">
                  Download started. Keep the file secure.
                </p>
              )}
            </section>
          )}
        </>
      )}
    </main>
  )
}
