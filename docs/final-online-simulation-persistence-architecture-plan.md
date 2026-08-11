# Final Online Simulation Persistence Architecture and Repair Plan

This is an implementation proposal only. No application code, migrations, Git history, or production data were changed while producing it.

## A. Current architecture audit

### React state is the current simulation authority

`src/App.tsx` initializes `completedMonths` as an empty React array. It controls the completed-month count, next month, locked months, cumulative charts, and the Policy page's current context. It disappears on refresh, logout, browser restart, browser change, or device change.

`src/pages/SimulationPage.tsx` calculates the next month as `completedMonths.length + 1`, then calls the backend with `month`, `policy_code`, `params`, and `previous_months`. The browser therefore currently chooses the requested month and supplies policy history.

### Simulation routes are stateless

`backend/app/routers/simulate.py` exposes:

- `POST /api/simulate`
- `POST /api/simulate/month`

Neither route requires student authentication, resolves an enrollment, persists results, owns sequencing, or restores an official session. The monthly route passes client-supplied `previous_months` directly to the engine.

### The existing engine has the correct monthly primitive

`backend/app/services/simulation_engine.py` provides:

- `simulate_month(...)`
- `run_full_simulation(...)`
- shared `_simulate_month_from_arrivals(...)`

`simulate_month()` already validates Month 1-12, derives deterministic arrivals from server-controlled `DEFAULT_SEED`, passes `history["previous_months"]` to policy code, and returns useful monthly aggregate fields. It should remain the official monthly calculation primitive; the algorithm does not need redesign.

### Submit Result is a separate and conflicting path

`backend/app/routers/submissions.py` currently authenticates the student, compiles the latest policy, calls `run_full_simulation()` for all 12 months, and inserts one legacy `Submission`. This does not persist the months the student actually ran and recomputes a different full-year result with the latest policy.

The button is in `src/pages/SimulationPage.tsx`; `src/lib/api.ts` calls `POST /api/submissions`.

### History is browser-local

`src/lib/storage.ts` defines:

- `currentUser`
- `submissionHistory`

"Save to My History" copies a client aggregate into localStorage. It is not tied to the authenticated enrollment or PostgreSQL. Official progress is not in sessionStorage either; it is React-only.

### Instructor Progress uses legacy submissions

`backend/app/routers/instructor_progress.py` loads `Submission` rows and computes submission count, latest result, best result, and last submission timestamp. The matching schema and `src/instructor/InstructorStudentProgress.tsx` expose the same submission-oriented fields.

The instructor therefore reads a different result path from the student simulation UI.

### Leaderboard is mock/local

`src/pages/LeaderboardPage.tsx` contains:

- `MOCK_CLASSMATES`
- `MOCK_PAST_SUBMISSIONS`
- generated browser-local identity
- local `submissionHistory`
- `bestRunRevenue`
- client-side descending sorting
- local prototype profile messaging

It is neither course-scoped nor based on authenticated enrollment nicknames.

## B. Proposed final architecture

```text
Authenticated student
        |
        v
AuthContext.enrollment
        |
        v
simulation_sessions
one row per enrollment
        |
        v
monthly_results
immutable Months 1 through N
        |
        +-- Student restoration
        +-- Simulation History
        +-- Student cumulative result
        +-- Instructor Progress
        +-- Same-Stage Leaderboard
        +-- Final Leaderboard
```

Core rules:

- PostgreSQL is the single official source of truth.
- Every enrollment has exactly one session.
- Every successful month creates one immutable monthly row.
- `completed_months` advances in the same transaction.
- The backend calculates the next month.
- The backend reconstructs `previous_months`.
- There is no Submit or Reset workflow.
- Students and instructors aggregate the same rows.
- Leaderboard queries never expose policy data.
- Existing enrollments receive empty sessions in 0004.
- Future enrollment creation creates its session transactionally.

## C. Database model proposal

### `simulation_sessions`

