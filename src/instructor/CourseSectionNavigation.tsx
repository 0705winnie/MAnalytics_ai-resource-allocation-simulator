import { Link } from 'react-router-dom'

type CourseSection = 'overview' | 'roster'

interface CourseSectionNavigationProps {
  courseId: string
  currentSection: CourseSection
  navigationDisabled?: boolean
}

const baseClass = [
  'rounded-md px-3 py-2 text-sm font-semibold',
  'focus:outline-none focus-visible:ring-2 focus-visible:ring-hud-accent/30',
].join(' ')

export default function CourseSectionNavigation({
  courseId,
  currentSection,
  navigationDisabled = false,
}: CourseSectionNavigationProps) {
  const sections = [
    {
      label: 'Overview',
      to: `/instructor/courses/${courseId}`,
      current: currentSection === 'overview',
    },
    {
      label: 'Roster',
      to: `/instructor/courses/${courseId}/roster`,
      current: currentSection === 'roster',
    },
  ]

  return (
    <nav
      className="mt-6 rounded-xl border border-line bg-white p-3 shadow-card"
      aria-label="Course sections"
    >
      <div className="flex flex-wrap items-center gap-2">
        {sections.map((section) => (
          section.current ? (
            <span
              key={section.label}
              className={`${baseClass} bg-hud-accent text-white`}
              aria-current="page"
            >
              {section.label}
            </span>
          ) : navigationDisabled ? (
            <span
              key={section.label}
              className={`${baseClass} cursor-not-allowed bg-well text-ink-faint`}
              aria-disabled="true"
            >
              {section.label}
            </span>
          ) : (
            <Link
              key={section.label}
              to={section.to}
              className={`${baseClass} text-ink-dim hover:bg-well hover:text-ink`}
            >
              {section.label}
            </Link>
          )
        ))}
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
