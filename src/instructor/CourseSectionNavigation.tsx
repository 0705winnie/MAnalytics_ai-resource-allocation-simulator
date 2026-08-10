export type CourseSection = 'roster' | 'progress'

interface CourseSectionNavigationProps {
  activeSection: CourseSection
  onSectionChange: (section: CourseSection) => void
  navigationDisabled?: boolean
}

const baseClass = [
  'rounded-md px-3 py-2 text-sm font-semibold',
  'focus:outline-none focus-visible:ring-2 focus-visible:ring-hud-accent/30',
].join(' ')

export default function CourseSectionNavigation({
  activeSection,
  onSectionChange,
  navigationDisabled = false,
}: CourseSectionNavigationProps) {
  const sections: { id: CourseSection; label: string }[] = [
    { id: 'roster', label: 'Roster Management' },
    { id: 'progress', label: 'Student Progress' },
  ]

  return (
    <nav
      className="mt-6 rounded-xl border border-line bg-white p-3 shadow-card"
      aria-label="Course sections"
    >
      <div className="flex flex-wrap items-center gap-2">
        {sections.map(({ id, label }) => {
          const isActive = id === activeSection
          return (
            <button
              key={id}
              type="button"
              onClick={() => onSectionChange(id)}
              disabled={navigationDisabled}
              className={[
                baseClass,
                isActive ? 'bg-hud-accent text-white' : 'bg-well text-ink-faint hover:text-ink',
                navigationDisabled ? 'cursor-not-allowed opacity-70' : '',
              ].join(' ')}
              aria-current={isActive ? 'page' : undefined}
            >
              {label}
            </button>
          )
        })}
      </div>
    </nav>
  )
}