| Field | Type | Rule |
|---|---|---|
| `id` | UUID | Primary key |
| `enrollment_id` | UUID | Non-null FK and unique |
| `completed_months` | SMALLINT | Non-null, server default 0 |
| `created_at` | TIMESTAMPTZ | Non-null server timestamp |
| `updated_at` | TIMESTAMPTZ | Non-null server timestamp |
| `last_completed_at` | TIMESTAMPTZ nullable | Latest committed month |

Do not add a redundant status column, reset counters, multiple-session flags, or engine-version fields.

Status is derived:

- 0: `not_started`
- 1-11: `in_progress`
- 12: `completed`

Cumulative metrics should be derived from at most 12 monthly rows. This avoids denormalized totals drifting from official monthly data.

### `monthly_results`

| Field | Type | Purpose |
|---|---|---|
| `id` | UUID | Primary key |
| `session_id` | UUID | Non-null FK |
| `month` | SMALLINT | Official month 1-12 |
| `idempotency_key` | UUID | Non-null retry identity |
| `policy_code` | TEXT | Exact executed source |
| `policy_params` | JSONB | Exact parameter snapshot |
| `policy_hash` | CHAR(64) | SHA-256 of canonical source and params |
| `total_requests` | INTEGER | Existing monthly field |
| `admitted_requests` | INTEGER | Existing monthly field |
| `completed_requests` | INTEGER | Existing monthly field |
| `rejected_requests` | INTEGER | Existing monthly field |
| `total_revenue` | NUMERIC(18,2) | Official monthly payoff |
| `unfinished_requests` | INTEGER | Existing monthly field |
| `unfinished_value` | NUMERIC(18,2) | Existing monthly field |
| `avg_utilization` | JSONB | Cluster-keyed aggregate |
| `peak_utilization` | JSONB | Cluster-keyed aggregate |
| `remaining_capacity` | JSONB | Cluster-keyed aggregate |
| `by_type` | JSONB | Small existing type breakdown |
| `warnings` | JSONB | Existing warning strings |
| `benchmark_comparison` | JSONB | Existing bounded comparison data |
| `completed_at` | TIMESTAMPTZ | Non-null server timestamp |

`NUMERIC(18,2)` is preferable for official monetary values because the engine already rounds to two decimals and leaderboard ties require exact equality. API responses may still serialize them as JSON numbers.

Do not persist every arrival, every job, raw capacity events, RNG state, compiled policy objects, or engine snapshots.

### Policy snapshots

A `policy_versions` table is not needed. Each immutable month is already one policy execution record. Store exact source, exact params, and a canonical SHA-256 hash directly on the monthly row.

## D. Constraints and indexes

### Session constraints

- Primary key on `simulation_sessions.id`.
- FK `enrollment_id -> enrollments.id` with `ON DELETE RESTRICT`.
- `UNIQUE (enrollment_id)`.
- `CHECK (completed_months BETWEEN 0 AND 12)`.

### Monthly-result constraints

- Primary key on `monthly_results.id`.
- FK `session_id -> simulation_sessions.id` with `ON DELETE RESTRICT`.
- `UNIQUE (session_id, month)`.
- `UNIQUE (session_id, idempotency_key)`.
- `CHECK (month BETWEEN 1 AND 12)`.
- Nonnegative request counts and monetary values.
- `admitted_requests <= total_requests`.
- `completed_requests <= admitted_requests`.
- `rejected_requests = total_requests - admitted_requests`.
- If the engine invariant remains exact, `unfinished_requests = admitted_requests - completed_requests`.
- `jsonb_typeof(policy_params) = 'object'`.

### Indexes

- Unique session enrollment index.
- Index on `simulation_sessions.completed_months`.
- Unique `(session_id, month)` index for duplicate protection and ordered history.
- Existing enrollment uniqueness on `(course_id, user_id)` supports course joins.

The application transaction enforces that monthly rows are exactly Months 1 through `completed_months`. A database trigger is unnecessary.

## E. Official month-run endpoint

### Route and authentication

```http
POST /api/simulation/session/months/next
```

