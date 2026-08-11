import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from './App'
import { officialSession } from './test/fixtures'

const getSession = vi.hoisted(() => vi.fn())

vi.mock('./lib/api', async (importOriginal) => ({
  ...await importOriginal<typeof import('./lib/api')>(),
  getOfficialSimulationSession: getSession,
}))

vi.mock('./auth/AuthProvider', () => ({
  useAuth: () => ({ nickname: 'Official Nickname' }),
}))

vi.mock('./components/NavBar', () => ({
  default: ({ onNavigate }: { onNavigate: (page: number) => void }) => (
    <nav>
      <button onClick={() => onNavigate(2)}>Policy page</button>
      <button onClick={() => onNavigate(3)}>Simulation page</button>
      <button onClick={() => onNavigate(4)}>History page</button>
    </nav>
  ),
}))

vi.mock('./pages/IntroDataPage', () => ({ default: () => <div>intro-page</div> }))
vi.mock('./pages/PolicyAIPage', () => ({
  POLICY_TEMPLATE: 'DEFAULT POLICY',
  default: ({ policyCode, session }: { policyCode: string; session: ReturnType<typeof officialSession> }) => (
    <div>policy-page:{policyCode}:month-{session.completed_months}</div>
  ),
}))
vi.mock('./pages/SimulationPage', () => ({
  default: ({ session }: { session: ReturnType<typeof officialSession> }) => (
    <div>
      simulation-page:completed-{session.completed_months}:next-{session.next_month ?? 'none'}
      {session.next_month !== null && <button>Run Month {session.next_month}</button>}
    </div>
  ),
}))
vi.mock('./pages/LeaderboardPage', () => ({
  default: ({ nickname, session }: { nickname: string; session: ReturnType<typeof officialSession> }) => (
    <div>history-page:{nickname}:months-{session.completed_months}</div>
  ),
}))

beforeEach(() => {
  getSession.mockReset()
  localStorage.clear()
})

async function openSimulation() {
  await screen.findByText('intro-page')
  await userEvent.click(screen.getByRole('button', { name: 'Simulation page' }))
}

describe('official session restoration in App', () => {
  it('blocks the student pages while initial restoration is pending', () => {
    getSession.mockReturnValue(new Promise(() => undefined))
    render(<App />)

    expect(screen.getByText('Restoring your official simulation…')).toBeTruthy()
    expect(screen.queryByText(/Run Month/)).toBeNull()
  })

  it.each([
    [0, 'simulation-page:completed-0:next-1', 'Run Month 1'],
    [5, 'simulation-page:completed-5:next-6', 'Run Month 6'],
  ])('uses a restored %i-month session as progress authority', async (count, summary, runLabel) => {
    getSession.mockResolvedValue(officialSession(count))
    render(<App />)
    await openSimulation()

    expect(screen.getByText(summary)).toBeTruthy()
    expect(screen.getByRole('button', { name: runLabel })).toBeTruthy()
  })

  it('shows completed state without a Month 13 Run action', async () => {
    getSession.mockResolvedValue(officialSession(12))
    render(<App />)
    await openSimulation()

    expect(screen.getByText('simulation-page:completed-12:next-none')).toBeTruthy()
    expect(screen.queryByText(/Run Month 13/)).toBeNull()
  })

  it('shows an error without a fake Month 1 fallback and retries restoration', async () => {
    getSession
      .mockRejectedValueOnce(new Error('Database restoration unavailable'))
      .mockResolvedValueOnce(officialSession(4))
    render(<App />)

    expect(await screen.findByText('Official simulation could not be restored.')).toBeTruthy()
    expect(screen.queryByText(/Run Month 1/)).toBeNull()
    await userEvent.click(screen.getByRole('button', { name: 'Retry restoration' }))
    await openSimulation()
    expect(screen.getByText('simulation-page:completed-4:next-5')).toBeTruthy()
  })

  it('initializes the editor baseline from the last executed policy', async () => {
    const restored = officialSession(2)
    getSession.mockResolvedValue(restored)
    render(<App />)
    await screen.findByText('intro-page')
    await userEvent.click(screen.getByRole('button', { name: 'Policy page' }))

    expect(screen.getAllByText((_, element) => (
      element?.textContent === `policy-page:${restored.latest_policy!.policy_code}:month-2`
    )).length).toBeGreaterThan(0)
  })

  it('ignores submissionHistory and other localStorage progress', async () => {
    localStorage.setItem('submissionHistory', JSON.stringify([{ monthly: Array(12).fill({}) }]))
    localStorage.setItem('completedMonths', '12')
    getSession.mockResolvedValue(officialSession(3))
    render(<App />)
    await openSimulation()

    expect(screen.getByText('simulation-page:completed-3:next-4')).toBeTruthy()
  })

  it('restores from the server again after the student app unmounts and remounts', async () => {
    getSession
      .mockResolvedValueOnce(officialSession(7))
      .mockResolvedValueOnce(officialSession(1))
    const first = render(<App />)
    await openSimulation()
    expect(screen.getByText('simulation-page:completed-7:next-8')).toBeTruthy()

    first.unmount()
    render(<App />)
    await openSimulation()
    expect(screen.getByText('simulation-page:completed-1:next-2')).toBeTruthy()
    expect(getSession).toHaveBeenCalledTimes(2)
  })
})
