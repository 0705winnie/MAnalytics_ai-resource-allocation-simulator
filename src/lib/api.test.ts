import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  getOfficialSimulationSession,
  OfficialSimulationApiError,
  postRunNextMonth,
} from './api'
import { officialSession } from '../test/fixtures'

afterEach(() => vi.unstubAllGlobals())

describe('official simulation API client', () => {
  it('restores with the authenticated GET endpoint', async () => {
    const session = officialSession(2)
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(session), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    await expect(getOfficialSimulationSession()).resolves.toEqual(session)
    expect(fetchMock).toHaveBeenCalledWith('/api/simulation/session', {
      credentials: 'include',
      method: 'GET',
      signal: undefined,
    })
  })

  it('sends only the official run-next request contract', async () => {
    const request = {
      expected_month: 3,
      idempotency_key: '11111111-1111-4111-8111-111111111111',
      policy_code: 'def admission_policy(): pass',
      params: { guard: 4 },
    }
    const response = { replayed: false, executed_month: 3, session: officialSession(3) }
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(response), { status: 201 }))
    vi.stubGlobal('fetch', fetchMock)

    await expect(postRunNextMonth(request)).resolves.toEqual(response)
    const init = fetchMock.mock.calls[0][1] as RequestInit
    expect(fetchMock.mock.calls[0][0]).toBe('/api/simulation/session/months/next')
    expect(JSON.parse(init.body as string)).toEqual(request)
    expect(init.credentials).toBe('include')
    expect(init.body).not.toContain('previous_months')
    expect(init.body).not.toContain('session_id')
    expect(init.body).not.toContain('enrollment_id')
    expect(init.body).not.toContain('course_id')
    expect(init.body).not.toContain('"month"')
  })

  it('preserves safe structured status and code without exposing arbitrary details', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      detail: { code: 'wrong_expected_month', message: 'Refresh the official session', context: { actual: 4 } },
    }), { status: 409 })))

    const error = await postRunNextMonth({
      expected_month: 3,
      idempotency_key: '11111111-1111-4111-8111-111111111111',
      policy_code: 'policy',
      params: {},
    }).catch((caught) => caught)

    expect(error).toBeInstanceOf(OfficialSimulationApiError)
    expect(error.status).toBe(409)
    expect(error.code).toBe('wrong_expected_month')
    expect(error.message).toBe('Refresh the official session')
    expect(error).not.toHaveProperty('context')
  })
})