Require `require_student`. Derive user, course, enrollment, and session from `AuthContext`. Do not accept client-provided course, enrollment, or session identifiers.

### Request

```json
{
  "expected_month": 5,
  "idempotency_key": "22db6736-6c41-4f65-a742-ab87599df26c",
  "policy_code": "def admission_policy(...): ...",
  "params": {
    "threshold": 0.75
  }
}
```

Do not accept authoritative `month`, `previous_months`, seed, cumulative values, results, or another session ID.

### Response

A new commit returns HTTP 201:

```json
{
  "replayed": false,
  "executed_month": 5,
  "session": {
    "session_id": "...",
    "completed_months": 5,
    "next_month": 6,
    "status": "in_progress",
    "cumulative": {},
    "monthly_results": [],
    "latest_policy": {}
  }
}
```

A safe replay returns HTTP 200 with `replayed=true` and the persisted state.

### Errors

| Status | Meaning |
|---|---|
| 400 | Policy validation, compilation, or safe execution error |
| 401 | Missing/invalid authentication cookie |
| 403 | Authenticated account is not an eligible student |
| 409 | Wrong expected month, complete session, stale concurrent request, or conflicting idempotency reuse |
| 422 | Invalid request shape, UUID, month range, or params |
| 500 | Unexpected calculation/database failure; transaction rolled back |

A 12/12 session always rejects further execution. There is no Month 13 or reset alternative.

## F. Transaction and concurrency design

1. Authenticate and resolve the enrollment.
2. Validate the request structure.
3. Begin the database transaction.
4. Load the single session with `SELECT ... FOR UPDATE`.
5. Check `(session_id, idempotency_key)`.
6. If it exists, compare expected month and policy hash:
   - a matching request returns the persisted result;
   - conflicting reuse returns 409.
7. Calculate `actual_next_month = completed_months + 1`.
8. Reject if the session is complete or `expected_month` differs.
9. Load previous official monthly rows in month order.
10. Construct `history["previous_months"]` server-side.
11. Compile and validate the policy.
12. Call `simulate_month(actual_next_month, ..., seed=DEFAULT_SEED, previous_months=database_history)`.
13. Insert the immutable monthly row.
14. Set session `completed_months` to the executed month.
15. Update timestamps.
16. Flush constraints.
17. Commit.
18. Build and return the complete persisted session.

### Double click/two tabs

If two requests both claim `expected_month=5`, the first commits Month 5. The second later obtains the lock, sees that Month 6 is next, and returns 409 rather than silently running Month 6.

### Lost-response retry

If Month 5 commits but the response is lost, retrying the same idempotency key finds and returns the persisted Month 5 result. It does not execute another month.

### Rollback

Policy, insert, flush, or commit failures leave no monthly row, no progress increment, and no activity timestamp update.

Holding one row lock during calculation is the simplest correctness-first design for twelve official executions per enrollment.

## G. Restoration endpoint

```http
GET /api/simulation/session
```

Require `require_student` and derive all scope from authentication.

Recommended response:

```json
{
  "session_id": "...",
  "completed_months": 4,
  "next_month": 5,
  "status": "in_progress",
  "cumulative": {
    "total_requests": 0,
    "admitted_requests": 0,
    "completed_requests": 0,
    "rejected_requests": 0,
    "total_revenue": 0.0,
    "unfinished_requests": 0,
    "unfinished_value": 0.0,
    "warnings_count": 0,
    "by_type": []
  },
  "monthly_results": [],
  "latest_policy": {
    "policy_code": "...",
    "params": {},
    "policy_hash": "..."
  }
}
```

At zero months, return `next_month=1`, `not_started`, empty results, zero cumulative values, and `latest_policy=null`. At 12 months return `next_month=null` and `completed`.

`src/App.tsx` should wait for authentication, call restoration, show loading until it resolves, initialize official state from the response, initialize the editor from the latest executed policy where appropriate, and never assume an empty official session before restoration.

## H. Simulation History design

Page 4 should contain three views:

