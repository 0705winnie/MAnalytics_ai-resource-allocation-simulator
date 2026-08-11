import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import InstructorLeaderboards from './InstructorLeaderboards'
import type { InstructorCourse } from './types'

const getSameMonth = vi.fn()
const getFinal = vi.fn()

vi.mock('../auth/AuthProvider', () => ({
  useAuth: () => ({ refreshAuth: vi.fn() }),
}))

vi.mock('./api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./api')>()
  return {
    ...actual,
    getInstructorSameStageLeaderboard: (...args: unknown[]) => getSameMonth(...args),
    getInstructorFinalLeaderboard: (...args: unknown[]) => getFinal(...args),
  }
})

const course: InstructorCourse = {
  id: 'course-id',
  course_code: 'COURSE',
  course_identifier: 'COURSE-2026FALL',
  course_name: 'Course',
  semester: 'Fall 2026',
  is_active: true,
  created_at: '2026-08-01T00:00:00Z',
  updated_at: '2026-08-01T00:00:00Z',
}

const entry = {
  rank: 1,
  nickname: 'Student',
  completed_months: 12,
  cumulative_revenue: 12000,
  last_activity: '2026-08-11T00:00:00Z',
  is_current_user: false,
}

describe('InstructorLeaderboards month terminology', () => {
  beforeEach(() => {
    getSameMonth.mockReset()
    getFinal.mockReset()
    getSameMonth.mockResolvedValue({ stage: 1, current_user_eligible: null, items: [entry] })
    getFinal.mockResolvedValue({ stage: 12, current_user_eligible: null, items: [entry] })
  })

  it('shows Final first and selected by default', async () => {
    render(<InstructorLeaderboards course={course} />)

    const tabs = screen.getAllByRole('button')
    expect(tabs[0].textContent).toBe('Final')
    expect(tabs[1].textContent).toBe('Same-Month')
    await waitFor(() => expect(getFinal).toHaveBeenCalledTimes(1))
    expect(screen.getByText('Total Revenue (12 Months)')).toBeTruthy()
    expect(screen.queryByRole('combobox', { name: 'Month' })).toBeNull()
  })

  it('keeps Month selector values and month revenue header on Same-Month', async () => {
    render(<InstructorLeaderboards course={course} />)

    await userEvent.click(screen.getByRole('button', { name: 'Same-Month' }))

    expect(screen.getByRole('combobox', { name: 'Month' })).toBeTruthy()
    expect(screen.getByRole('option', { name: 'Month 1' })).toBeTruthy()
    expect(screen.getByRole('option', { name: 'Month 12' })).toBeTruthy()
    expect(await screen.findByText('Revenue through Month 1')).toBeTruthy()
  })
})
