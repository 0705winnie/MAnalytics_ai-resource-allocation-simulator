import { useState, useRef, useEffect, type ReactNode } from 'react'
import { postChat, type ChatMessage } from '../lib/api'
import type { MonthDetailResult, PolicyParams } from '../types/simulation'
import type { Page } from '../components/NavBar'

const MONTH_LABELS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
const TOTAL_MONTHS = 12

// ── Constants ────────────────────────────────────────────────────────────────

export const POLICY_TEMPLATE = `def admission_policy(request, state, history, params):
    """
    request : dict — {"type": str, "required_units": int, "arrival_time": float}
    state   : dict — {"remaining_capacity": {1: int, 2: int, 3: int}}
    history : dict — historical data + previous monthly results
    params  : dict — your tunable parameters (can be empty {})
    returns : int  — cluster id (1, 2, or 3) to admit, or 0 to reject
    """
    # Example: greedy first-fit — admit to the first cluster with enough room.
    # Replace this with your own logic.
    for cluster_id, remaining in state["remaining_capacity"].items():
        if remaining >= request["required_units"]:
            return cluster_id
    return 0  # reject if no cluster has enough capacity`

const INTERFACE_SPEC = `def admission_policy(request, state, history, params):
    # Called once per arriving request. Must return an int.
    # return 1 | 2 | 3   →  admit to that cluster
    # return 0            →  reject the request
    ...`

const INPUT_FIELDS = [
  { key: 'request["type"]',            val: '"VIP" | "Standard" | "Economy"' },
  { key: 'request["required_units"]',  val: 'int — units of capacity needed' },
  { key: 'request["arrival_time"]',    val: 'float — arrival time within month' },
  { key: 'state["remaining_capacity"]', val: '{1: int, 2: int, 3: int} — free units per cluster' },
]

const SUGGESTED_PROMPTS = [
  'How should I handle VIP vs. Economy requests differently?',
  'What is a good threshold for rejecting Economy jobs?',
  'My policy rejects too many VIPs — how do I fix it?',
  'Suggest a type-priority routing rule in pseudocode.',
]

const CHECKLIST = [
  { done: true,  text: 'Always return 0 if no cluster has enough capacity — never return an infeasible cluster id.' },
  { done: false, text: 'Prioritise VIP over Economy when capacity is scarce — they earn 3× more per unit.' },
  { done: false, text: 'Try a capacity guard: reject Economy requests if every cluster drops below ~30 free units.' },
  { done: false, text: 'Route to the least-loaded cluster rather than always Cluster 1 to avoid load imbalance.' },
]

// ── Sub-components ───────────────────────────────────────────────────────────

function SectionCard({
  title,
  label,
  children,
}: {
  title: string
  label?: string
  children: ReactNode
}) {
  return (
    <div className="rounded-lg border border-gray-800 bg-gray-900 p-5">
      <div className="flex items-center gap-3 mb-4">
        {label && (
          <span className="text-xs font-mono px-2 py-0.5 rounded bg-gray-800 text-gray-600 shrink-0">
            {label}
          </span>
        )}
        <h2 className="text-xs font-semibold uppercase tracking-widest text-gray-500">
          {title}
        </h2>
      </div>
      {children}
    </div>
  )
}

