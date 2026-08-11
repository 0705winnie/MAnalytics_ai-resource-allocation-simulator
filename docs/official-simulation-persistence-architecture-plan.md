# Official Simulation Persistence Architecture and Repair Plan

This document is an implementation proposal only. No application code, migrations, Git history, or production data were changed while producing it.

## A. Current vs intended architecture

### Current architecture

| Concern | Current source of truth | Problem |
|---|---|---|
| Completed months | React `completedMonths` state in `src/App.tsx` | Refresh, logout, browser change, and device change lose progress. |
| Next month | `completedMonths.length + 1` in `SimulationPage.tsx` | The browser controls sequencing. |
| Previous-month policy history | Browser-supplied `previous_months` | The backend trusts client history. |
| Monthly calculation | Unauthenticated `POST /api/simulate/month` | No database write or enrollment ownership. |
| Official submission | Authenticated `POST /api/submissions` | Re-runs all 12 months with the latest policy and inserts one legacy row. |
| Student history | `submissionHistory` in localStorage | Browser-specific and manually saved. |
| Student leaderboard | localStorage plus hardcoded classmates | Not shared or course-scoped. |
| Instructor progress | Legacy `submissions` rows | Uses a different result path from the student UI. |

The existing engine already contains the correct reusable calculation primitive: `simulate_month(...)`. It derives a deterministic month-specific arrival stream from `DEFAULT_SEED`, accepts prior monthly summaries as policy history, and uses the same monthly core as `run_full_simulation(...)`. The persistence redesign does not require a new simulation algorithm.

### Intended architecture

```text
Authenticated enrollment
        |
        v
simulation_sessions -- one official progression per enrollment
        |
        v
monthly_results -- immutable months 1 through N with policy snapshots
        |
        +-- Student restoration/history/cumulative result
        +-- Instructor Progress
        +-- Same-Stage Leaderboard
        +-- Final Leaderboard
```

PostgreSQL becomes the only authority for:

- `completed_months`
- the next runnable month
- monthly and cumulative results
- policy execution history
- instructor progress
- both leaderboards

The backend supplies database-loaded `previous_months` to `simulate_month`. The browser no longer supplies authoritative progress or history.

## B. Database model proposal

Two new tables are sufficient.

### `simulation_sessions`

| Field | Type | Rule |
|---|---|---|
| `id` | UUID | Primary key |
| `enrollment_id` | UUID | FK to `enrollments.id`, non-null and unique |
| `completed_months` | SMALLINT | Non-null, default `0`, range 0-12 |
| `created_at` | TIMESTAMPTZ | Non-null server timestamp |
| `updated_at` | TIMESTAMPTZ | Updated after each committed month |
| `last_completed_at` | TIMESTAMPTZ nullable | Most recent successful month timestamp |

Do not store a separate status column. Derive it:

- `0` -> `not_started`
- `1-11` -> `in_progress`
- `12` -> `completed`

This prevents status and month count from disagreeing.

Cumulative totals should initially be calculated from at most 12 `monthly_results` rows. Avoid denormalized cumulative columns that could drift from the monthly records.

### `monthly_results`

| Field | Type | Purpose |
|---|---|---|
| `id` | UUID | Primary key |
| `session_id` | UUID | FK to `simulation_sessions.id`, non-null |
| `month` | SMALLINT | Official month 1-12 |
| `idempotency_key` | UUID | Makes a lost-response retry safe |
| `policy_code` | TEXT | Exact policy source used for this month |
| `policy_params` | JSONB | Exact numeric parameter snapshot |
| `policy_hash` | CHAR(64) | SHA-256 of canonical source and params |
| `total_requests` | INTEGER | Existing monthly response field |
| `admitted_requests` | INTEGER | Existing field |
| `completed_requests` | INTEGER | Existing field |
| `rejected_requests` | INTEGER | Existing field |
| `total_revenue` | FLOAT | Preserves current engine semantics |
| `unfinished_requests` | INTEGER | Existing field |
| `unfinished_value` | FLOAT | Existing field |
| `avg_utilization` | JSONB | Small cluster-keyed map |
| `peak_utilization` | JSONB | Small cluster-keyed map |
| `remaining_capacity` | JSONB | Small cluster-keyed map |
| `by_type` | JSONB | Bounded existing aggregate list |
| `warnings` | JSONB | Existing warning strings |
| `benchmark_comparison` | JSONB | Bounded historical comparison result |
| `completed_at` | TIMESTAMPTZ | Non-null server timestamp |

