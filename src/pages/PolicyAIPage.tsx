import { useState, useRef, useEffect, type ReactNode } from 'react'
import {
  AIQuotaError,
  NetworkError,
  boundedCompleteHistory,
  getAIUsage,
  postChat,
  type AssistantUsage,
  type ChatMessage,
} from '../lib/api'
import type { OfficialSimulationSession, PolicyParams } from '../types/simulation'
import type { Page } from '../components/NavBar'

const MONTH_LABELS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
const TOTAL_MONTHS = 12

// ── Constants ────────────────────────────────────────────────────────────────

export const POLICY_TEMPLATE = `def admission_policy(request, state, history, params):
    """
    request : dict - {"type": str, "required_units": int, "arrival_time": float}
    state   : dict - {"remaining_capacity": {cluster_id: remaining_units}}
    history : dict - historical data + previous monthly results
    params  : dict - your tunable parameters (can be empty {})
    returns : int  - cluster id (1 through 10) to admit, or 0 to reject
    """
    # Example: greedy first-fit - admit to the first cluster with enough room.
    # Replace this with your own logic.
    for cluster_id, remaining in state["remaining_capacity"].items():
        if remaining >= request["required_units"]:
            return cluster_id
    return 0  # reject if no cluster has enough capacity`

const INTERFACE_SPEC = `def admission_policy(request, state, history, params):
    # Called once per arriving request. Must return an int.
    # return 1..10  -> admit to that cluster
    # return 0      -> reject the request
    ...`

const INPUT_FIELDS = [
  { key: 'request["type"]',            val: '"VIP" | "Standard" | "Economy"' },
  { key: 'request["required_units"]',  val: 'int - units of capacity needed' },
  { key: 'request["arrival_time"]',    val: 'float - arrival time within month' },
  { key: 'state["remaining_capacity"]', val: '{cluster_id: remaining_units} - free units per cluster' },
]

const SUGGESTED_PROMPTS = [
  'How should I handle VIP vs. Economy requests differently?',
  'What is a good threshold for rejecting Economy jobs?',
  'My policy rejects too many VIPs — how do I fix it?',
  'Help me write a type-priority routing rule in Python.',
]

