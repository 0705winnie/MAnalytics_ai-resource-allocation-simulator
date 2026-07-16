import type {
  MonthDetailResult,
  SimulateMonthRequest,
  SimulateRequest,
  SimulationResponse,
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

export async function postChat(req: AssistantRequest): Promise<AssistantResponse> {
  const res = await fetch('/api/ai-assistant', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  })
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}))
    throw new Error((detail as { detail?: string })?.detail ?? `HTTP ${res.status}`)
  }
  return res.json() as Promise<AssistantResponse>
}

export async function postSimulate(req: SimulateRequest): Promise<SimulationResponse> {
  const res = await fetch('/api/simulate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  })
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}))
    throw new Error((detail as { detail?: string })?.detail ?? `HTTP ${res.status}`)
  }
  return res.json() as Promise<SimulationResponse>
}

export async function postSimulateMonth(req: SimulateMonthRequest): Promise<MonthDetailResult> {
  const res = await fetch('/api/simulate/month', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  })
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}))
    throw new Error((detail as { detail?: string })?.detail ?? `HTTP ${res.status}`)
  }
  return res.json() as Promise<MonthDetailResult>
}