Do not persist raw arrivals, every simulated job, RNG state, or policy execution internals. The current aggregate response contains enough information for restoration and History.

### Policy snapshots

A separate `policy_versions` table is unnecessary in this phase. Each immutable month corresponds to exactly one executed policy snapshot, so storing `policy_code`, `policy_params`, and `policy_hash` directly on `monthly_results` is simpler and correctly supports different policies in different months.

The hash supports comparison and integrity; it does not replace the source snapshot.

## C. Constraints and indexes

Recommended constraints:

- `UNIQUE (enrollment_id)` on `simulation_sessions`.
- `CHECK (completed_months BETWEEN 0 AND 12)`.
- `UNIQUE (session_id, month)` on `monthly_results`.
- `UNIQUE (session_id, idempotency_key)`.
- `CHECK (month BETWEEN 1 AND 12)`.
- Nonnegative checks for request counts, revenue, and unfinished value.
- `admitted_requests <= total_requests`.
- `completed_requests <= admitted_requests`.
- `rejected_requests = total_requests - admitted_requests`.
- `unfinished_requests = admitted_requests - completed_requests`, while this remains guaranteed by the engine.
- Foreign keys using `ON DELETE RESTRICT` in this phase.

Recommended indexes:

- Unique index on `simulation_sessions.enrollment_id`.
- Index on `simulation_sessions.completed_months` for stage filtering.
- Unique `(session_id, month)` index for ordered history reads and duplicate protection.
- Existing enrollment uniqueness on `(course_id, user_id)` supports course joins.

A simple database constraint cannot enforce both contiguous stored months and `completed_months = MAX(month)`. Enforce that invariant in one locked transaction and test it explicitly. A database trigger would add unnecessary complexity.

### Preventing duplicate execution

Three protections work together:

1. `expected_month` prevents two separate clicks or tabs from turning one intended action into Month N followed by Month N+1.
2. `idempotency_key` allows the same request to be retried safely when the committed response was lost.
3. `UNIQUE (session_id, month)` is the final database backstop.

## D. Backend endpoint design

### Student restoration

`GET /api/simulation/session`

Authenticated student endpoint returning:

- `session_id`
- `completed_months`
- `next_month`, or `null` at 12/12
- derived status
- ordered persisted monthly results
- server-calculated cumulative result
- latest executed policy/params for restoring the editor baseline

The session is derived from the authenticated enrollment. No client-supplied enrollment or course ID is accepted.

### Run next month

`POST /api/simulation/session/months/next`

Recommended body:

```json
{
  "expected_month": 5,
  "idempotency_key": "client-generated-UUID",
  "policy_code": "def admission_policy(...): ...",
  "params": {}
}
```

`expected_month` is a concurrency assertion rather than authority. The server calculates the actual next month from the locked database session.

Return the complete persisted session representation after commit. This avoids frontend append and state-drift errors.

### Student Same-Stage Leaderboard

`GET /api/leaderboards/same-stage`

The server derives the requesting student's course and current `completed_months`. Return only students in the same course at exactly that stage.

Student-facing entries contain:

- rank
- nickname
- completed months
- cumulative revenue
- last activity
- `is_current_user`

Never return Berkeley usernames, policies, parameters, or policy hashes.

At stage 0, return an empty/unranked response indicating that Month 1 must be completed.

### Student Final Leaderboard

`GET /api/leaderboards/final`