1. Simulation History
2. Same-Stage Leaderboard
3. Final Leaderboard

History replaces Past Submissions, Save to My History, local submission statistics, and local snapshots. Every committed month appears automatically.

Recommended list columns:

- month
- completion timestamp
- revenue
- total/admitted/rejected requests
- completed/unfinished requests
- warnings count

Expandable detail may show utilization, remaining capacity, type breakdown, warning messages, benchmark comparison, and policy hash. Policy source remains private to the owning student.

## I. Same-Stage Leaderboard design

### Student API

```http
GET /api/leaderboards/same-stage
```

The backend derives the student's course and current stage. Eligible rows require:

- same course;
- active enrollment;
- active user account;
- nickname present;
- exact matching `completed_months` from 1 through 12.

At stage 0, return an unranked empty state indicating that Month 1 must be completed.

Student rows contain rank, nickname, completed months, cumulative revenue, last activity, and `is_current_user`. Never return username or policy data.

### Instructor API

```http
GET /api/instructor/courses/{course_id}/leaderboards/same-stage?stage=4
```

Require course ownership and Stage 1-12. Use the identical shared ranking logic and nickname-only identity.

## J. Final Leaderboard design

### Student API

```http
GET /api/leaderboards/final
```

Students may view it at any stage. Ranked rows require same course, active enrollment, active account, and 12/12. An incomplete student receives the rows but is marked ineligible/unranked.

### Instructor API

```http
GET /api/instructor/courses/{course_id}/leaderboards/final
```

Use the same shared ranking service and course ownership check. Committing Month 12 automatically makes a student eligible.

## K. Ranking query

The official metric is:

```sql
COALESCE(SUM(monthly_results.total_revenue), 0)
```

Conceptual query:

```sql
WITH eligible AS (
    SELECT
        e.id AS enrollment_id,
        e.nickname,
        s.completed_months,
        s.last_completed_at,
        COALESCE(SUM(m.total_revenue), 0) AS cumulative_revenue
    FROM enrollments e
    JOIN users u ON u.id = e.user_id
    JOIN simulation_sessions s ON s.enrollment_id = e.id
    JOIN monthly_results m ON m.session_id = s.id
    WHERE e.course_id = :course_id
      AND e.status = 'active'
      AND u.is_active = TRUE
      AND e.nickname IS NOT NULL
      AND s.completed_months = :stage
    GROUP BY e.id, e.nickname, s.completed_months, s.last_completed_at
)
SELECT
    RANK() OVER (ORDER BY cumulative_revenue DESC) AS rank,
    enrollment_id,
    nickname,
    completed_months,
    cumulative_revenue,
    last_completed_at
FROM eligible
ORDER BY rank ASC, lower(nickname) ASC, enrollment_id ASC;
```

For Final, use Stage 12. Nickname/ID ordering affects display only; equal revenue retains the same SQL rank.

## L. Anonymous nickname behavior

Current fake aliases originate in `src/lib/storage.ts` (`ADJECTIVES`, `NOUNS`, `getOrCreateCurrentUser`) and `MOCK_CLASSMATES` in `src/pages/LeaderboardPage.tsx`.

Remove them. All leaderboard identity comes from `enrollments.nickname`.

The API returns the stored nickname unchanged. The UI adds `(you)` from `is_current_user`; it is not stored. Berkeley usernames remain allowed only in authorized management views such as Instructor Progress and Roster Management.

## M. Instructor Progress redesign

Keep:

```http
GET /api/instructor/courses/{course_id}/progress
```

Replace the implementation with an owned-course query that includes every enrollment and left joins its session/monthly results. Do not exclude pending, disabled, or inactive students from Instructor Progress.

Recommended row:

```json
{
  "enrollment_id": "...",
  "berkeley_username": "student",
  "nickname": "kyra",
  "enrollment_status": "active",
  "user_is_active": true,
  "completed_months": 5,
  "cumulative_revenue": 12345.67,
  "last_activity": "...",
  "simulation_status": "in_progress",
  "warnings_count": 2
}
```