const POLICY_DESIGN_TIPS = [
  'Return `0` when no cluster has sufficient capacity.',
  'Consider prioritizing higher-value requests when capacity is scarce.',
  'Consider using a capacity guard for lower-value requests.',
  'Consider load-aware routing instead of always choosing the same cluster.',
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
    <div className="rounded-lg border border-line bg-white p-5 shadow-card">
      <div className="flex items-center gap-3 mb-4">
        {label && (
          <span className="text-xs font-mono px-2 py-0.5 rounded bg-chip text-ink-faint shrink-0">
            {label}
          </span>
        )}
        <h2 className="text-xs font-semibold uppercase tracking-widest text-ink-faint">
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
          ? 'border-hud-positive/50 bg-hud-positive/10 text-hud-positive'
          : 'border-amber-300 bg-amber-50 text-amber-700'
      }`}
    >
      {ok ? 'check' : '!'}  {label}
    </span>
  )
}

function ProviderBadge({ provider }: { provider: 'azure' | undefined }) {
  if (!provider) return null
  return (
    <span
      className="text-xs font-mono px-2 py-0.5 rounded bg-hud-accent/12 text-hud-accent"
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
              className="bg-well border border-line rounded p-3 text-xs font-mono text-ink-dim overflow-x-auto whitespace-pre-wrap"
            >
              {code}
            </pre>
          )
        }
        // Render text with **bold** and preserved newlines
        return (
          <div key={i} className="text-ink-dim whitespace-pre-wrap">
            {part.split(/(\*\*[^*\n]+\*\*)/g).map((seg, j) =>
              seg.startsWith('**') && seg.endsWith('**') ? (
                <strong key={j} className="text-ink font-medium">
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
      <p className="text-ink-faint text-xs leading-relaxed mb-3">
        These key/value pairs are passed into your policy as the <code className="text-hud-accent">params</code> dict -
        use them for thresholds or multipliers you want to tune without editing code. They carry over
        into <strong className="text-ink-dim">03 Simulation</strong> automatically.
      </p>
      <div className="space-y-2">
        {entries.map(([key, value]) => (
          <div key={key} className="flex items-center gap-2">
            <input
              defaultValue={key}
              onBlur={(e) => updateKey(key, e.target.value.trim())}
              className="flex-1 rounded border border-line bg-well px-2.5 py-1.5 text-xs font-mono text-ink-dim focus:outline-none focus:border-hud-accent/50"
            />
            <input
              type="number"
              value={value}
              onChange={(e) => updateValue(key, e.target.value)}
              className="w-28 rounded border border-line bg-well px-2.5 py-1.5 text-xs font-mono text-ink-dim focus:outline-none focus:border-hud-accent/50"
            />
            <button
              onClick={() => removeParam(key)}
              className="shrink-0 text-ink-faintest hover:text-red-600 text-xs px-1.5 transition-colors"
              aria-label={`Remove ${key}`}
            >
              x
            </button>
          </div>
        ))}
        {entries.length === 0 && (
          <p className="text-ink-faintest text-xs italic">No parameters yet - add one below.</p>
        )}
      </div>
      <button
        onClick={addParam}
        className="mt-3 text-xs text-ink-faint hover:text-hud-accent border border-line hover:border-hud-accent/40 rounded px-2.5 py-1 transition-colors"
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
  provider: 'azure' | undefined
  onProviderChange: (provider: 'azure' | undefined) => void
  onNavigate: (page: Page) => void
  session: OfficialSimulationSession
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
  session,
}: Props) {
  const [input,   setInput]   = useState('')
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState<string | null>(null)
  const [errorIsNetwork, setErrorIsNetwork] = useState(false)
  const [usage, setUsage] = useState<AssistantUsage | null>(null)
  const [quotaExhausted, setQuotaExhausted] = useState(false)
  const [responseLimitWarning, setResponseLimitWarning] = useState<string | null>(null)

  const chatEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  useEffect(() => {
    const controller = new AbortController()
    getAIUsage(controller.signal)
      .then((nextUsage) => {
        setUsage(nextUsage)
        setQuotaExhausted(
          nextUsage.metered && nextUsage.calls_used >= nextUsage.calls_limit,
        )
      })
      .catch(() => undefined)
    return () => controller.abort()
  }, [])

  const hasSignature = policyCode.includes('def admission_policy(')
  const hasReturn    = policyCode.includes('return ')
  const isValid      = hasSignature && hasReturn

  const completedMonths = session.monthly_results
  const nextMonth = session.next_month
  const latestMonth = completedMonths.length > 0 ? completedMonths[completedMonths.length - 1] : null

  async function sendMessage(text: string) {
    const trimmed = text.trim()
    if (!trimmed || loading || quotaExhausted) return

    const userMsg: ChatMessage = { role: 'user', content: trimmed }
    const priorHistory = boundedCompleteHistory(messages)
    onMessagesChange([...messages, userMsg])
    setInput('')
    setLoading(true)
    setError(null)
    setErrorIsNetwork(false)
    setResponseLimitWarning(null)

    try {
      const res = await postChat({
        message: trimmed,
        history: priorHistory,
        draft_policy_code: policyCode,
        draft_params: policyParams,
      })
      onMessagesChange([...priorHistory, userMsg, { role: 'assistant', content: res.content }])
      onProviderChange(res.provider)
      setResponseLimitWarning(
        res.response_limited
          ? 'Response reached the length limit. Ask the AI to continue.'
          : null,
      )
      setUsage(res.usage)
      setQuotaExhausted(
        res.usage.metered && res.usage.calls_used >= res.usage.calls_limit,
      )
    } catch (err) {
      if (err instanceof AIQuotaError) {
        setQuotaExhausted(true)
        setError('Daily AI assistant limit reached. Your allowance resets tomorrow.')
      } else {
        setError(err instanceof Error ? err.message : 'Request failed')
      }
      setErrorIsNetwork(err instanceof NetworkError)
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
      `Here is my current policy code - can you review it and suggest improvements?\n\n\`\`\`python\n${policyCode}\n\`\`\``,
    )
  }

  return (
    <div className="space-y-6">

      {/* ── Hero ────────────────────────────────────────────────────────── */}
      <div className="rounded-xl border border-line bg-gradient-to-br from-white via-white to-hud-positive/5 p-7 shadow-card">
        <div className="flex items-center gap-2 mb-4">
          <span className="text-xs font-mono px-2.5 py-1 rounded-full border border-line-strong text-ink-faint tracking-widest uppercase">
            02  Policy &amp; AI
          </span>
        </div>
        <h1 className="text-xl font-bold text-ink tracking-tight mb-2">
          Design Your Admission Policy
        </h1>
        <p className="text-ink-dim text-sm leading-relaxed max-w-3xl">
          Write a Python function that decides - for every arriving request - whether to
          admit it to a cluster or reject it. The AI assistant on the right is here to
          help you think through your logic, suggest ideas, and debug your code.
          When you are satisfied, head to{' '}
          <strong className="text-ink-dim">03 Simulation</strong> to run the next month.
        </p>

        <div className="mt-5 rounded-lg border border-line bg-well/60 px-4 py-3 space-y-2.5">
          <div className="flex flex-wrap items-center gap-3">
            <span className="text-xs font-mono px-2 py-0.5 rounded bg-chip text-ink-faint shrink-0">
              Session
            </span>
            {nextMonth !== null ? (
              <span className="text-ink-dim text-xs">
                Next up: <strong className="text-hud-accent">Month {nextMonth}</strong>{' '}
                ({MONTH_LABELS[nextMonth - 1]}) - {completedMonths.length} of {TOTAL_MONTHS} months done.
              </span>
            ) : (
              <span className="text-ink-dim text-xs">
                <strong className="text-hud-positive">All 12 months complete.</strong> Review the official
                persisted results on <strong className="text-ink-dim">03 Simulation</strong> or Page 04.
              </span>
            )}
          </div>

          {latestMonth && (
            <div className="flex flex-wrap items-center gap-2 border-t border-line pt-2.5">
              <span className="text-ink-faint text-xs shrink-0">
                Latest - Month {latestMonth.month} ({MONTH_LABELS[latestMonth.month - 1]}):
              </span>
              <span className="text-xs font-mono px-2 py-0.5 rounded bg-chip text-ink-dim">
                ${latestMonth.total_revenue.toLocaleString()} revenue
              </span>
              <span className="text-xs font-mono px-2 py-0.5 rounded bg-chip text-ink-dim">
                {latestMonth.rejected_requests} rejected
              </span>
              {latestMonth.warnings.length > 0 && (
                <span className="text-xs font-mono px-2 py-0.5 rounded bg-amber-50 text-amber-700">
                  {latestMonth.warnings.length} warning{latestMonth.warnings.length === 1 ? '' : 's'}
                </span>
              )}
            </div>
          )}

          {completedMonths.length > 0 && nextMonth !== null && (
            <p className="text-ink-faint text-xs border-t border-line pt-2.5">
              Edits below only take effect on <strong className="text-ink-dim">Month {nextMonth}</strong>{' '}
              and later -{' '}
              {completedMonths.length === 1 ? 'Month 1 is' : `Months 1-${completedMonths.length} are`}{' '}
              already locked in and won't be recalculated.
            </p>
          )}
        </div>
      </div>

      {/* ── Two-column layout ───────────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-[3fr_2fr] gap-6 items-start">

        {/* ── Left: Policy editor ───────────────────────────────────────── */}
        <div className="space-y-5">

          {/* Interface specification */}
          <SectionCard title="Policy Interface" label="Contract">
            <p className="text-ink-faint text-xs leading-relaxed mb-4">
              Your function is called once per arriving request. It must return an integer
              cluster id (1 through 10) to admit the request, or 0 to reject it. If you
              return an infeasible cluster id (not enough capacity), the simulator
              auto-rejects and logs a warning.
            </p>
            <pre className="bg-well border border-line rounded p-4 text-xs font-mono text-ink-dim overflow-x-auto leading-relaxed mb-4">
              {INTERFACE_SPEC}
            </pre>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {INPUT_FIELDS.map(({ key, val }) => (
                <div
                  key={key}
                  className="rounded border border-line bg-well px-3 py-2"
                >
                  <div className="font-mono text-hud-accent text-xs">{key}</div>
                  <div className="text-ink-faint text-xs mt-0.5">{val}</div>
                </div>
              ))}
            </div>
          </SectionCard>

          {/* Policy editor */}
          <SectionCard title="Your Policy" label="Editor">
            <div className="flex items-center justify-between mb-3">
              <p className="text-ink-faint text-xs">
                The template shows a greedy first-fit baseline. Edit it or replace it
                entirely.
              </p>
              <button
                onClick={shareCode}
                className="shrink-0 text-xs text-ink-faint hover:text-hud-accent border border-line hover:border-hud-accent/40 rounded px-2.5 py-1 focus:outline-none focus-visible:ring-2 focus-visible:ring-hud-accent/60 transition-colors ml-3"
              >
                Ask AI to review {'->'}
              </button>
            </div>
            <textarea
              className="w-full rounded border border-line-strong bg-well p-4 font-mono text-xs text-ink-dim leading-relaxed resize-y focus:outline-none focus:border-hud-accent/50 transition-colors"
              rows={18}
              value={policyCode}
              onChange={(e) => onPolicyCodeChange(e.target.value)}
              spellCheck={false}
            />
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <ValidationBadge ok={hasSignature} label="def admission_policy(...) present" />
              <ValidationBadge ok={hasReturn}    label="return statement present" />
              {isValid && (
                <span className="text-xs text-hud-positive/60 ml-auto">
                  Looks good - ready to simulate
                </span>
              )}
            </div>
          </SectionCard>

          {/* Tunable parameters */}
          <SectionCard title="Parameters" label="Params">
            <ParamsEditor params={policyParams} onChange={onPolicyParamsChange} />
          </SectionCard>

          {/* Informational policy tips */}
          <SectionCard title="Policy Design Tips" label="Tips">
            <ul className="list-disc space-y-2.5 pl-4">
              {POLICY_DESIGN_TIPS.map((text) => (
                <li key={text} className="text-xs leading-relaxed text-ink-faint">
                  {text}
                </li>
              ))}
            </ul>
          </SectionCard>

        </div>

        {/* ── Right: AI assistant (sticky) ──────────────────────────────── */}
        <div
          className="sticky top-6 rounded-lg border border-line bg-white shadow-card flex flex-col"
          style={{ height: 'calc(100vh - 6rem)', minHeight: '540px' }}
        >
          {/* Header */}
          <div className="flex items-center justify-between px-5 py-3.5 border-b border-line shrink-0">
            <div>
              <h2 className="text-xs font-semibold uppercase tracking-widest text-ink-faint">
                AI Assistant
              </h2>
              <p className="text-ink-faintest text-xs mt-0.5">
                Ask about your policy, data patterns, or trade-offs.
              </p>
              {usage && (
                <p className="mt-1 text-xs font-medium text-ink-dim">
                  {`${usage.calls_used} / ${usage.calls_limit} requests used today`}
                </p>
              )}
            </div>
            <ProviderBadge provider={provider} />
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4 min-h-0">
            {messages.length === 0 && (
              <div className="py-6">
                <p className="text-ink-faintest text-xs mb-4 text-center">
                  No messages yet. Try a suggested prompt or ask anything.
                </p>
                <div className="space-y-2">
                  {SUGGESTED_PROMPTS.map((p) => (
                    <button
                      key={p}
                      onClick={() => sendMessage(p)}
                      disabled={loading || quotaExhausted}
                      className="w-full text-left text-xs text-ink-faint border border-line rounded px-3 py-2.5 hover:border-line-strong hover:text-ink-dim disabled:opacity-40 transition-colors"
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
                <span className="text-xs text-ink-faintest px-1">
                  {msg.role === 'user' ? 'You' : 'Assistant'}
                </span>
                <div
                  className={`rounded-lg px-4 py-3 max-w-[94%] ${
                    msg.role === 'user'
                      ? 'bg-hud-accent/12 border border-hud-accent/20 text-sm text-ink-dim'
                      : 'bg-chip/50 border border-line-strong/40'
                  }`}
                >
                  {msg.role === 'assistant' ? (
                    <MessageContent content={msg.content} />
                  ) : (
                    <p className="text-sm text-ink-dim leading-relaxed whitespace-pre-wrap">
                      {msg.content}
                    </p>
                  )}
                </div>
              </div>
            ))}

            {loading && (
              <div className="flex items-start">
                <div className="rounded-lg px-4 py-3 bg-chip/50 border border-line-strong/40">
                  <div className="flex gap-1 items-center h-4">
                    {[0, 150, 300].map((delay) => (
                      <span
                        key={delay}
                        className="w-1.5 h-1.5 rounded-full bg-ink-faint animate-bounce"
                        style={{ animationDelay: `${delay}ms` }}
                      />
                    ))}
                  </div>
                </div>
              </div>
            )}

            {error && (
              <div className="rounded border border-red-200 bg-red-50 px-3 py-2.5 text-xs text-red-600 leading-relaxed">
                <strong>Error:</strong> {error}
                {errorIsNetwork && (
                  <>
                    <br />
                    <span className="text-red-600">
                      Is the backend running?{' '}
                      <code className="text-red-600">
                        cd backend &amp;&amp; uvicorn app.main:app --reload
                      </code>
                    </span>
                  </>
                )}
              </div>
            )}

            <div ref={chatEndRef} />
          </div>

          {/* Input */}
          <div className="px-4 pb-4 pt-3 border-t border-line shrink-0">
            {quotaExhausted && (
              <p className="mb-3 rounded border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-medium text-amber-900">
                Daily AI assistant limit reached. Your allowance resets tomorrow.
              </p>
            )}
            {responseLimitWarning && (
              <p className="mb-3 rounded border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-medium text-amber-900" role="status">
                {responseLimitWarning}
              </p>
            )}
            <div className="flex gap-2 items-end">
              <textarea
                rows={2}
                className="flex-1 rounded border border-line-strong bg-well px-3 py-2 text-sm text-ink-dim resize-none focus:outline-none focus:border-hud-accent/50 transition-colors leading-relaxed placeholder:text-ink-faintest"
                placeholder="Ask a question... (Enter to send, Shift+Enter for newline)"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                disabled={loading || quotaExhausted}
              />
              <button
                onClick={() => sendMessage(input)}
                disabled={loading || quotaExhausted || !input.trim()}
                className="rounded border border-hud-accent/30 bg-hud-accent/8 px-4 py-2 text-xs font-medium text-hud-accent hover:bg-hud-accent/12 focus:outline-none focus-visible:ring-2 focus-visible:ring-hud-accent/60 disabled:opacity-30 disabled:cursor-not-allowed transition-colors shrink-0 self-end"
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
                  setResponseLimitWarning(null)
                }}
                className="mt-2 text-xs text-ink-faintest hover:text-ink-faint transition-colors"
              >
                Clear conversation
              </button>
            )}
          </div>
        </div>

      </div>

      {/* ── CTA ─────────────────────────────────────────────────────────── */}
      <button
        type="button"
        onClick={() => onNavigate(3)}
        className="w-full text-left rounded-xl border border-hud-accent/20 bg-gradient-to-r from-hud-accent/6 to-white p-6 flex items-center justify-between gap-6 hover:border-hud-accent/40 hover:from-hud-accent/9 transition-colors cursor-pointer shadow-card focus:outline-none focus-visible:ring-2 focus-visible:ring-hud-accent/50"
      >
        <div>
          <p className="text-xs font-mono uppercase tracking-widest text-hud-accent mb-2">
            Next Step
          </p>
          <h3 className="text-ink font-semibold text-base mb-1.5">
            {nextMonth !== null
              ? `Run Month ${nextMonth} (${MONTH_LABELS[nextMonth - 1]})`
              : 'Review Your Final Results'}
          </h3>
          <p className="text-ink-faint text-sm max-w-lg">
            Head to <strong className="text-ink-dim">03 Simulation</strong> to run the
            next month and see how much revenue it earns. Come back here anytime between
            months to refine your code - completed months stay locked.
          </p>
        </div>
        <div className="shrink-0 flex items-center gap-2 rounded-lg border border-hud-gold bg-hud-gold px-4 py-2.5 text-ink text-xs font-semibold whitespace-nowrap">
          {nextMonth !== null ? `Run Month ${nextMonth}` : 'Review Results'}
          <span className="text-lg font-thin leading-none">{'->'}</span>
        </div>
      </button>

    </div>
  )
}
