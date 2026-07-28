import { Link } from 'react-router-dom'

const UPCOMING_TOOLS = [
  ['Roster management', 'Coming next'],
  ['Student progress', 'Coming later'],
] as const

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
            {UPCOMING_TOOLS.map(([title, status]) => (
              <article key={title} className="rounded-xl border border-line bg-well p-5">
                <h3 className="font-semibold">{title}</h3>
                <p className="mt-2 font-mono text-xs uppercase tracking-wider text-ink-faint">
                  {status}
                </p>
              </article>
            ))}
          </div>
        </section>
      </div>
    </main>
  )
}
