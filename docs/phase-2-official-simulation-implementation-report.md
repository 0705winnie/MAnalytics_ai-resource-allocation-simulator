# Phase 2 Official Simulation Backend Implementation Report

## A. Files changed

Phase 2 added:

- `backend/app/routers/official_simulation.py`
- `backend/app/schemas/simulation_sessions.py`
- `backend/app/services/simulation_persistence.py`
- `backend/tests/test_official_simulation.py`

Phase 2 modified:

- `backend/app/main.py` — registers the official simulation router at `/api`; the existing optional legacy-proxy registration follows the application's current routing convention.

The other modified/untracked backend files visible in the worktree are the already-approved Phase 0/1 persistence foundation. No frontend file was changed. No `0005` migration was created. Existing stateless simulation routes and `/api/submissions` were not changed or removed.

## B. `GET /api/simulation/session` behavior

The new authenticated student endpoint:

- requires the existing student authentication dependency;
- derives the active enrollment from `AuthContext` and accepts no client-selected user, course, enrollment, or session ID;
- loads the enrollment's single `SimulationSession`;
- treats a missing session or inconsistent persisted progress as an internal data-integrity problem instead of lazily creating a session;
- restores monthly results ordered by month;
- derives `completed_months`, `next_month`, and status (`not_started`, `in_progress`, or `completed`) from persisted state;
- derives cumulative metrics exclusively from persisted monthly rows;
- returns the latest executed policy snapshot, or `null` when no month has run.

At 12 completed months, `next_month` is `null` and status is `completed`.

## C. `POST /api/simulation/session/months/next` behavior

The endpoint accepts only:

```json
{
  "expected_month": 5,
  "idempotency_key": "<UUID>",
  "policy_code": "...",
  "params": {}
}
```

Unknown fields are forbidden. The request therefore cannot supply an authoritative month, `previous_months`, seed, cumulative/result payload, course ID, enrollment ID, or session ID.

For a fresh valid request, the backend:

1. resolves the authenticated student's enrollment;
2. locks the corresponding session;
3. derives the actual next month from `completed_months + 1`;
4. reconstructs prior history from persisted rows;
5. compiles and validates the submitted policy;
6. calls the simulation engine's `simulate_month` service directly;
7. calculates the existing baseline-policy comparisons;
8. persists the official monthly policy and result snapshot;
9. advances the session exactly one month;
10. commits and returns the complete persisted session representation.

A fresh execution returns HTTP 201 with `replayed: false`. It does not call the stateless HTTP endpoint or create a legacy submission.

## D. Transaction and row-lock behavior

Authentication resolution, `SELECT ... FOR UPDATE`, result insertion, session advancement, flush, and commit use the same SQLAlchemy session/transaction.

The row lock serializes requests for one simulation session. If two requests assert the same `expected_month` with different idempotency keys, the second waits. After the first commits, the second observes the advanced `completed_months` and receives HTTP 409; it cannot silently run the following month.

Policy compilation, simulation, insert/constraint, flush, and commit failures all roll back the transaction. A failed request therefore leaves neither a monthly row nor a session increment.

## E. Idempotency implementation

Before checking the next month, the locked transaction queries the unique `(session_id, idempotency_key)` identity.

- Same key, same `expected_month`, same exact policy source, and same canonical parameter identity: returns the persisted result/session without executing again, HTTP 200, `replayed: true`.
- Same key with a different expected month, source, or parameters: returns structured HTTP 409 with code `idempotency_key_conflict`; no write occurs.

The replay comparison uses the same canonical hashing/canonical-parameter helpers used by new execution.

## F. `previous_months` reconstruction behavior

The browser is not authoritative for history. The service loads official rows ordered by month and reconstructs only the public history shape already supplied by `run_full_simulation`:

- `month`
- `requests_received`
- `requests_processed`
- `requests_rejected`
- `total_revenue`
- `unfinished_requests`
- `unfinished_value`
- `avg_utilization`
- `peak_utilization`

It does not pass SQLAlchemy objects, policy source/parameters/hash, idempotency keys, database IDs, type detail, benchmark detail, warnings, or remaining/internal fields to policy history. Tests verify that Month 2 receives only the persisted public summary of Month 1.

## G. Policy hash canonicalization

The exact policy source is preserved as the executed snapshot; it is not whitespace-normalized.

Parameters are canonicalized by:

- validating values as finite numbers;
- converting numeric values to the request model's normalized floating-point representation;
- serializing JSON with sorted keys, compact separators, UTF-8, and non-finite values disabled.

