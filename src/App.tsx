import { useCallback, useEffect, useRef, useState } from 'react'
import { useAuth } from './auth/AuthProvider'
import NavBar, { type Page } from './components/NavBar'
import type { ChatMessage } from './lib/api'
import { getOfficialSimulationSession } from './lib/api'
import IntroDataPage from './pages/IntroDataPage'
import LeaderboardPage from './pages/LeaderboardPage'
import PolicyAIPage, { POLICY_TEMPLATE } from './pages/PolicyAIPage'
import SimulationPage from './pages/SimulationPage'
import type { OfficialSimulationSession, PolicyParams } from './types/simulation'

type RestorationStatus = 'loading' | 'error' | 'loaded'

export default function App() {
  const { nickname } = useAuth()
  const [currentPage, setCurrentPage] = useState<Page>(1)
  const [policyCode, setPolicyCode] = useState(POLICY_TEMPLATE)
  const [policyParams, setPolicyParams] = useState<PolicyParams>({})
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [provider, setProvider] = useState<'azure' | 'mock' | undefined>(undefined)
  const [officialSession, setOfficialSession] = useState<OfficialSimulationSession | null>(null)
  const [restorationStatus, setRestorationStatus] = useState<RestorationStatus>('loading')
  const [restorationError, setRestorationError] = useState<string | null>(null)
  const initializedPolicyRef = useRef(false)

  const restoreOfficialSession = useCallback(async (
    options: { signal?: AbortSignal; showLoading?: boolean } = {},
  ): Promise<OfficialSimulationSession> => {
    if (options.showLoading !== false) setRestorationStatus('loading')
    setRestorationError(null)
    try {
      const restored = await getOfficialSimulationSession(options.signal)
      setOfficialSession(restored)
      if (!initializedPolicyRef.current) {
        initializedPolicyRef.current = true
        if (restored.latest_policy) {
          setPolicyCode(restored.latest_policy.policy_code)
          setPolicyParams(restored.latest_policy.params)
        }
      }
      setRestorationStatus('loaded')
      return restored
    } catch (error) {
      if (options.signal?.aborted) throw error
      setOfficialSession(null)
      setRestorationStatus('error')
      setRestorationError(
        error instanceof Error
          ? error.message
          : 'Official simulation state could not be restored.',
      )
      throw error
    }
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    void restoreOfficialSession({ signal: controller.signal }).catch(() => undefined)
    return () => controller.abort()
  }, [restoreOfficialSession])

  return (
    <div className="min-h-screen bg-paper text-ink">
      <NavBar currentPage={currentPage} onNavigate={setCurrentPage} />
      <main className="max-w-6xl mx-auto px-6 py-10">
        {restorationStatus === 'loading' && (
          <div className="rounded-xl border border-line bg-white p-10 text-center shadow-card" role="status">
            <p className="font-semibold text-ink">Restoring your official simulation…</p>
            <p className="mt-2 text-sm text-ink-faint">
              Progress and history are loading from the course database.
            </p>
          </div>
        )}

        {restorationStatus === 'error' && (
          <div className="rounded-xl border border-red-200 bg-white p-10 text-center shadow-card" role="alert">
            <p className="font-semibold text-red-700">Official simulation could not be restored.</p>
            <p className="mx-auto mt-2 max-w-xl text-sm text-ink-faint">
              {restorationError ?? 'Please try again. No local Month 1 fallback has been created.'}
            </p>
            <button
              type="button"
              onClick={() => void restoreOfficialSession().catch(() => undefined)}
              className="mt-5 rounded border border-hud-accent bg-hud-accent px-4 py-2 text-xs font-semibold text-white"
            >
              Retry restoration
            </button>
          </div>
        )}

        {restorationStatus === 'loaded' && officialSession && (
          <>
            {currentPage === 1 && <IntroDataPage onNavigate={setCurrentPage} />}
            {currentPage === 2 && (
              <PolicyAIPage
                policyCode={policyCode}
                onPolicyCodeChange={setPolicyCode}
                policyParams={policyParams}
                onPolicyParamsChange={setPolicyParams}
                messages={messages}
                onMessagesChange={setMessages}
                provider={provider}
                onProviderChange={setProvider}
                onNavigate={setCurrentPage}
                session={officialSession}
              />
            )}
            {currentPage === 3 && (
              <SimulationPage
                policyCode={policyCode}
                policyParams={policyParams}
                session={officialSession}
                onSessionChange={setOfficialSession}
                onRestoreSession={() => restoreOfficialSession({ showLoading: false })}
                onNavigate={setCurrentPage}
              />
            )}
            {currentPage === 4 && (
              <LeaderboardPage nickname={nickname ?? 'Student'} session={officialSession} />
            )}
          </>
        )}
      </main>
    </div>
  )
}
