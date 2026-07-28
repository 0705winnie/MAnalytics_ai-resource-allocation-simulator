import { Link } from 'react-router-dom'

export default function InstructorLandingPage() {
  return (
    <main className="px-6 py-10 sm:px-10">
      <div className="mx-auto w-full max-w-5xl">
        <p className="font-mono text-xs uppercase tracking-[0.18em] text-hud-accent">
          Instructor workspace
        </p>
        <h1 className="mt-2 text-3xl font-bold tracking-tight">
          Instructor Dashboard
        </h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-ink-dim">
          Create course instances and open an existing course to prepare for
          roster management.
        </p>

        <section className="mt-8 rounded-2xl border border-line bg-white p-6 shadow-card sm:p-8">
          <div className="grid gap-4 sm:grid-cols-2">
            <Link
              to="/instructor/courses"
              className="rounded-xl border border-line bg-well p-5 transition-colors hover:border-hud-accent/40 hover:bg-white focus:outline-none focus-visible:ring-2 focus-visible:ring-hud-accent/30"
            >
              <h2 className="font-semibold">My Courses</h2>
              <p className="mt-2 text-sm leading-6 text-ink-dim">
                View and select course instances created by your account.
              </p>
            </Link>
            <Link
              to="/instructor/courses/new"
              className="rounded-xl border border-line bg-well p-5 transition-colors hover:border-hud-accent/40 hover:bg-white focus:outline-none focus-visible:ring-2 focus-visible:ring-hud-accent/30"
            >
              <h2 className="font-semibold">Create Course</h2>
              <p className="mt-2 text-sm leading-6 text-ink-dim">
                Add a new course code, display name, and semester.
              </p>
            </Link>
          </div>

          <div className="mt-8 grid gap-4 sm:grid-cols-2">
            <Link
              to="/instructor/courses"
              className="rounded-xl border border-line bg-well p-5 transition-colors hover:border-hud-accent/40 hover:bg-white focus:outline-none focus-visible:ring-2 focus-visible:ring-hud-accent/30"
            >
              <h3 className="font-semibold">Roster Management</h3>
              <p className="mt-2 text-sm leading-6 text-ink-dim">
                Choose a course to view students, import a roster, and manage
                activation status.
              </p>
              <p className="mt-3 font-mono text-xs uppercase tracking-wider text-hud-accent">
                Select a course
              </p>
            </Link>
            <article className="rounded-xl border border-line bg-well p-5">
              <h3 className="font-semibold">Student Progress</h3>
              <p className="mt-2 text-sm leading-6 text-ink-dim">
                Review student simulation progress and results when this tool
                becomes available.
              </p>
              <p className="mt-3 font-mono text-xs uppercase tracking-wider text-ink-faint">
                Coming later
              </p>
            </article>
          </div>
        </section>
      </div>
    </main>
  )
}
