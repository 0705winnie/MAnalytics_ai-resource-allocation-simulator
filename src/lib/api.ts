import type {
  MonthDetailResult,
  SimulateMonthRequest,
  SimulateRequest,
  SimulationResponse,
  SubmitResultRequest,
  SubmitResultResponse,
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

export function postSimulate(req: SimulateRequest): Promise<SimulationResponse> {
  return postJSON('/api/simulate', req)
}

export function postSimulateMonth(req: SimulateMonthRequest): Promise<MonthDetailResult> {
  return postJSON('/api/simulate/month', req)
}

// A separate, authenticated flow from postSimulate/postSimulateMonth above:
// this is the only call in this file that sends the student's session
// cookie, since submitting a result (unlike running a simulation) must be
// tied to the authenticated student's enrollment.
async function postJSONAuthenticated<T>(url: string, body: unknown): Promise<T> {
  let res: Response
  try {
    res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
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

export function postSubmitResult(req: SubmitResultRequest): Promise<SubmitResultResponse> {
  return postJSONAuthenticated('/api/submissions', req)
}
