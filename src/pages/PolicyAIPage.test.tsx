import { useState } from 'react'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { ChatMessage } from '../lib/api'
import { officialSession } from '../test/fixtures'
import PolicyAIPage from './PolicyAIPage'

const postChat = vi.fn()
const getAIUsage = vi.fn()

vi.mock('../lib/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../lib/api')>()
  return {
    ...actual,
    postChat: (...args: unknown[]) => postChat(...args),
    getAIUsage: (...args: unknown[]) => getAIUsage(...args),
  }
})

const POLICY = 'def admission_policy(request, state, history, params):\n    return 0'

function Harness() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [provider, setProvider] = useState<'azure' | undefined>()
  return (
    <PolicyAIPage
      policyCode={POLICY}
      onPolicyCodeChange={() => undefined}
      policyParams={{ threshold: 4 }}
      onPolicyParamsChange={() => undefined}
      messages={messages}
      onMessagesChange={setMessages}
      provider={provider}
      onProviderChange={setProvider}
      onNavigate={() => undefined}
      session={officialSession(2)}
    />
  )
}

describe('PolicyAIPage real-provider entry points', () => {
  beforeEach(() => {
    postChat.mockReset()
    getAIUsage.mockReset()
    getAIUsage.mockResolvedValue({
      calls_used: 0,
      calls_limit: 50,
      resets_at: '2026-08-12T00:00:00-07:00',
      metered: true,
    })
    postChat.mockResolvedValue({
      content: 'real provider response',
      provider: 'azure',
      usage: {
        calls_used: 1,
        calls_limit: 50,
        resets_at: '2026-08-12T00:00:00-07:00',
        metered: true,
      },
    })
  })

  afterEach(() => cleanup())

  it.each([
    'How should I handle VIP vs. Economy requests differently?',
    'What is a good threshold for rejecting Economy jobs?',
    'My policy rejects too many VIPs — how do I fix it?',
    'Help me write a type-priority routing rule in Python.',
  ])('sends suggested prompt through the same postChat contract: %s', async (prompt) => {
    render(<Harness />)

    await userEvent.click(screen.getByRole('button', { name: prompt }))

    await waitFor(() => expect(postChat).toHaveBeenCalledTimes(1))
    expect(postChat).toHaveBeenCalledWith({
      message: prompt,
      history: [],
      draft_policy_code: POLICY,
      draft_params: { threshold: 4 },
    })
    expect(await screen.findByText('real provider response')).toBeTruthy()
  })

  it('keeps Clear Conversation browser-session behavior', async () => {
    render(<Harness />)
    await userEvent.click(screen.getByRole('button', {
      name: 'Help me write a type-priority routing rule in Python.',
    }))
    expect(await screen.findByText('real provider response')).toBeTruthy()

    await userEvent.click(screen.getByRole('button', { name: 'Clear conversation' }))

    expect(screen.queryByText('real provider response')).toBeNull()
    expect(screen.getByText('No messages yet. Try a suggested prompt or ask anything.')).toBeTruthy()
  })
})