Course is derived from authentication. Rank only sessions with `completed_months = 12`. Students below 12/12 may view the list but are marked ineligible/unranked.

### Instructor Progress

Keep the existing route:

`GET /api/instructor/courses/{course_id}/progress`

Replace its submission-based implementation. Each row should contain:

- `enrollment_id`
- Berkeley username for authorized roster management
- nickname
- `completed_months`
- cumulative revenue
- last activity
- derived status
- optionally aggregated warning count

Students with no completed months still appear as 0/12.

### Instructor leaderboards

- `GET /api/instructor/courses/{course_id}/leaderboards/same-stage?stage=N`
- `GET /api/instructor/courses/{course_id}/leaderboards/final`

Both require instructor ownership of the course. Same-stage validates `N` from 1 through 12.

Student and instructor leaderboard endpoints should call one shared course-scoped ranking service so calculations cannot diverge.

### Endpoints to retire

- `POST /api/submissions`: return `410 Gone` without calculation or persistence during a compatibility period.
- `POST /api/simulate`: remove from the normal student flow; it must not remain an alternative official full-year run.
- `POST /api/simulate/month`: replace with the authenticated session endpoint.

The underlying `simulate_month` service remains. `run_full_simulation` may remain for engine tests and internal benchmarks, but not as a student finalization mechanism.

## E. Month-run transactional flow

1. Authenticate with `require_student`.
2. Resolve the enrollment and official session only from the authentication context.
3. Validate and compile `policy_code`. Policy errors return 400 without changing progress.
4. Begin a PostgreSQL transaction.
5. Lock the session row using `SELECT ... FOR UPDATE`.
6. Check `(session_id, idempotency_key)`:
   - If the same request already committed, return that persisted result.
   - If the key exists with different inputs, return 409.
7. Calculate `actual_next_month = completed_months + 1`.
8. Return 409 if the session is complete or `expected_month != actual_next_month`.
9. Load Months 1 through N from `monthly_results`, ordered by month.
10. Construct `history["previous_months"]` from those persisted results.
11. Call `simulate_month(actual_next_month, ..., seed=DEFAULT_SEED, previous_months=...)`.
12. Insert the immutable monthly result, policy snapshot, and idempotency key.
13. Update `completed_months`, `updated_at`, and `last_completed_at`.
14. Flush so constraint failures occur before response construction.
15. Commit.
16. Build the response from persisted rows.
17. Return only after the commit succeeds.

Any calculation, insert, flush, or commit failure rolls back both the result and the progress update.

For two simultaneous requests with `expected_month=5`, the first locks and commits Month 5. The second then sees that Month 6 is next and returns 409 instead of running it accidentally.

Holding the session lock through calculation is the simplest correctness-first design for the current workload. A job/reservation system should be considered only if execution later becomes too slow for a database transaction.

## F. Frontend changes

### Restoration

`src/App.tsx` should load `GET /api/simulation/session` after authentication. Until it completes, Policy, Simulation, and History should show a loading state instead of constructing an empty official session.

Replace `completedMonths` as an independent client authority with the returned session object. After a successful month run, replace the complete state with the committed server response rather than appending a client result.

The latest executed policy snapshot may initialize the editor after login. Any subsequent unsaved editor draft must remain clearly non-official.

### Simulation page

`src/pages/SimulationPage.tsx` should:

- stop supplying authoritative `month`;
- stop supplying `previous_months`;
- generate one idempotency UUID per user action;
- send `expected_month`;
- consume the official session response;
- remove "Save to My History";
- remove "Submit Result" and all related state/error handling;
- retain existing charts and monthly details using persisted results.

### History and student leaderboards

Convert `src/pages/LeaderboardPage.tsx` into three views or tabs:

- Simulation History
- Same-Stage Leaderboard
- Final Leaderboard

History reads official monthly results. Leaderboard views call their respective APIs.

