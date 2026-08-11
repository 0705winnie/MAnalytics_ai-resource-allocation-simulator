import { useState } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { OfficialSimulationSession } from '../types/simulation'
import { officialSession } from '../test/fixtures'
import SimulationPage from './SimulationPage'

const fetchMock = vi.fn()

vi.mock('recharts', () => {
  const Box = ({ children }: { children?: React.ReactNode }) => <div>{children}</div>
  return {
    BarChart: Box,
    Bar: Box,
    XAxis: Box,
    YAxis: Box,
    CartesianGrid: Box,
    Tooltip: Box,
    Legend: Box,
    ResponsiveContainer: Box,
    Cell: Box,
  }
})

beforeEach(() => {
  fetchMock.mockReset()
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => vi.unstubAllGlobals())

function jsonResponse(body: unknown, status: number): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function Harness({
  initial = officialSession(0),
  restore = vi.fn().mockResolvedValue(initial),
}: {
  initial?: OfficialSimulationSession
  restore?: () => Promise<OfficialSimulationSession>
}) {
  const [session, setSession] = useState(initial)
  return (
    <SimulationPage
      policyCode={'def admission_policy(request, state, history, params):\n    return 1'}
      policyParams={{ guard: 2 }}
      session={session}
      onSessionChange={setSession}
      onRestoreSession={restore}
      onNavigate={() => undefined}
    />
  )
}

describe('official Run Month UI', () => {
  it('uses the official endpoint and replaces the complete session on success', async () => {
    fetchMock.mockResolvedValue(jsonResponse({
      replayed: false,
      executed_month: 1,
      session: officialSession(1),
    }, 201))
    render(<Harness />)

    fireEvent.click(screen.getByRole('button', { name: /Run Month 1/ }))

    await screen.findByText('Month 1 completed and was saved to official history.')
    expect(fetchMock).toHaveBeenCalledTimes(1)
    const request = JSON.parse((fetchMock.mock.calls[0][1] as RequestInit).body as string)
    expect(request).toMatchObject({
      expected_month: 1,
      policy_code: 'def admission_policy(request, state, history, params):\n    return 1',
      params: { guard: 2 },
    })
    expect(Object.keys(request).sort()).toEqual([
      'expected_month',
      'idempotency_key',
      'params',
      'policy_code',
    ])
    expect(screen.getByRole('button', { name: /Run Month 2/ })).toBeTruthy()
  })

  it('accepts an idempotent replay as authoritative session state', async () => {
    fetchMock.mockResolvedValue(jsonResponse({
      replayed: true,
      executed_month: 1,
      session: officialSession(1),
    }, 200))
    render(<Harness />)

    fireEvent.click(screen.getByRole('button', { name: /Run Month 1/ }))

    expect(await screen.findByText(/Month 1 was already saved/)).toBeTruthy()
    expect(screen.getByRole('button', { name: /Run Month 2/ })).toBeTruthy()
  })

  it('disables duplicate clicks while one request is pending', async () => {
    let resolve!: (value: unknown) => void
    fetchMock.mockReturnValue(new Promise((done) => { resolve = done }))
    render(<Harness />)
    const button = screen.getByRole('button', { name: /Run Month 1/ }) as HTMLButtonElement

    fireEvent.click(button)
    fireEvent.click(button)
    expect(button.disabled).toBe(true)
    expect(fetchMock).toHaveBeenCalledTimes(1)

    resolve(jsonResponse({ replayed: false, executed_month: 1, session: officialSession(1) }, 201))
    await screen.findByText(/Month 1 completed/)
  })

  it('does not advance the displayed month after a definite policy failure', async () => {
    fetchMock.mockResolvedValue(jsonResponse({
      detail: { status: 400, message: 'Policy cannot compile', code: 'invalid_policy' },
    }, 400))
    render(<Harness />)

    fireEvent.click(screen.getByRole('button', { name: /Run Month 1/ }))

    expect(await screen.findByText(/Policy cannot compile/)).toBeTruthy()
    expect(screen.getByRole('button', { name: /Run Month 1/ })).toBeTruthy()
    expect(screen.queryByRole('button', { name: /Run Month 2/ })).toBeNull()
  })

  it('reconciles wrong expected month with GET state and never auto-runs the next month', async () => {
    const restore = vi.fn().mockResolvedValue(officialSession(1))
    fetchMock.mockResolvedValue(jsonResponse({
      detail: { message: 'Expected month is stale', code: 'wrong_expected_month' },
    }, 409))
    render(<Harness restore={restore} />)

    fireEvent.click(screen.getByRole('button', { name: /Run Month 1/ }))

    expect(await screen.findByText(/Official state has been refreshed/)).toBeTruthy()
    expect(restore).toHaveBeenCalledTimes(1)
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(screen.getByRole('button', { name: /Run Month 2/ })).toBeTruthy()
  })

  it('shows completed state and offers no additional Run action', () => {
    render(<Harness initial={officialSession(12)} />)

    const completed = screen.getByRole('button', { name: 'All 12 Months Complete' }) as HTMLButtonElement
    expect(completed.disabled).toBe(true)
    expect(screen.queryByText(/Run Month 13/)).toBeNull()
  })

  it('does not reconcile or silently retry an idempotency-key conflict', async () => {
    const restore = vi.fn().mockResolvedValue(officialSession(0))
    fetchMock.mockResolvedValue(jsonResponse({
      detail: { message: 'Conflicting request', code: 'idempotency_key_conflict' },
    }, 409))
    render(<Harness restore={restore} />)

    fireEvent.click(screen.getByRole('button', { name: /Run Month 1/ }))

    expect(await screen.findByText(/run identifier was already used/)).toBeTruthy()
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(restore).not.toHaveBeenCalled()
  })

  it('reuses the same request identity when retrying an uncertain response', async () => {
    fetchMock
      .mockRejectedValueOnce(new Error('Connection lost'))
      .mockResolvedValueOnce(jsonResponse({
        replayed: true,
        executed_month: 1,
        session: officialSession(1),
      }, 200))
    render(<Harness />)

    await userEvent.click(screen.getByRole('button', { name: /Run Month 1/ }))
    await screen.findByText(/prior outcome is uncertain/i)
    await userEvent.click(screen.getByRole('button', { name: 'Retry Month 1' }))

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
    const first = (fetchMock.mock.calls[0][1] as RequestInit).body
    const second = (fetchMock.mock.calls[1][1] as RequestInit).body
    expect(second).toEqual(first)
  })

  it('contains neither manual save nor legacy Submit Result controls', () => {
    render(<Harness initial={officialSession(2)} />)

    expect(screen.queryByText('Save to My History')).toBeNull()
    expect(screen.queryByText('Submit Result')).toBeNull()
    expect(screen.getByText(/saved automatically/)).toBeTruthy()
  })
})
