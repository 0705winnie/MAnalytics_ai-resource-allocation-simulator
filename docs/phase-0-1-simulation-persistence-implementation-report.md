# Phase 0-1 Simulation Persistence Implementation Report

Scope: approved Phase 0 and Phase 1 only. No Phase 2 endpoints, frontend behavior, Instructor Progress changes, leaderboard logic, legacy deletion, production migration, commit, or push were performed.

All destructive migration tests used only the local disposable PostgreSQL database `resource_allocation_test` on `127.0.0.1:55432`. No production Neon connection was used.

## A. Files changed

### New migrations

- `backend/alembic/versions/0003_months_completed.py`
- `backend/alembic/versions/0004_simulation_persistence.py`

### New models

- `backend/app/models/simulation_session.py`
- `backend/app/models/monthly_result.py`

### Updated backend implementation

- `backend/app/models/__init__.py`
- `backend/app/models/enrollment.py`
- `backend/app/models/submission.py`
- `backend/app/services/roster_imports.py`

### Updated tests

- `backend/tests/test_migrations.py`
- `backend/tests/test_account_models.py`
- `backend/tests/test_instructor_roster.py`

### Report

- `docs/phase-0-1-simulation-persistence-implementation-report.md`

No frontend files were changed.

## B. Reconstructed 0003 behavior

`0003_months_completed` has:

```python
revision = "0003_months_completed"
down_revision = "0002_submissions"
```

Upgrade behavior:

1. Adds `submissions.months_completed` as nullable `INTEGER`.
2. Backfills every null legacy value to `12`.
3. Alters the column to `nullable=False`.
4. Leaves the column without a server default.

Downgrade drops only that column. The downgrade was exercised only on the protected disposable test database and must not be run against production.

The legacy `Submission` ORM model now declares `months_completed: Integer, nullable=False`, matching the confirmed production schema. No new submission business logic was added.

Because production Neon is already stamped at `0003_months_completed`, this reconstructed migration must not be run manually there. Its purpose is to restore the honest Alembic graph and support older/fresh databases.

## C. 0004 schema

`0004_simulation_persistence` has:

```python
revision = "0004_simulation_persistence"
down_revision = "0003_months_completed"
```

### `simulation_sessions`

Fields:

