export type Page = 1 | 2 | 3 | 4

interface Props {
  currentPage: Page
  onNavigate: (page: Page) => void
}

const TABS: { page: Page; label: string }[] = [
  { page: 1, label: '01  Introduction' },
  { page: 2, label: '02  Policy & AI' },
  { page: 3, label: '03  Simulation' },
  { page: 4, label: '04  History' },
]

export default function NavBar({ currentPage, onNavigate }: Props) {
  return (
    <header className="border-b border-line bg-white shadow-card">
      <div className="max-w-6xl mx-auto px-6 flex items-center h-14">
        <span className="text-xs font-mono tracking-widest text-ink-faintest uppercase shrink-0 mr-10">
          Resource Allocation Simulator
        </span>
        <nav className="flex h-full">
          {TABS.map(({ page, label }) => (
            <button
              key={page}
              onClick={() => onNavigate(page)}
              className={[
                'px-5 h-full text-sm font-medium tracking-wide border-b-2 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-hud-accent/50 focus-visible:ring-inset',
                currentPage === page
                  ? 'border-hud-accent text-hud-accent'
                  : 'border-transparent text-ink-faint hover:text-ink-dim',
              ].join(' ')}
            >
              {label}
            </button>
          ))}
        </nav>
      </div>
    </header>
  )
}
