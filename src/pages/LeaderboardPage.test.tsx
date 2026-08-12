import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { officialMonth, officialSession } from '../test/fixtures'
import LeaderboardPage from './LeaderboardPage'

const getSameStageLeaderboard = vi.fn()
const getFinalLeaderboard = vi.fn()

vi.mock('../lib/api', () => ({
  getSameStageLeaderboard: (...args: unknown[]) => getSameStageLeaderboard(...args),
  getFinalLeaderboard: (...args: unknown[]) => getFinalLeaderboard(...args),
}))

describe('persisted Simulation History and real leaderboards', () => {
  beforeEach(() => {
    getSameStageLeaderboard.mockReset()
    getFinalLeaderboard.mockReset()
  })
  it('shows ordered official monthly results in unified expandable month items', async () => {
    const monthOne = officialMonth(1, { policy_hash: 'same', warnings: ['warning one'] })
    const monthTwo = officialMonth(2, { policy_hash: 'same' })
    const session = officialSession(2, { monthly_results: [monthTwo, monthOne] })
    render(<LeaderboardPage nickname="Course Nickname" session={session} />)

    expect(screen.getByText('Course Nickname')).toBeTruthy()
    expect(screen.getByRole('heading', { name: 'History & Leaderboards' })).toBeTruthy()
    const monthHeadings = screen.getAllByRole('heading', { level: 3 })
    expect(monthHeadings.map((heading) => heading.textContent)).toEqual(['Month 1', 'Month 2'])

    const monthOneDetails = monthHeadings[0].closest('details') as HTMLDetailsElement
    const monthTwoDetails = monthHeadings[1].closest('details') as HTMLDetailsElement
    expect(within(monthOneDetails).getByText('$1,000')).toBeTruthy()
    expect(within(monthTwoDetails).getByText('Unchanged')).toBeTruthy()
    expect(monthOneDetails.open).toBe(false)

    await userEvent.click(within(monthOneDetails).getByText('Show details'))
    expect(monthOneDetails.open).toBe(true)
    expect(within(monthOneDetails).getByText('VIP:')).toBeTruthy()
    expect(within(monthOneDetails).getByText('Average')).toBeTruthy()
    expect(within(monthOneDetails).getByText('Peak')).toBeTruthy()
    expect(within(monthOneDetails).getByText('warning one')).toBeTruthy()
  })

  it('marks a changed policy by comparing adjacent persisted hashes', () => {
    const session = officialSession(2, {
      monthly_results: [
        officialMonth(1, { policy_hash: 'first' }),
        officialMonth(2, { policy_hash: 'second' }),
      ],
    })
    render(<LeaderboardPage nickname="Student" session={session} />)

    expect(screen.getByText('Initial policy')).toBeTruthy()
    expect(screen.getByText('Changed')).toBeTruthy()
  })

  it('keeps full policy source collapsed behind View Policy Used', async () => {
    const session = officialSession(1)
    render(<LeaderboardPage nickname="Student" session={session} />)
    await userEvent.click(screen.getByText('Show details'))
    const policyDetails = screen.getByText('View Policy Used').closest('details') as HTMLDetailsElement

    expect(policyDetails.open).toBe(false)
    await userEvent.click(screen.getByText('View Policy Used'))
    expect(policyDetails.open).toBe(true)
    const codeBlocks = policyDetails.querySelectorAll('pre')
    expect(codeBlocks[0].textContent).toBe(session.monthly_results[0].policy_code)
    expect(codeBlocks[1].textContent).toContain('"threshold": 1')
  })

  it('shows the honest month-zero state without fake identities', async () => {
    getSameStageLeaderboard.mockResolvedValue({
      stage: 0,
      current_user_eligible: false,
      items: [],
    })
    render(<LeaderboardPage nickname="Real Nickname" session={officialSession(0)} />)

    expect(screen.queryByText(/Sharp Cluster/)).toBeNull()
    expect(screen.queryByText(/Bright Comet/)).toBeNull()
    await userEvent.click(screen.getByRole('tab', { name: 'Same-Month Leaderboard' }))
    expect(await screen.findByText(/Complete Month 1 to join/)).toBeTruthy()
  })

  it('uses same-month terminology and the selected month revenue header', async () => {
    getSameStageLeaderboard.mockResolvedValue({
      stage: 2,
      current_user_eligible: true,
      items: [{
        rank: 1,
        nickname: 'Real Nickname',
        completed_months: 2,
        cumulative_revenue: 2500,
        last_activity: '2026-08-10T12:00:00Z',
        is_current_user: true,
      }],
    })
    render(<LeaderboardPage nickname="Real Nickname" session={officialSession(2)} />)

    const viewTabs = screen.getAllByRole('tab')
    expect(viewTabs[0].textContent).toBe('Simulation History')
    expect(viewTabs[1].textContent).toBe('Same-Month Leaderboard')
    expect(viewTabs[2].textContent).toBe('Final Leaderboard')
    await userEvent.click(screen.getByRole('tab', { name: 'Same-Month Leaderboard' }))

    expect(await screen.findByText('Same-Month Leaderboard')).toBeTruthy()
    expect(screen.getByText('Revenue through Month 2')).toBeTruthy()
  })

  it('shows official nickname-only final rankings and current-user eligibility', async () => {
    getFinalLeaderboard.mockResolvedValue({
      stage: 12,
      current_user_eligible: false,
      items: [{
        rank: 1,
        nickname: 'Real Nickname',
        completed_months: 12,
        cumulative_revenue: 125000,
        last_activity: '2026-08-10T12:00:00Z',
        is_current_user: false,
      }],
    })
    render(<LeaderboardPage nickname="Incomplete Student" session={officialSession(2)} />)

    await userEvent.click(screen.getByRole('tab', { name: 'Final Leaderboard' }))
    expect(await screen.findByText('Real Nickname')).toBeTruthy()
    expect(screen.getByText(/join it only after completing all 12 months/)).toBeTruthy()
    expect(screen.getByText('Total Revenue (12 Months)')).toBeTruthy()
    expect(screen.queryByText(/berkeley/i)).toBeNull()
  })
})
