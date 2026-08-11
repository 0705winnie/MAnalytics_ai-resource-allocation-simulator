import { Link } from 'react-router-dom'

export interface InstructorBreadcrumbItem {
  label: string
  to?: string
  current?: boolean
  disabled?: boolean
  back?: boolean
}

interface InstructorBreadcrumbsProps {
  items: InstructorBreadcrumbItem[]
}

export function courseBreadcrumbLabel(
  courseCode: string,
  semester: string,
): string {
  return semester ? `${courseCode} · ${semester}` : courseCode
}

export default function InstructorBreadcrumbs({
  items,
}: InstructorBreadcrumbsProps) {
  return (
    <nav aria-label="Breadcrumb">
      <ol className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1 text-sm">
        {items.map((item, index) => (
          <li
            key={`${item.label}-${index}`}
            className="flex min-w-0 items-center gap-x-2"
          >
            {index > 0 && (
              <span className="text-ink-faint" aria-hidden="true">
                ›
              </span>
            )}
            {item.to && !item.disabled && !item.current ? (
              <Link
                to={item.to}
                className={[
                  'min-w-0 break-words font-semibold text-hud-accent',
                  'hover:text-hud-accent-hover focus:outline-none',
                  'focus-visible:ring-2 focus-visible:ring-hud-accent/30',
                  item.back
                    ? 'rounded-md border border-line-strong px-3 py-2 hover:bg-white'
                    : 'focus-visible:rounded-sm',
                ].join(' ')}
              >
                {item.label}
              </Link>
            ) : (
              <span
                className={[
                  'min-w-0 break-words font-medium',
                  item.disabled ? 'text-ink-faint' : 'text-ink-dim',
                  item.back
                    ? 'rounded-md border border-line px-3 py-2'
                    : '',
                ].join(' ')}
                aria-current={item.current ? 'page' : undefined}
                aria-disabled={item.disabled ? 'true' : undefined}
              >
                {item.label}
              </span>
            )}
          </li>
        ))}
      </ol>
    </nav>
  )
}