At zero months return 0 revenue, null activity, and `not_started`.

Remove submission count, latest result, best result, and last-submitted fields. The backend should reuse the same cumulative aggregation logic as restoration/ranking.

`src/instructor/InstructorStudentProgress.tsx` should show `N / 12`, cumulative revenue, last activity, enrollment/account status, and derived simulation status.

## N. Legacy submissions retirement

### Reconstruct 0003

Add during implementation:

```text
backend/alembic/versions/0003_months_completed.py
```

with:

```python
revision = "0003_months_completed"
down_revision = "0002_submissions"
```

Upgrade logic:

1. add `months_completed` nullable;
2. backfill existing rows to 12;
3. alter it to non-null;
4. leave no server default.

Add the field to the legacy ORM model while the table remains. Never run the downgrade in production.

### Preserve honest history

The permanent chain is:

```text
0001 -> 0002 -> 0003 -> 0004 -> later cleanup
```

Do not rewrite 0002, stamp production backward, downgrade production, fabricate monthly rows, or manually delete the four rows.

### Retirement sequence

After official persistence, Student flow, Instructor Progress, leaderboards, and smoke tests are proven, add a forward migration such as `0005_drop_legacy_submissions`.

That migration drops the legacy table and its four rows. The same application release removes the Submission model, schemas, router, relationships, router registration, and obsolete tests. Retain a Neon backup/branch through the agreed retention window.

## O. localStorage and mock cleanup

Remove from `src/lib/storage.ts`:

- `CURRENT_USER_KEY = 'currentUser'`
- `SUBMISSION_HISTORY_KEY = 'submissionHistory'`
- fake name generation
- `getOrCreateCurrentUser()`
- history load/save helpers
- local submission construction

Remove from `src/App.tsx`:

- `localPrototypeUser`
- `submissionHistory`
- `handleSaveSubmission`

Remove from `src/pages/SimulationPage.tsx`:

- Save to My History
- Submit Result
- local submission construction
- submit state/error handlers

Remove from `src/pages/LeaderboardPage.tsx`:

- mock classmates
- mock past submissions
- fake current-user score
- local best/average/latest calculations
- local profile messaging
- sample-data fallback

Remove obsolete local types from `src/types/user.ts` when unused.

Authentication remains in the HTTP-only cookie. A future policy draft localStorage key is acceptable only as a clearly non-authoritative unsaved draft.

## P. Migration plan

```text
0001_account_foundation
  -> 0002_submissions
  -> 0003_months_completed
  -> 0004_simulation_persistence
  -> 0005_drop_legacy_submissions
```

0004 should create both tables and all constraints/indexes, create exactly one empty 0-month session for every existing enrollment, and create no monthly results. It must not read progress from submissions.

Future roster imports create enrollment and session in one transaction. Missing sessions after 0004 are integrity errors, not a normal lazy path for creating competing sessions.

### Production-safe rollout

On a Neon branch/test database:

1. test base to latest;
2. test 0002 with legacy rows through 0003/0004;
3. test production-shaped 0003 to 0004;
4. prove session count equals enrollment count;
5. prove all sessions start at 0;
6. prove monthly-result count is zero;
7. prove four submissions remain unchanged;
8. run `alembic check`;
9. run application tests.

Production initially upgrades only through 0004. Apply 0005 only after the new system has passed its proof period and a recoverable backup/branch exists.

## Q. Incremental implementation phases

### Phase 0 - Restore migration graph

- Reconstruct 0003.
- Update the legacy model.
- Correct migration head tests.
- Test clean, 0002-shaped, and production-shaped 0003 databases.

### Phase 1 - Add official persistence schema

- Add 0004.
- Add session/month models and relationships.
- Backfill one empty session per enrollment.
- Create future sessions transactionally with roster enrollment creation.

### Phase 2 - Official backend flow

- Add restoration.
- Add authenticated run-next-month.
- Build policy history server-side.
- Add row locking, expected-month validation, and idempotency.
- Add shared session/cumulative query services.