The current leaderboard sorts descending by `bestRunRevenue`. With one official progression, the equivalent ranking metric is cumulative `SUM(monthly_results.total_revenue)`.

The current JavaScript sort has no explicit business tie rule. Equal results inherit input order from stable sorting, which must not silently become a ranking policy.

### localStorage

Existing keys that must stop being authoritative:

- `currentUser`
- `submissionHistory`

Both are defined in `src/lib/storage.ts`. They should ultimately be removed. A future distinct key for an unsaved policy draft or UI preferences is acceptable, but it must never contain official progress, official results, ranks, or authenticated identity.

### Mock leaderboard removal

Remove from `src/pages/LeaderboardPage.tsx`:

- `MOCK_CLASSMATES`
- `MOCK_PAST_SUBMISSIONS`
- local `leaderboardRows` construction
- the mock fallback when local history is empty
- local browser identity and "Local Prototype Profile" messaging

### Instructor UI

The smallest navigation change is:

```ts
export type CourseSection = 'roster' | 'progress' | 'leaderboards'
```

Add `Leaderboards` to `src/instructor/CourseSectionNavigation.tsx` and render one new `InstructorLeaderboards` component from `src/pages/InstructorCourseDetailPage.tsx`. No unrelated instructor routing redesign is required.

## G. Legacy submissions / Alembic 0003 handling

Reconstruct `0003_months_completed` with exactly:

```python
revision = "0003_months_completed"
down_revision = "0002_submissions"
```

Its upgrade should:

1. Add `submissions.months_completed` as temporarily nullable.
2. Backfill existing 0002 submission rows to `12`.
3. Alter the column to `nullable=False`.
4. Leave it without a server default.

Backfilling to 12 is supported by both the old endpoint behavior, which always recomputed a full year, and the confirmed production distribution `(12, 4)`.

This migration is legacy-schema compatibility only. No new business logic should depend on the field.

Add `months_completed` to the SQLAlchemy `Submission` model so model metadata matches production and Alembic. Do not add new write behavior around it.

Production is already stamped at `0003_months_completed`, so restoring the missing migration file does not rerun it there. It restores the graph so production can advance to 0004.

Avoid:

- `alembic stamp`, because it changes metadata without proving schema correctness;
- production downgrade, because it drops legacy information;
- direct production drop/alter operations on the legacy column;
- importing legacy submissions as fabricated monthly rows.

Keep the table and its four rows. Retire the POST endpoint with 410 and no full-year rerun.

## H. Migration plan

### Revision chain

```text
0001_account_foundation
  -> 0002_submissions
  -> 0003_months_completed
  -> 0004_simulation_persistence
```

`0004_simulation_persistence` should:

- create `simulation_sessions`;
- create `monthly_results`;
- add all constraints and indexes;
- create 0-month sessions for existing enrollments, subject to the legacy-transition decision in Section L.

Future roster imports should create the empty session transactionally with the enrollment. A defensive internal get-or-create guarded by the unique enrollment constraint may cover legacy edge cases, but the restoration GET should normally be read-only.

### Required migration rehearsal

On an isolated PostgreSQL or Neon branch:

1. Upgrade a clean database from base through 0004.
2. Start from 0002 with existing submissions and verify 0003 backfills to 12.
3. Build a production-shaped database already stamped at 0003 with the existing non-null column and legacy rows.
4. Run `alembic upgrade head` and verify only 0004 executes.
5. Confirm all legacy rows and values are unchanged.
6. Run `alembic check`.
7. Inspect the new constraints and indexes.
8. Exercise downgrade only on a disposable test database.

Production should run `alembic upgrade head` only after these rehearsals and application tests pass. No production stamp, downgrade, or manual DDL should be necessary.

## I. Incremental implementation phases

### Phase 0 - Restore migration graph

- Reconstruct 0003.
- Add legacy model compatibility.
- Correct migration head tests.
- Verify clean, 0002-shaped, and production-0003-shaped paths.

### Phase 1 - Add persistence schema