- `id UUID PRIMARY KEY`
- `enrollment_id UUID NOT NULL`
- FK to `enrollments.id` with `ON DELETE RESTRICT`
- `completed_months SMALLINT NOT NULL DEFAULT 0`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`
- `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()`
- `last_completed_at TIMESTAMPTZ NULL`

Constraints/indexes:

- `UNIQUE(enrollment_id)`
- `CHECK(completed_months BETWEEN 0 AND 12)`
- index on `completed_months`

It contains no status, reset, multi-session, or engine-version fields.

### `monthly_results`

Identity/policy fields:

- `id UUID PRIMARY KEY`
- `session_id UUID NOT NULL`
- FK to `simulation_sessions.id` with `ON DELETE RESTRICT`
- `month SMALLINT NOT NULL`
- `idempotency_key UUID NOT NULL`
- `policy_code TEXT NOT NULL`
- `policy_params JSONB NOT NULL`
- `policy_hash CHAR(64) NOT NULL`

Persisted monthly aggregates:

- request/admitted/completed/rejected counts
- `total_revenue NUMERIC(18,2)`
- unfinished count
- `unfinished_value NUMERIC(18,2)`
- average/peak utilization JSONB
- remaining capacity JSONB
- by-type breakdown JSONB
- warnings JSONB
- benchmark comparison JSONB
- `completed_at TIMESTAMPTZ NOT NULL DEFAULT now()`

Constraints:

- `UNIQUE(session_id, month)`
- `UNIQUE(session_id, idempotency_key)`
- Month 1-12
- Nonnegative counts and monetary values
- admitted does not exceed total
- completed does not exceed admitted
- rejected equals total minus admitted
- unfinished equals admitted minus completed, matching the current engine
- `policy_params` must be a JSON object

No database triggers were added.

The ORM uses `Decimal` for the two `NUMERIC(18,2)` values. Phase 2 schemas must serialize these safely as API JSON numbers.

## D. Existing-enrollment migration behavior

During 0004, the migration reads all existing enrollment IDs and inserts exactly one session per enrollment using generated UUIDs.

Every backfilled session has:

- `completed_months = 0`
- no completed timestamp
- zero monthly-result rows

The migration does not query legacy submission scores or `months_completed`. It does not infer progress and does not fabricate History.

Tests covered:

- a 0002 database with an existing submission;
- a production-shaped database already at 0003;
- preservation of the legacy row through 0004;
- one empty session for the existing enrollment;
- zero monthly results.

## E. Future-enrollment creation behavior

`import_roster()` now constructs:

```python
Enrollment(..., simulation_session=SimulationSession())
```

The roster route already calls `import_roster()` and commits once. Therefore user creation, enrollment creation, activation-code state, and the empty simulation session participate in the same transaction.

The one-to-one relationship and `UNIQUE(simulation_sessions.enrollment_id)` prevent competing sessions.

Tests verify:

- a successful roster import creates one 0-month session;
- one student enrolled in two courses receives one session per enrollment;
- an integrity failure rolls back user, enrollment, and session;
- a rendering failure before commit also rolls back all three;
- session `last_completed_at` starts null.

No normal lazy session-creation path was added.

## F. Tests run and exact pass/fail summary

### Successful protected-database runs

1. Migration scenarios:

   ```text
   11 passed, 2 warnings in 1.23s
   ```

2. Model and roster integration tests:

   ```text
   43 passed, 1 warning in 2.84s
   ```

3. Complete backend suite:

   ```text
   349 passed, 4 warnings in 35.33s
   ```

4. Strengthened roster rollback assertions rerun:

   ```text
   2 passed, 1 warning in 1.06s
   ```

5. Python compilation checks and `git diff --check` passed.

Warnings were non-failing:

- existing Alembic computed-column comparison warnings for normalized course code and nickname;
- Starlette TestClient/httpx deprecation warning;
- one test-only JWT key-length recommendation.

### Initial sandbox-only attempt

The first test invocation could not access local TCP and reported 6 failures plus 43 setup errors, all caused by:

```text
connection to 127.0.0.1:55432 failed: Operation not permitted
```

This was an execution-sandbox restriction, not a code/test assertion failure. The identical tests were rerun with approved local-network access and passed as listed above.

No unrelated pre-existing test failures remain in the completed backend run.

## G. Alembic heads/check results

`alembic heads`:

```text
0004_simulation_persistence (head)
```

There is exactly one head.

`alembic check` against the protected local test database:

```text
No new upgrade operations detected.
```

It emitted only the existing computed-column warnings and found no model/schema drift.

## H. Deviations from the approved architecture

No material deviations.

Implementation details consistent with the approved plan:

- monetary columns use exact `NUMERIC(18,2)`;
- timestamps use server `now()` defaults;
- Python UUID defaults are used by ORM inserts;
- migration backfill explicitly generates session UUIDs;
- no engine version, reset, status, trigger, endpoint, leaderboard, or frontend changes were introduced.

The current stateless simulation and legacy submission routes remain unchanged because retiring them is explicitly outside Phase 0/1.

## I. Phase 2 implementation notes

Before implementing:

- `GET /api/simulation/session`
- `POST /api/simulation/session/months/next`

Phase 2 should account for the following foundation behavior:

1. **Session existence:** 0004 backfills all existing enrollments and roster imports create future sessions transactionally. A missing session should be treated as a data-integrity problem, not as a normal student-controlled creation path.

2. **Row locking:** lock `SimulationSession` with `SELECT ... FOR UPDATE` before checking and advancing `completed_months`.

3. **Idempotency:** use the existing unique `(session_id, idempotency_key)` constraint. A replay lookup must occur before treating the request as an out-of-order new execution.

4. **Month uniqueness:** `(session_id, month)` is the final duplicate-execution guard.

5. **Official history:** load ordered `MonthlyResult` rows. When passing history to the current engine, construct the same public monthly shape used by `run_full_simulation`; do not send client-provided history or blindly pass policy snapshots/internal database fields.

6. **Money serialization:** SQLAlchemy returns `Decimal` for official revenue/value. Response schemas should consistently serialize them without losing the stored two-decimal value.

7. **Policy hashing:** Phase 2 must define one canonical source/params encoding and use it consistently for new execution and idempotent-replay comparison.

8. **Atomic update:** result insert, session increment, and `last_completed_at` update must share one transaction.

9. **Ordered relationship:** `SimulationSession.monthly_results` is configured in month order, but explicit query ordering is still preferable in endpoint/service queries.

10. **Legacy endpoint remains known-broken:** `Submission.months_completed` now honestly matches the non-default production column, while the legacy POST route still does not assign it. This phase intentionally did not add submission business logic. The approved later Student-flow phase must remove/retire that call rather than building new logic around submissions.

11. **No user-flow changes yet:** React state, localStorage, Submit Result, Save to My History, mock leaderboard, Instructor Progress, and existing simulation routes are untouched.
