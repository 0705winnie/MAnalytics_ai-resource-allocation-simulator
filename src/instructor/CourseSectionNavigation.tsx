interface CourseSectionNavigationProps {
  navigationDisabled?: boolean
}

const baseClass = [
  'rounded-md px-3 py-2 text-sm font-semibold',
  'focus:outline-none focus-visible:ring-2 focus-visible:ring-hud-accent/30',
].join(' ')

export default function CourseSectionNavigation({
  navigationDisabled = false,
}: CourseSectionNavigationProps) {
  return (
    <nav
      className="mt-6 rounded-xl border border-line bg-white p-3 shadow-card"
      aria-label="Course sections"
    >
      <div className="flex flex-wrap items-center gap-2">
        <span
          className={[
            baseClass,
            'bg-hud-accent text-white',
            navigationDisabled ? 'cursor-not-allowed opacity-70' : '',
          ].join(' ')}
          aria-current="page"
          aria-disabled={navigationDisabled ? 'true' : undefined}
        >
          Roster Management
        </span>
        <span
          className={`${baseClass} cursor-not-allowed bg-well text-ink-faint`}
          aria-disabled="true"
        >
          Student Progress
          <span className="ml-2 font-mono text-[0.65rem] uppercase tracking-wider">
            Coming later
          </span>
        </span>
      </div>
    </nav>
  )
}
