// Shared types for the Phase 1 simulated-account / personal-history feature.
// See src/lib/storage.ts for how these are persisted (localStorage only —
// no backend, no real auth).

import type { PolicyParams, SimulationResponse } from './simulation'

export interface CurrentUser {
  userId: string
  anonymousName: string
  createdAt: string // ISO timestamp
}

// A single saved simulation run: the full backend response plus enough
// metadata to show it in a history list. Extends SimulationResponse rather
// than re-declaring its fields so this can never drift from what Page 3
// actually receives.
export interface Submission extends SimulationResponse {
  id: string
  timestamp: string // ISO timestamp
  policyCodeSnapshot: string
  params: PolicyParams
}