- Add session/month models and relationships.
- Add 0004.
- Add serialization/query services.
- Backfill empty sessions as agreed.
- Do not switch the UI yet.

### Phase 2 - Official restoration and month execution

- Add authenticated restoration.
- Add transactional run-next-month.
- Load policy history from PostgreSQL.
- Add row locking, expected-month validation, and idempotency.
- Verify rollback and concurrent requests.

### Phase 3 - Switch student flow

- Initialize from restoration.
- Run months through the official endpoint.
- Replace append logic with the server response.
- Remove Save and Submit controls/calls.
- Convert page 4 to persisted monthly History.
- Retire submission execution with 410.

Phases 2 and 3 should deploy together so students never receive a UI without a working official month path.

### Phase 4 - Instructor Progress

- Replace submission queries with session/month aggregation.
- Update schemas, frontend types, and UI.
- Compare instructor totals with the exact student response.

### Phase 5 - Both leaderboards

- Add one shared course-scoped ranking service.
- Add student Same-Stage and Final APIs/UI.
- Add instructor stage selector and Final view.
- Enforce nickname-only student visibility.

### Phase 6 - Remove obsolete authority paths

- Remove mock classmates/submissions.
- Remove `currentUser` and `submissionHistory` localStorage paths.
- Remove unused local user/submission types.
- Stop registering old simulation routes once compatibility traffic no longer needs them.

### Phase 7 - Cross-user production smoke test

- Test two students, multiple stages, and two courses.
- Verify refresh/login/device restoration.
- Verify instructor equality.
- Test double-click/concurrent execution.
- Confirm legacy submissions remain unchanged.

## J. Exact files likely to change

### Phase 0

- `backend/alembic/versions/0003_months_completed.py` - new
- `backend/app/models/submission.py`
- `backend/tests/test_migrations.py`
- `backend/tests/test_submissions.py` - new, or equivalent legacy endpoint tests

### Phases 1-2

- `backend/alembic/versions/0004_simulation_persistence.py` - new
- `backend/app/models/simulation_session.py` - new
- `backend/app/models/monthly_result.py` - new
- `backend/app/models/enrollment.py`
- `backend/app/models/__init__.py`
- `backend/app/schemas/simulation_sessions.py` - new
- `backend/app/routers/official_simulation.py` - new
- `backend/app/services/simulation_persistence.py` - new
- `backend/app/services/roster_imports.py`
- `backend/app/routers/simulate.py`
- `backend/app/main.py`
- `backend/tests/test_official_simulation.py` - new
- `backend/tests/test_simulate_month.py`

The calculation behavior in `backend/app/services/simulation_engine.py` should not need redesign.

### Phase 3

- `src/App.tsx`
- `src/pages/SimulationPage.tsx`
- `src/pages/PolicyAIPage.tsx`
- `src/pages/LeaderboardPage.tsx`
- `src/components/NavBar.tsx`
- `src/lib/api.ts`
- `src/types/simulation.ts`
- `backend/app/routers/submissions.py`
- `backend/app/schemas/submissions.py`
- frontend component/API tests using the project's selected test framework

### Phase 4

- `backend/app/routers/instructor_progress.py`
- `backend/app/schemas/instructor_progress.py`
- `src/instructor/InstructorStudentProgress.tsx`
- `src/instructor/api.ts`
- `src/instructor/types.ts`
- `backend/tests/test_instructor_progress.py` - new

### Phase 5

- `backend/app/routers/leaderboards.py` - new
- `backend/app/schemas/leaderboards.py` - new
- `backend/app/services/leaderboards.py` - new
- `backend/app/main.py`
- `src/instructor/InstructorLeaderboards.tsx` - new
- `src/instructor/CourseSectionNavigation.tsx`
- `src/pages/InstructorCourseDetailPage.tsx`
- `src/instructor/api.ts`
- `src/instructor/types.ts`
- `src/pages/LeaderboardPage.tsx`
- `backend/tests/test_leaderboards.py` - new

