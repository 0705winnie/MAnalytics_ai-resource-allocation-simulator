import type {
  LeaderboardResponse,
  OfficialSimulationSession,
  RunNextMonthRequest,
  RunNextMonthResponse,
  StructuredApiErrorDetail,
} from '../types/simulation'

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface AssistantRequest {
  message: string
  history: ChatMessage[]
  context?: {
    current_month?: number
    remaining_capacity?: Record<number, number>
    monthly_result?: Record<string, unknown>
  } | null
}

export interface AssistantResponse {
  content: string
  provider: 'azure' | 'mock'
}

// Thrown when the backend itself never actually handled the request — the
// fetch failed outright (server down, no network), or Vite's dev proxy
// answered on its behalf with a plain-text 502/503/504 (no JSON `detail`
// body, since FastAPI never saw the request). This is distinct from a
// normal Error, where the backend *did* respond with a structured
// `{detail: ...}` (bad policy code, validation, etc). The UI uses this to
// decide whether "is the backend running?" is actually relevant advice.
export class NetworkError extends Error {}

export class OfficialSimulationApiError extends Error {
  readonly status: number
  readonly code: string | null

  constructor(status: number, message: string, code: string | null = null) {
    super(message)
    this.name = 'OfficialSimulationApiError'
    this.status = status
    this.code = code
  }
}

async function postJSON<T>(url: string, body: unknown): Promise<T> {
  let res: Response
  try {
    res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
  } catch (err) {
    throw new NetworkError(err instanceof Error ? err.message : 'Network request failed')
  }
  if (!res.ok) {
    const parsed = await res.json().catch(() => null)
    const detail = (parsed as { detail?: string } | null)?.detail
    if (detail === undefined) {
      throw new NetworkError(`The backend did not respond as expected (HTTP ${res.status}).`)
    }
    throw new Error(detail)
  }
  return res.json() as Promise<T>
}

export function postChat(req: AssistantRequest): Promise<AssistantResponse> {
  return postJSON('/api/ai-assistant', req)
}

function structuredDetail(value: unknown): StructuredApiErrorDetail | null {
  if (!value || typeof value !== 'object') return null
  const detail = value as Record<string, unknown>
  if (typeof detail.code !== 'string' || typeof detail.message !== 'string') return null
  return {
    code: detail.code,
    message: detail.message,
    context: detail.context && typeof detail.context === 'object'
      ? detail.context as Record<string, unknown>
      : undefined,
  }
}

function safeOfficialErrorMessage(status: number): string {
  if (status === 401) return 'Your sign-in session has expired. Please sign in again.'
  if (status === 403) return 'This account cannot run a student simulation.'
  if (status === 422) return 'The simulation request could not be validated.'
  return 'Official simulation state is temporarily unavailable. Please try again.'
}

async function officialRequest<T>(
  url: string,
  init: RequestInit,
): Promise<T> {
  let res: Response
  try {
    res = await fetch(url, {
      credentials: 'include',
      ...init,
    })
  } catch (err) {
    throw new NetworkError(err instanceof Error ? err.message : 'Network request failed')
  }
  if (!res.ok) {
    const parsed = await res.json().catch(() => null)
    const rawDetail = parsed && typeof parsed === 'object'
      ? (parsed as Record<string, unknown>).detail
      : undefined
    const detail = structuredDetail(rawDetail)
    if (detail) {
      throw new OfficialSimulationApiError(res.status, detail.message, detail.code)
    }
    if (typeof rawDetail === 'string' && (res.status === 400 || res.status === 409)) {
      throw new OfficialSimulationApiError(res.status, rawDetail)
    }
    throw new OfficialSimulationApiError(res.status, safeOfficialErrorMessage(res.status))
  }
  return res.json() as Promise<T>
}

export function getOfficialSimulationSession(
  signal?: AbortSignal,
): Promise<OfficialSimulationSession> {
  return officialRequest('/api/simulation/session', { method: 'GET', signal })
}

export function postRunNextMonth(
  request: RunNextMonthRequest,
): Promise<RunNextMonthResponse> {
  return officialRequest('/api/simulation/session/months/next', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  })
}

export function getSameStageLeaderboard(signal?: AbortSignal): Promise<LeaderboardResponse> {
  return officialRequest('/api/leaderboards/same-stage', { method: 'GET', signal })
}

export function getFinalLeaderboard(signal?: AbortSignal): Promise<LeaderboardResponse> {
  return officialRequest('/api/leaderboards/final', { method: 'GET', signal })
}
