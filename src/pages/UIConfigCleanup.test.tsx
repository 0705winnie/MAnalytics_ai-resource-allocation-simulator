import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { TABS } from '../components/NavBar'
import { SYSTEM_PARAMS } from './IntroDataPage'
import InstructorLoginPage from './InstructorLoginPage'
import StudentLoginPage from './StudentLoginPage'

vi.mock('../auth/AuthProvider', () => ({
  AUTH_SERVICE_UNAVAILABLE_MESSAGE: 'Authentication is temporarily unavailable.',
  useAuth: () => ({
    status: 'unauthenticated',
    error: null,
    loginStudent: vi.fn(),
    loginInstructor: vi.fn(),
    refreshAuth: vi.fn(),
  }),
}))

describe('approved UI/config cleanup', () => {
  it('groups environment parameters before all three price cards', () => {
    expect(SYSTEM_PARAMS.map(({ label }) => label)).toEqual([
      'Server Clusters',
      'Cluster Capacity',
      'Simulation Horizon',
      'VIP Price',
      'Standard Price',
      'Economy Price',
    ])
  })

  it('renames the fourth student navigation page', () => {
    expect(TABS.find(({ page }) => page === 4)?.label).toBe('04  History & Leaderboards')
    expect(TABS.some(({ label }) => label === '04  History')).toBe(false)
  })

  it('makes the student role and instructor switch destination explicit', async () => {
    render(
      <MemoryRouter initialEntries={['/login']}>
        <Routes>
          <Route path="/login" element={<StudentLoginPage />} />
          <Route path="/instructor/login" element={<p>Instructor destination</p>} />
        </Routes>
      </MemoryRouter>,
    )

    expect(screen.getByRole('heading', { name: 'Student Login' })).toBeTruthy()
    expect(screen.getByText('Student Account')).toBeTruthy()
    await userEvent.click(screen.getByRole('button', {
      name: 'Are you an instructor? Go to Instructor Login',
    }))
    expect(screen.getByText('Instructor destination')).toBeTruthy()
  })

  it('makes the instructor role and student switch destination explicit', async () => {
    render(
      <MemoryRouter initialEntries={['/instructor/login']}>
        <Routes>
          <Route path="/instructor/login" element={<InstructorLoginPage />} />
          <Route path="/login" element={<p>Student destination</p>} />
        </Routes>
      </MemoryRouter>,
    )

    expect(screen.getByRole('heading', { name: 'Instructor Login' })).toBeTruthy()
    expect(screen.getByText('Instructor Account')).toBeTruthy()
    await userEvent.click(screen.getByRole('button', {
      name: 'Are you a student? Go to Student Login',
    }))
    expect(screen.getByText('Student destination')).toBeTruthy()
  })
})
