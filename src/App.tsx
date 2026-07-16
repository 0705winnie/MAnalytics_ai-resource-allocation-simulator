import { useState } from 'react'
import NavBar, { type Page } from './components/NavBar'
import IntroDataPage from './pages/IntroDataPage'
import PolicyAIPage, { POLICY_TEMPLATE } from './pages/PolicyAIPage'
import SimulationPage from './pages/SimulationPage'
import LeaderboardPage from './pages/LeaderboardPage'
import type { ChatMessage } from './lib/api'
import { getOrCreateCurrentUser, loadSubmissionHistory, saveSubmissionHistory } from './lib/storage'
import type { MonthDetailResult, PolicyParams } from './types/simulation'
import type { CurrentUser, Submission } from './types/user'

export default function App() {
  const [currentPage, setCurrentPage] = useState<Page>(1)

  // Shared across Page 2 (Policy & AI) and Page 3 (Simulation) so switching
  // back and forth never loses the student's work — lifted here because
  // both pages unmount when the other tab is active.
  const [policyCode, setPolicyCode] = useState(POLICY_TEMPLATE)
  const [policyParams, setPolicyParams] = useState<PolicyParams>({})
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [provider, setProvider] = useState<'azure' | 'mock' | undefined>(undefined)

  // The month-by-month simulation session: completed months in order
  // (index 0 = month 1). Lifted here for the same reason as policyCode/
  // policyParams — both Page 2 (shows "next month" + latest result) and
  // Page 3 (runs months, shows cumulative results) need it, and it must
  // survive switching between them.
  const [completedMonths, setCompletedMonths] = useState<MonthDetailResult[]>([])

  function handleMonthCompleted(result: MonthDetailResult) {
    setCompletedMonths((prev) => [...prev, result])
  }

  function handleResetSession() {
    setCompletedMonths([])
  }

  // Phase 1 simulated account (see src/lib/storage.ts) — persisted to
  // localStorage, not a real backend. currentUser is created once and never
  // changes within a browser; submissionHistory is a personal log of saved
  // simulation runs, newest first.
  const [currentUser] = useState<CurrentUser>(() => getOrCreateCurrentUser())
  const [submissionHistory, setSubmissionHistory] = useState<Submission[]>(() => loadSubmissionHistory())

  function handleSaveSubmission(submission: Submission) {
    setSubmissionHistory((prev) => {
      const next = [submission, ...prev]
      saveSubmissionHistory(next)
      return next
    })
  }

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      <NavBar currentPage={currentPage} onNavigate={setCurrentPage} />
      <main className="max-w-6xl mx-auto px-6 py-10">
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
            completedMonths={completedMonths}
          />
        )}
        {currentPage === 3 && (
          <SimulationPage
            policyCode={policyCode}
            policyParams={policyParams}
            completedMonths={completedMonths}
            onMonthCompleted={handleMonthCompleted}
            onResetSession={handleResetSession}
            onSaveSubmission={handleSaveSubmission}
            onNavigate={setCurrentPage}
          />
        )}
        {currentPage === 4 && (
          <LeaderboardPage currentUser={currentUser} submissionHistory={submissionHistory} />
        )}
      </main>
    </div>
  )
}