### Phase 3 - Student persistence switch

- Initialize App from restoration.
- Run months through the official endpoint.
- Remove authoritative client month/history input.
- Remove Submit Result and Save to My History.
- Convert Page 4 to History, Same-Stage, and Final tabs.

Phases 2 and 3 should deploy together.

### Phase 4 - Instructor Progress

- Replace submission queries.
- Show all enrollments, including inactive and zero-month students.
- Prove cumulative equality with Student UI.

### Phase 5 - Shared leaderboards

- Add one ranking service.
- Add Student and Instructor Same-Stage/Final APIs.
- Add the Instructor Leaderboards section.
- Use nickname-only identity and SQL `RANK()`.

### Phase 6 - Remove mock/local authority

- Delete fake aliases and mock rows.
- Remove obsolete localStorage keys/types.
- Retire stateless routes from the normal student flow.

### Phase 7 - Remove legacy submissions

- Deploy 0005 after proof.
- Drop the table/data.
- Remove model/schema/router/relationships and legacy tests.

### Phase 8 - Production smoke testing

- Cross-browser/device restoration.
- Two students and two courses.
- Inactive exclusion.
- Instructor equality.
- Concurrent execution.
- Month 12 Final eligibility.
- No Submit or Reset path.

## R. Exact files likely to change

### Phase 0

- `backend/alembic/versions/0003_months_completed.py` - new
- `backend/app/models/submission.py`
- `backend/tests/test_migrations.py`
- `backend/tests/test_submissions.py` - new or equivalent

### Phase 1

- `backend/alembic/versions/0004_simulation_persistence.py` - new
- `backend/app/models/simulation_session.py` - new
- `backend/app/models/monthly_result.py` - new
- `backend/app/models/enrollment.py`
- `backend/app/models/__init__.py`
- `backend/app/services/roster_imports.py`
- `backend/tests/test_account_models.py`
- `backend/tests/test_instructor_roster.py`
- `backend/tests/test_migrations.py`

### Phase 2

- `backend/app/schemas/simulation_sessions.py` - new
- `backend/app/routers/official_simulation.py` - new
- `backend/app/services/simulation_persistence.py` - new
- `backend/app/main.py`
- `backend/app/routers/simulate.py`
- `backend/tests/test_official_simulation.py` - new
- `backend/tests/test_simulate_month.py`
- `backend/tests/test_simulate_month_api.py`

`backend/app/services/simulation_engine.py` should retain its calculation behavior.

### Phase 3

- `src/App.tsx`
- `src/pages/PolicyAIPage.tsx`
- `src/pages/SimulationPage.tsx`
- `src/pages/LeaderboardPage.tsx`
- `src/components/NavBar.tsx`
- `src/lib/api.ts`
- `src/types/simulation.ts`
- `backend/app/routers/submissions.py`
- frontend API/component tests

### Phase 4

- `backend/app/routers/instructor_progress.py`
- `backend/app/schemas/instructor_progress.py`
- `src/instructor/InstructorStudentProgress.tsx`
- `src/instructor/api.ts`
- `src/instructor/types.ts`
- `backend/tests/test_instructor_progress.py` - new

### Phase 5

- `backend/app/services/leaderboards.py` - new
- `backend/app/routers/leaderboards.py` - new
- `backend/app/schemas/leaderboards.py` - new
- `backend/app/main.py`
- `backend/tests/test_leaderboards.py` - new
- `src/instructor/InstructorLeaderboards.tsx` - new
- `src/instructor/CourseSectionNavigation.tsx`
- `src/pages/InstructorCourseDetailPage.tsx`
- `src/instructor/api.ts`
- `src/instructor/types.ts`
- `src/pages/LeaderboardPage.tsx`
- `src/lib/api.ts`
- `src/types/simulation.ts`

### Phase 6

- `src/lib/storage.ts` - remove if nothing non-authoritative remains
- `src/types/user.ts` - remove when unused
- `src/App.tsx`
- `src/pages/LeaderboardPage.tsx`
- `backend/app/main.py`
- `backend/app/routers/simulate.py`, if public stateless routes are removed completely