### Phase 6

- `src/lib/storage.ts` - remove if no draft/UI storage remains
- `src/types/user.ts` - remove if unused
- `src/App.tsx`
- `src/pages/LeaderboardPage.tsx`
- `backend/app/main.py`

## K. Test plan

### Database and migrations

- Fresh base -> 0004 upgrade.
- 0002 with legacy rows -> 0003 -> 0004.
- Production-shaped, already-stamped 0003 -> 0004.
- `alembic check` reports no drift.
- Legacy row count and values remain unchanged.
- No migration fabricates monthly results from submissions.
- Existing `months_completed NOT NULL` remains intact.

### Official progression

- Month 1 creates one row and changes progress 0 -> 1.
- Sequential Months 1-12 produce exactly 12 rows.
- Month 13 is rejected.
- A completed month cannot be rerun.
- A month cannot be skipped.
- Wrong `expected_month` returns 409.
- A client cannot select another enrollment/course.
- Policy history is ordered and server-generated.
- Different policy snapshots are preserved across months.
- Policy failure does not insert or increment.
- Commit failure rolls back both result and progress.

### Concurrency and idempotency

- Retrying the same idempotency key returns the same persisted month.
- Reusing a key with different inputs returns 409.
- Two concurrent requests for one expected month create one row.
- Two different double-click keys do not advance two months.
- Unique constraint failures produce no partial state.

### Restoration

- Refresh after Month N restores N and next month N+1.
- Logout/login restores identical state.
- A second browser/device restores identical state.
- Cumulative totals equal persisted monthly sums.
- Latest policy restoration exposes only the current student's policy.

### Instructor Progress

- A 0-month enrolled student appears as 0/12.
- Month N immediately changes instructor progress to N/12.
- Instructor cumulative revenue exactly equals the student response.
- Last activity equals the latest monthly timestamp.
- 12/12 status is completed.
- An instructor cannot access an unowned course.

### Leaderboards

- Same-course, same-stage students are included.
- Other stages and other courses are excluded.
- Final includes only 12/12.
- An incomplete student can view Final but is unranked.
- Ranking uses only persisted cumulative revenue.
- Student responses expose nickname but not Berkeley username.
- No leaderboard exposes another policy or parameters.
- Student and instructor results agree for the same course/stage.
- Tie behavior is tested after the rule is selected.

### Frontend

- Initial UI waits for restoration.
- A successful month uses the committed server response.
- Refresh preserves the result.
- No Submit Result button or `/api/submissions` call.
- No Save to My History official flow.
- History renders persisted monthly results.
- Same-Stage follows the current stage automatically.
- Final displays eligibility correctly.
- No mock classmates or mock submissions remain.
- Clearing or altering localStorage cannot change official progress or rank.
- A network failure does not optimistically advance a month.

## L. Open decisions

Only the following decisions remain unresolved by the confirmed rules:

1. **Revenue ties.** Decide whether equal cumulative revenue shares a rank and how tied entries are displayed. Recommended default: SQL `RANK()` by revenue, with equal values sharing rank and a non-ranking stable display order.

2. **The four legacy 12-month submitters.** Legacy rows contain full-year aggregates but no monthly results or per-month policy snapshots. They cannot be truthfully converted into the new official history. Choose between starting these enrollments at 0/12, showing a separately labeled legacy final result, or a documented exceptional transition. Do not fabricate twelve monthly rows.

3. **Inactive/disabled enrollment visibility.** Recommended default: only active users/enrollments appear to students, while instructors retain progress visibility for disabled records.

4. **Engine changes during an active progression.** Decide whether students remain pinned to the Month 1 engine version or later months use the currently deployed engine. If behavior may change mid-course, introduce an engine version identifier before official persistence begins.

5. **Future Reset Session behavior.** Authorization, audit retention, and archive/delete semantics remain undefined. Keep reset absent until a separate destructive, instructor-controlled workflow is approved.
