// Phase 1 local prototype profile/history persistence — localStorage only.
//
// `currentUser` is not authentication and must never be treated as the signed-in
// Student. AuthProvider owns server-backed identity. This local identifier is
// retained temporarily for prototype History/Leaderboard rows, while
// `submissionHistory` remains a browser-only log of saved simulation runs.

import type { PolicyParams, SimulationResponse } from '../types/simulation'
import type { CurrentUser, Submission } from '../types/user'

const CURRENT_USER_KEY = 'currentUser'
const SUBMISSION_HISTORY_KEY = 'submissionHistory'

const ADJECTIVES = ['Quiet', 'Swift', 'Bold', 'Calm', 'Sharp', 'Bright', 'Steady', 'Keen']
const NOUNS = ['Falcon', 'Otter', 'Cluster', 'Harbor', 'Comet', 'Ridge', 'Beacon', 'Atlas']

function generateAnonymousName(): string {
  const adj = ADJECTIVES[Math.floor(Math.random() * ADJECTIVES.length)]
  const noun = NOUNS[Math.floor(Math.random() * NOUNS.length)]
  const num = Math.floor(Math.random() * 90) + 10
  return `${adj} ${noun} ${num}`
}

function generateId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return `id_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`
}

export function getOrCreateCurrentUser(): CurrentUser {
  try {
    const raw = localStorage.getItem(CURRENT_USER_KEY)
    if (raw) return JSON.parse(raw) as CurrentUser
  } catch {
    // Corrupt or unavailable storage (e.g. private browsing) — fall through
    // and hand back a fresh in-memory user for this session.
  }

  const user: CurrentUser = {
    userId: generateId(),
    anonymousName: generateAnonymousName(),
    createdAt: new Date().toISOString(),
  }

  try {
    localStorage.setItem(CURRENT_USER_KEY, JSON.stringify(user))
  } catch {
    // Storage unavailable — user still works for this session, just won't persist.
  }

  return user
}

export function loadSubmissionHistory(): Submission[] {
  try {
    const raw = localStorage.getItem(SUBMISSION_HISTORY_KEY)
    if (raw) return JSON.parse(raw) as Submission[]
  } catch {
    // Corrupt or unavailable storage — start from an empty history.
  }
  return []
}

export function saveSubmissionHistory(history: Submission[]): void {
  try {
    localStorage.setItem(SUBMISSION_HISTORY_KEY, JSON.stringify(history))
  } catch {
    // Storage unavailable — history stays in-memory only for this session.
  }
}

export function createSubmission(
  policyCode: string,
  params: PolicyParams,
  response: SimulationResponse,
): Submission {
  return {
    ...response,
    id: generateId(),
    timestamp: new Date().toISOString(),
    policyCodeSnapshot: policyCode,
    params,
  }
}