### Phase 7

- `backend/alembic/versions/0005_drop_legacy_submissions.py` - new
- `backend/app/models/submission.py` - delete
- `backend/app/schemas/submissions.py` - delete
- `backend/app/routers/submissions.py` - delete
- `backend/app/models/enrollment.py`
- `backend/app/models/__init__.py`
- `backend/app/main.py`
- legacy submission and Instructor Progress tests

## S. Test plan

### Migrations

- Fresh database upgrades to latest.
- 0002 with submission rows upgrades through reconstructed 0003.
- Production-shaped 0003 upgrades to 0004 without rerunning 0003.
- Every existing enrollment receives exactly one empty session.
- No legacy monthly results are fabricated.
- Four legacy rows remain unchanged before 0005.
- 0005 removes only legacy submissions.
- New persistence remains intact after 0005.
- `alembic check` reports no drift.

### Official progression

- Month 1 creates one official row.
- Months 1-12 execute sequentially.
- A completed month cannot rerun.
- A future month cannot be skipped.
- Month 13 cannot execute.
- No reset endpoint/UI exists.
- One session exists per enrollment.
- Different policy snapshots remain attached to their months.
- Server history contains only official preceding months.

### Concurrency

- Button double click creates one month.
- Two tabs claiming the same expected month create one month.
- Same idempotency retry returns the persisted result.
- Same key with different inputs returns 409.
- Different concurrent keys cause one commit and one conflict.
- Lost-response retry does not advance another month.
- Failure before commit leaves progress unchanged.

### Restoration

- Refresh after Month N restores N.
- Logout/login restores N.
- Second browser restores N.
- Second device restores N.
- Completed months remain locked.
- Next month is backend-derived.
- Cumulative metrics equal persisted monthly sums.

### Multi-user/privacy

- Two same-course students have isolated sessions/results.
- A student cannot request another enrollment.
- Ranking exposes only nickname and allowed metrics.
- Policy source/hash/params never appears in leaderboard responses.
- Different-course students never appear.

### Instructor Progress

- A zero-month student appears.
- An N-month student shows N/12.
- Inactive students remain visible and marked inactive.
- Instructor cumulative revenue exactly equals Student UI.
- Last activity equals the latest committed month.
- An instructor cannot access an unowned course.

### Same-Stage

- Same course and stage included.
- Different stage/course excluded.
- Inactive enrollment/account excluded.
- Equal revenue shares rank.
- Deterministic display order does not alter rank.
- Only nickname is displayed.
- Stage 0 is unranked.

### Final

- Only active 12/12 students are ranked.
- Incomplete students may view but are unranked.
- Inactive 12/12 students are excluded.
- Equal revenue shares rank.
- Only nickname is displayed.
- Month 12 commit immediately grants eligibility.

### Frontend

- No Submit Result button.
- No Save to My History official flow.
- No fake aliases, mock classmates, or mock fallback.
- History, Same-Stage, and Final share Page 4.
- Editing localStorage cannot alter official state.
- Network errors do not optimistically advance progress.
- Repeat clicks are blocked while pending.
- Restoration finishes before Run Month is enabled.

### Legacy retirement

- Old submissions do not affect progress, History, Instructor Progress, or ranking.
- Submission endpoint no longer recomputes a year.
- 0005 leaves sessions/monthly results intact.
- No runtime import/query refers to the removed table.

## T. Genuine remaining open decisions

Only these implementation/operational details remain unresolved:

1. **History policy presentation:** exact policy snapshots are stored, but the UI has not specified whether to show full source for every historical month or only a hash/change indicator.
2. **Legacy cleanup acceptance window:** the exact proof period, backup retention duration, and approval gate before 0005 remain operational decisions.
3. **Inactive course historical leaderboard:** inactive enrollments are excluded, but it is not specified whether instructors may view a historical leaderboard for an inactive course.