The SHA-256 input uses length-prefixed UTF-8 bytes for the exact policy source and for canonical parameter JSON, avoiding ambiguous concatenation boundaries. Parameter key order therefore does not change the hash, while any exact source change does.

## H. Response schemas and Decimal serialization

GET and POST share one session-response builder. POST wraps that representation with `replayed` and `executed_month`; GET returns the session representation directly.

The owning student receives official monthly aggregates plus their own `policy_code`, `params`, and `policy_hash`, which Phase 3 needs for history/editor restoration. Database-only IDs, enrollment/session foreign keys, idempotency keys, and other internal fields are omitted from monthly API rows.

Persisted `NUMERIC(18,2)` values are accumulated as `Decimal` on the server and deliberately serialized as JSON numbers at the API boundary. The focused tests verify this behavior.

## I. Error handling

- HTTP 400: policy compilation, validation, or safe policy-execution errors (`invalid_policy`).
- HTTP 401: missing/invalid authenticated session, through existing auth behavior.
- HTTP 403: authenticated account is not eligible as a student, through existing role enforcement.
- HTTP 409: conflicting idempotency reuse (`idempotency_key_conflict`), completed session (`session_completed`), or wrong/stale expected month (`wrong_expected_month`).
- HTTP 422: request-schema failure, including forbidden authority fields or invalid/non-finite parameters.
- HTTP 500: missing/inconsistent official session state or unexpected database/backend failure (`official_simulation_unavailable`) after rollback.

Unexpected exceptions and integrity problems are logged server-side. Client errors do not expose SQL, database URLs, secrets, or raw tracebacks.

## J. Tests run and exact pass/fail summary

Protected disposable local PostgreSQL was used at `127.0.0.1:55432` with a dedicated test database. Production Neon was not contacted.

Focused Phase 2 suite, final run:

```text
22 passed, 1 warning in 2.27s
```

Coverage includes:

- zero-, partial-, and 12-month restoration;
- ordered rows, cumulative derivation, and latest policy;
- Month 1 ownership and persistence;
- a real-engine official Month 1 execution with baseline comparisons;
- sequential persisted history and separate policy snapshots;
- skip, rerun, wrong month, and Month 13 rejection;
- successful replay and both idempotency-conflict forms;
- actual PostgreSQL concurrent row-lock behavior;
- compile, simulation, constraint, and commit rollback paths;
- authentication, role enforcement, forbidden authority fields, missing session integrity handling, and cross-student policy privacy;
- policy-hash stability/source identity and Decimal JSON serialization.

Alembic/static verification:

```text
alembic heads: 0004_simulation_persistence (head)
alembic check: No new upgrade operations detected.
python compile checks: passed
git diff --check: passed
```

Alembic emitted only the existing computed-column warnings concerning course code/nickname metadata; it reported no pending upgrade operation.

## K. Full backend regression result

The final complete backend suite after the Phase 2 implementation passed:

```text
371 passed, 4 warnings in 36.55s
```

The warnings were limited to existing test/dependency notices: Starlette TestClient/httpx deprecation, one test-only JWT SHA-384 key-length recommendation, and Alembic computed-column metadata warnings. There were no test failures.

## L. Phase 3 integration notes

- Restore state with `GET /api/simulation/session`; do not infer completed progress from browser storage.
- Run one official month with `POST /api/simulation/session/months/next`; do not send `month`, prior history, a seed, IDs, or simulated/cumulative results.
- Generate one idempotency UUID per user action and preserve it when retrying an uncertain/lost response. A genuinely new action must receive a new UUID.
- Set `expected_month` from the most recently restored server session. A 409 should trigger restoration/reconciliation, not an automatic attempt to execute another month.
- Replace the client session view from the full returned representation after each success/replay; do not append optimistically.
- GET returns the session object directly. POST returns `{ replayed, executed_month, session }`.
- Monetary fields are JSON numbers.
- The owning-student schema includes private policy snapshots. Instructor Progress and future leaderboard endpoints must use separate response schemas that exclude policy source, parameters, and hash.
- The old stateless routes and Submit Result path remain unchanged for now. Phase 3 should switch the UI deliberately and remove the legacy Submit Result call only within its approved scope.
- No frontend, Instructor Progress, leaderboard, localStorage, or mock-data behavior was changed in this phase.
- No production database operation, deployment, commit, or push was performed.

There were no implementation deviations from the approved Phase 2 scope.