function ValidationBadge({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded border ${
        ok
          ? 'border-lime-800/50 bg-lime-950/30 text-lime-400'
          : 'border-amber-800/40 bg-amber-950/20 text-amber-500'
      }`}
    >
      {ok ? '✓' : '!'}  {label}
    </span>
  )
}

function ProviderBadge({ provider }: { provider: 'azure' | 'mock' | undefined }) {
  if (!provider) return null
  return (
    <span
      className={`text-xs font-mono px-2 py-0.5 rounded ${
        provider === 'azure'
          ? 'bg-blue-950/70 text-blue-400'
          : 'bg-gray-800 text-gray-500'
      }`}
    >
      {provider}
    </span>
  )
}

function MessageContent({ content }: { content: string }) {
  const parts = content.split(/(```[\s\S]*?```)/g)
  return (
    <div className="text-sm leading-relaxed space-y-2">
      {parts.map((part, i) => {
        if (part.startsWith('```')) {
          const code = part.slice(3).replace(/^\w*\n/, '').replace(/\n?```$/, '')
          return (
            <pre
              key={i}
              className="bg-gray-950 border border-gray-800 rounded p-3 text-xs font-mono text-gray-300 overflow-x-auto whitespace-pre-wrap"
            >
              {code}
            </pre>
          )
        }
        // Render text with **bold** and preserved newlines
        return (
          <div key={i} className="text-gray-400 whitespace-pre-wrap">
            {part.split(/(\*\*[^*\n]+\*\*)/g).map((seg, j) =>
              seg.startsWith('**') && seg.endsWith('**') ? (
                <strong key={j} className="text-gray-200 font-medium">
                  {seg.slice(2, -2)}
                </strong>
              ) : (
                seg
              ),
            )}
          </div>
        )
      })}
    </div>
  )
}

function ParamsEditor({
  params,
  onChange,
}: {
  params: PolicyParams
  onChange: (next: PolicyParams) => void
}) {
  const entries = Object.entries(params)

  function updateKey(oldKey: string, newKey: string) {
    if (!newKey || newKey === oldKey) return
    const next = { ...params }
    delete next[oldKey]
    next[newKey] = params[oldKey]
    onChange(next)
  }

  function updateValue(key: string, value: string) {
    const parsed = parseFloat(value)
    onChange({ ...params, [key]: Number.isNaN(parsed) ? 0 : parsed })
  }

  function removeParam(key: string) {
    const next = { ...params }
    delete next[key]
    onChange(next)
  }

  function addParam() {
    let name = 'new_param'
    let i = 1
    while (name in params) {
      name = `new_param_${i}`
      i += 1
    }
    onChange({ ...params, [name]: 0 })
  }

  return (
    <div>
      <p className="text-gray-500 text-xs leading-relaxed mb-3">
        These key/value pairs are passed into your policy as the <code className="text-hud-accent">params</code> dict —
        use them for thresholds or multipliers you want to tune without editing code. They carry over
        into <strong className="text-gray-300">03 Simulation</strong> automatically.
      </p>
      <div className="space-y-2">
        {entries.map(([key, value]) => (
          <div key={key} className="flex items-center gap-2">
            <input
              defaultValue={key}
              onBlur={(e) => updateKey(key, e.target.value.trim())}
              className="flex-1 rounded border border-gray-800 bg-gray-950 px-2.5 py-1.5 text-xs font-mono text-gray-300 focus:outline-none focus:border-hud-accent/50"
            />
            <input
              type="number"
              value={value}
              onChange={(e) => updateValue(key, e.target.value)}
              className="w-28 rounded border border-gray-800 bg-gray-950 px-2.5 py-1.5 text-xs font-mono text-gray-300 focus:outline-none focus:border-hud-accent/50"
            />
            <button
              onClick={() => removeParam(key)}
              className="shrink-0 text-gray-700 hover:text-red-400 text-xs px-1.5 transition-colors"
              aria-label={`Remove ${key}`}
            >
              ✕
            </button>
          </div>
        ))}
        {entries.length === 0 && (
          <p className="text-gray-700 text-xs italic">No parameters yet — add one below.</p>
        )}
      </div>
      <button
        onClick={addParam}
        className="mt-3 text-xs text-gray-600 hover:text-hud-accent border border-gray-800 hover:border-hud-accent/40 rounded px-2.5 py-1 transition-colors"
      >
        + Add parameter
      </button>
    </div>
  )
}

// ── Page ─────────────────────────────────────────────────────────────────────

interface Props {
  policyCode: string
  onPolicyCodeChange: (code: string) => void
  policyParams: PolicyParams
  onPolicyParamsChange: (params: PolicyParams) => void
  messages: ChatMessage[]
  onMessagesChange: (messages: ChatMessage[]) => void
  provider: 'azure' | 'mock' | undefined
  onProviderChange: (provider: 'azure' | 'mock' | undefined) => void
  onNavigate: (page: Page) => void
  completedMonths: MonthDetailResult[]
}

export default function PolicyAIPage({
  policyCode,
  onPolicyCodeChange,
  policyParams,
  onPolicyParamsChange,
  messages,
  onMessagesChange,
  provider,
  onProviderChange,
  onNavigate,
  completedMonths,
}: Props) {
  const [input,   setInput]   = useState('')
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState<string | null>(null)

  const chatEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  const hasSignature = policyCode.includes('def admission_policy(')
  const hasReturn    = policyCode.includes('return ')
  const isValid      = hasSignature && hasReturn

  const nextMonth = completedMonths.length < TOTAL_MONTHS ? completedMonths.length + 1 : null
  const latestMonth = completedMonths.length > 0 ? completedMonths[completedMonths.length - 1] : null

  async function sendMessage(text: string) {
    const trimmed = text.trim()
    if (!trimmed || loading) return

    const userMsg: ChatMessage = { role: 'user', content: trimmed }
    const priorHistory = messages
    onMessagesChange([...messages, userMsg])
    setInput('')
    setLoading(true)
    setError(null)

    try {
      const res = await postChat({ message: trimmed, history: priorHistory })
      onMessagesChange([...priorHistory, userMsg, { role: 'assistant', content: res.content }])
      onProviderChange(res.provider)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Request failed')
    } finally {
      setLoading(false)
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage(input)
    }
  }

  function shareCode() {
    setInput(
      `Here is my current policy code — can you review it and suggest improvements?\n\n\`\`\`python\n${policyCode}\n\`\`\``,
    )
  }

  return (
    <div className="space-y-6">

      {/* ── Hero ───────────────────────────────────────────────────────── */}
      <div className="rounded-xl border border-gray-800 bg-gradient-to-br from-gray-900 via-gray-900 to-lime-950/10 p-7">
        <div className="flex items-center gap-2 mb-4">
          <span className="text-xs font-mono px-2.5 py-1 rounded-full border border-gray-700 text-gray-500 tracking-widest uppercase">
            02  Policy &amp; AI
          </span>
        </div>
        <h1 className="text-xl font-bold text-gray-100 tracking-tight mb-2">
          Design Your Admission Policy
        </h1>
        <p className="text-gray-400 text-sm leading-relaxed max-w-3xl">
          Write a Python function that decides — for every arriving request — whether to
          admit it to a cluster or reject it. The AI assistant on the right is here to
          help you think through your logic, suggest ideas, and debug your code.
          When you are satisfied, head to{' '}
          <strong className="text-gray-300">03 Simulation</strong> to run the next month.
        </p>

        <div className="mt-5 flex flex-wrap items-center gap-3 rounded-lg border border-gray-800 bg-gray-950/60 px-4 py-3">
          <span className="text-xs font-mono px-2 py-0.5 rounded bg-gray-800 text-gray-500 shrink-0">
            Session
          </span>
          {nextMonth !== null ? (
            <span className="text-gray-300 text-xs">
              Next up: <strong className="text-hud-accent">Month {nextMonth}</strong>{' '}
              ({MONTH_LABELS[nextMonth - 1]}) — {completedMonths.length} of {TOTAL_MONTHS} months done.
            </span>
          ) : (
            <span className="text-gray-300 text-xs">
              <strong className="text-hud-positive">All 12 months complete.</strong> Revise your policy and
              reset the session on <strong className="text-gray-300">03 Simulation</strong> to try again.
            </span>
          )}
          {latestMonth && (
            <span className="text-gray-600 text-xs border-l border-gray-800 pl-3">
              Latest: Month {latestMonth.month} earned{' '}
              <span className="font-mono text-gray-400">${latestMonth.total_revenue.toLocaleString()}</span>,{' '}
              {latestMonth.rejected_requests} rejected
              {latestMonth.warnings.length > 0 && (
                <span className="text-amber-500"> · {latestMonth.warnings.length} warning{latestMonth.warnings.length === 1 ? '' : 's'}</span>
              )}
            </span>
          )}
        </div>
      </div>

      {/* ── Two-column layout ──────────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-[3fr_2fr] gap-6 items-start">

        {/* ── Left: Policy editor ──────────────────────────────────────── */}
        <div className="space-y-5">

          {/* Interface specification */}
          <SectionCard title="Policy Interface" label="Contract">
            <p className="text-gray-500 text-xs leading-relaxed mb-4">
              Your function is called once per arriving request. It must return an integer
              cluster id (1, 2, or 3) to admit the request, or 0 to reject it. If you
              return an infeasible cluster id (not enough capacity), the simulator
              auto-rejects and logs a warning.
            </p>
            <pre className="bg-gray-950 border border-gray-800 rounded p-4 text-xs font-mono text-gray-400 overflow-x-auto leading-relaxed mb-4">
              {INTERFACE_SPEC}
            </pre>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {INPUT_FIELDS.map(({ key, val }) => (
                <div
                  key={key}
                  className="rounded border border-gray-800 bg-gray-950 px-3 py-2"
                >
                  <div className="font-mono text-hud-accent text-xs">{key}</div>
                  <div className="text-gray-600 text-xs mt-0.5">{val}</div>
                </div>
              ))}
            </div>
          </SectionCard>

          {/* Policy editor */}
          <SectionCard title="Your Policy" label="Editor">
            <div className="flex items-center justify-between mb-3">
              <p className="text-gray-500 text-xs">
                The template shows a greedy first-fit baseline. Edit it or replace it
                entirely.
              </p>
              <button
                onClick={shareCode}
                className="shrink-0 text-xs text-gray-600 hover:text-hud-accent border border-gray-800 hover:border-hud-accent/40 rounded px-2.5 py-1 transition-colors ml-3"
              >
                Ask AI to review ↗
              </button>
            </div>
            <textarea
              className="w-full rounded border border-gray-700 bg-gray-950 p-4 font-mono text-xs text-gray-300 leading-relaxed resize-y focus:outline-none focus:border-hud-accent/50 transition-colors"
              rows={18}
              value={policyCode}
              onChange={(e) => onPolicyCodeChange(e.target.value)}
              spellCheck={false}
            />
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <ValidationBadge ok={hasSignature} label="def admission_policy(...) present" />
              <ValidationBadge ok={hasReturn}    label="return statement present" />
              {isValid && (
                <span className="text-xs text-lime-400/60 ml-auto">
                  Looks good — ready to simulate
                </span>
              )}
            </div>
          </SectionCard>

          {/* Tunable parameters */}
          <SectionCard title="Parameters" label="Params">
            <ParamsEditor params={policyParams} onChange={onPolicyParamsChange} />
          </SectionCard>

          {/* Design checklist */}
          <SectionCard title="Design Checklist" label="Tips">
            <ul className="space-y-2.5">
              {CHECKLIST.map(({ done, text }) => (
                <li key={text} className="flex gap-2.5 text-xs">
                  <span
                    className={`shrink-0 mt-px ${
                      done ? 'text-lime-400' : 'text-gray-700'
                    }`}
                  >
                    {done ? '✓' : '○'}
                  </span>
                  <span className={done ? 'text-lime-400/70' : 'text-gray-500'}>
                    {text}
                  </span>
                </li>
              ))}
            </ul>
          </SectionCard>

        </div>

        {/* ── Right: AI assistant (sticky) ─────────────────────────────── */}
        <div
          className="sticky top-6 rounded-lg border border-gray-800 bg-gray-900 flex flex-col"
          style={{ height: 'calc(100vh - 6rem)', minHeight: '540px' }}
        >
          {/* Header */}
          <div className="flex items-center justify-between px-5 py-3.5 border-b border-gray-800 shrink-0">
            <div>
              <h2 className="text-xs font-semibold uppercase tracking-widest text-gray-500">
                AI Assistant
              </h2>
              <p className="text-gray-700 text-xs mt-0.5">
                Ask about your policy, data patterns, or trade-offs.
              </p>
            </div>
            <ProviderBadge provider={provider} />
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4 min-h-0">
            {messages.length === 0 && (
              <div className="py-6">
                <p className="text-gray-700 text-xs mb-4 text-center">
                  No messages yet. Try a suggested prompt or ask anything.
                </p>
                <div className="space-y-2">
                  {SUGGESTED_PROMPTS.map((p) => (
                    <button
                      key={p}
                      onClick={() => sendMessage(p)}
                      disabled={loading}
                      className="w-full text-left text-xs text-gray-600 border border-gray-800 rounded px-3 py-2.5 hover:border-gray-600 hover:text-gray-300 disabled:opacity-40 transition-colors"
                    >
                      {p}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((msg, i) => (
              <div
                key={i}
                className={`flex flex-col gap-1 ${
                  msg.role === 'user' ? 'items-end' : 'items-start'
                }`}
              >
                <span className="text-xs text-gray-700 px-1">
                  {msg.role === 'user' ? 'You' : 'Assistant'}
                </span>
                <div
                  className={`rounded-lg px-4 py-3 max-w-[94%] ${
                    msg.role === 'user'
                      ? 'bg-blue-950/50 border border-blue-900/40 text-sm text-gray-300'
                      : 'bg-gray-800/50 border border-gray-700/40'
                  }`}
                >
                  {msg.role === 'assistant' ? (
                    <MessageContent content={msg.content} />
                  ) : (
                    <p className="text-sm text-gray-300 leading-relaxed whitespace-pre-wrap">
                      {msg.content}
                    </p>
                  )}
                </div>
              </div>
            ))}

            {loading && (
              <div className="flex items-start">
                <div className="rounded-lg px-4 py-3 bg-gray-800/50 border border-gray-700/40">
                  <div className="flex gap-1 items-center h-4">
                    {[0, 150, 300].map((delay) => (
                      <span
                        key={delay}
                        className="w-1.5 h-1.5 rounded-full bg-gray-500 animate-bounce"
                        style={{ animationDelay: `${delay}ms` }}
                      />
                    ))}
                  </div>
                </div>
              </div>
            )}

            {error && (
              <div className="rounded border border-red-900/40 bg-red-950/20 px-3 py-2.5 text-xs text-red-400 leading-relaxed">
                <strong>Error:</strong> {error}
                <br />
                <span className="text-red-600">
                  Is the backend running?{' '}
                  <code className="text-red-500">
                    cd backend &amp;&amp; uvicorn app.main:app --reload
                  </code>
                </span>
              </div>
            )}

            <div ref={chatEndRef} />
          </div>

          {/* Input */}
          <div className="px-4 pb-4 pt-3 border-t border-gray-800 shrink-0">
            <div className="flex gap-2 items-end">
              <textarea
                rows={2}
                className="flex-1 rounded border border-gray-700 bg-gray-950 px-3 py-2 text-sm text-gray-300 resize-none focus:outline-none focus:border-hud-accent/50 transition-colors leading-relaxed placeholder:text-gray-700"
                placeholder="Ask a question… (Enter to send, Shift+Enter for newline)"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                disabled={loading}
              />
              <button
                onClick={() => sendMessage(input)}
                disabled={loading || !input.trim()}
                className="rounded border border-hud-accent/30 bg-blue-950/30 px-4 py-2 text-xs font-medium text-hud-accent hover:bg-blue-950/50 disabled:opacity-30 disabled:cursor-not-allowed transition-colors shrink-0 self-end"
              >
                Send
              </button>
            </div>
            {messages.length > 0 && (
              <button
                onClick={() => {
                  onMessagesChange([])
                  onProviderChange(undefined)
                  setError(null)
                }}
                className="mt-2 text-xs text-gray-700 hover:text-gray-500 transition-colors"
              >
                Clear conversation
              </button>
            )}
          </div>
        </div>

      </div>

      {/* ── CTA ────────────────────────────────────────────────────────── */}
      <button
        type="button"
        onClick={() => onNavigate(3)}
        className="w-full text-left rounded-xl border border-hud-positive/20 bg-gradient-to-r from-lime-950/20 to-gray-900 p-6 flex items-center justify-between gap-6 hover:border-hud-positive/50 hover:from-lime-950/30 transition-colors cursor-pointer"
      >
        <div>
          <p className="text-xs font-mono uppercase tracking-widest text-hud-positive mb-2">
            Next Step
          </p>
          <h3 className="text-gray-100 font-semibold text-base mb-1.5">
            {nextMonth !== null ? `Ready to run Month ${nextMonth}?` : 'Ready to review your final results?'}
          </h3>
          <p className="text-gray-500 text-sm max-w-lg">
            Head to <strong className="text-gray-300">03 Simulation</strong> to run the
            next month and see how much revenue it earns. Come back here anytime between
            months to refine your code — completed months stay locked.
          </p>
        </div>
        <div className="shrink-0 text-hud-positive text-4xl font-thin opacity-50 select-none">
          →
        </div>
      </button>

    </div>
  )
}
