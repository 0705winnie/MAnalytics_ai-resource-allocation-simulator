# `months_completed` Production Schema Mismatch Investigation

Date: 2026-08-10

Scope: investigate the missing `0003_months_completed` migration and the incompatibility between the current repository's submission code and the production Neon `submissions` table.

No application code, Git history, migrations, or database records were modified during this investigation.

## A. Repository evidence

### Working-tree search results

The exact search terms appear only in these repository files.

#### `src/pages/LeaderboardPage.tsx`

Uses camelCase `monthsCompleted` exclusively in the browser-local mock leaderboard:

- Mock classmate values.
- Current user value derived from `bestSubmission?.monthly.length`.
- Table display.

It has no connection to PostgreSQL or `POST /api/submissions`.

Relevant lines:

```text
src/pages/LeaderboardPage.tsx:13
src/pages/LeaderboardPage.tsx:19-22
src/pages/LeaderboardPage.tsx:122
src/pages/LeaderboardPage.tsx:289
```

#### `docs/account-system-design.md`

Uses `completed_months` at line 352 as a proposed field on a future `simulation_sessions` table, not on `submissions`.

No tracked or untracked file contains:

- `months_completed`
- `month_count`
- `0003_months_completed`

No backend model, schema, route, API type, test, or migration contains a matching submission field.

### Current submission files

There is no `backend/app/schemas/submission.py`. The actual schema filename is plural:

- `backend/app/models/submission.py`
- `backend/app/schemas/submissions.py`
- `backend/app/routers/submissions.py`

### Reachable Git history

The following searches found no implementation:

```sh
git log --all -S'months_completed'
git log --all -G'months_completed|completed_months|monthsCompleted|month_count|0003_months_completed'
```

The only history matches were:

- The account-system design document.
- Historical versions of `LeaderboardPage.tsx`.

Branches and remotes present:

- `feature/debug`
- `online-database`
- `origin/feature/debug`
- `origin/feature/instructor-login-view-student-progress`
- `origin/online-database`

No tags exist, and no ref contains `0003`.

### Reflogs and unreachable objects

The reflogs contain only the clone, checkout, and remote-head operations for the current reachable commits.

`git fsck --full --no-reflogs --unreachable` found six unreachable trees but:

- No unreachable commits.
- No unique migration or implementation blobs.
- The trees are index/worktree snapshots containing current tracked files and previously generated untracked diagnostic documents.

A complete scan of every Git blob up to 2 MB found searched terms only in:

- Blob `39a3da3...`: `docs/account-system-design.md`.
- Three historical blobs of `src/pages/LeaderboardPage.tsx`.

There is no recoverable local blob for:

- `0003_months_completed.py`
- A `Submission.months_completed` model field.
- A submission request or response field.
- A route assignment.
- A frontend payload field.

Conclusion: the missing migration and matching code cannot be recovered from this clone's refs, reflogs, commits, trees, or object database.

### Test-suite evidence

The existing migration tests are already stale:

- `backend/tests/test_migrations.py:10` still defines `HEAD_REVISION = "0001_account_foundation"`.
- Its expected table set excludes `submissions`.
- `backend/tests/test_account_models.py:15` also expects only users, courses, and enrollments.

There are no submission endpoint tests. This explains why the `0002`/`0003` drift was not automatically caught.

## B. Confirmed HTTP 500 mechanism

### 1. Does the current model define `months_completed`?

No.

`backend/app/models/submission.py` maps only:

- `id`
- `enrollment_id`
- `total_revenue`
- `total_unfinished_requests`
- `total_unfinished_value`
- `warnings_count`
- `submitted_at`

### 2. Does the endpoint assign it?

No.

`submit_result()` currently constructs:

```python
Submission(
    enrollment_id=context.enrollment.id,
    total_revenue=result["total_revenue"],
    total_unfinished_requests=result["total_unfinished_requests"],
    total_unfinished_value=result["total_unfinished_value"],
    warnings_count=len(result["warnings"]),
)
```

### 3. Does the frontend send a month count?

No.

The request type contains only:

```ts
{
  policy_code: string
  params: PolicyParams
}
```

The actual call is:

```ts
postSubmitResult({
  policy_code: policyCode,
  params: policyParams,
})
```

The Pydantic request schema uses `extra="forbid"`, so adding a frontend-only field without updating the backend schema would produce HTTP 422.

### 4. Does the current INSERT omit the column?

Yes. Compiling the current SQLAlchemy insert locally produced:

```sql
INSERT INTO submissions (
    id,
    enrollment_id,
    total_revenue,
    total_unfinished_requests,
    total_unfinished_value,
    warnings_count
)
VALUES (...)
```

It omits both:

- `months_completed`
- `submitted_at`, which correctly has a server default

The production database has no server default for `months_completed`.

### 5. Does this predictably cause a NOT NULL violation?

Yes.

For an omitted PostgreSQL column:

- A server default is used if one exists.
- Otherwise the value is effectively `NULL`.

Because production defines:

```text
months_completed INTEGER NOT NULL
```

with no default, every INSERT from the current code must fail.

Expected database error:

```text
psycopg.errors.NotNullViolation:
null value in column "months_completed" of relation "submissions"
violates not-null constraint
```

Expected SQLSTATE:

```text
23502
```

Confirmed failure path:

```text
POST /api/submissions
  -> submit_result()
  -> run_full_simulation() succeeds
  -> Submission(...) without months_completed
  -> db.add(submission)
  -> SQL INSERT omits months_completed
  -> db.commit()
  -> PostgreSQL has no value/default for the required column
  -> NOT NULL violation (23502)
  -> unhandled SQLAlchemy IntegrityError
  -> FastAPI/Uvicorn returns HTTP 500
  -> frontend cannot parse a JSON detail
  -> "The backend did not respond as expected (HTTP 500)"
```

This is now a deterministic root cause, not merely a candidate.

## C. Student A and Student B timeline possibilities

### Confirmed facts

- Production is stamped `0003_months_completed`.
- Production has a non-null `submissions.months_completed` column with no default.
- Current reachable repository code does not supply that column.
- The current code cannot successfully insert into that production schema.
- Student B's HTTP 500 is consistent with the resulting NOT NULL violation.

### Most plausible timeline: matching `0003` code was deployed, then code rolled back

1. A code version containing the `0003` migration, model support, and route/request support was deployed.
2. Production was migrated to `0003`.
3. Student A submitted successfully using that matching code.
4. Render was later redeployed or rolled back to code equivalent to the current repository.
5. Database migrations were not downgraded, which is normally correct.
6. Student B submitted with old code against the forward schema.
7. The INSERT omitted `months_completed` and failed.

This best explains successful earlier writes plus current deterministic failures.

### Plausible alternative: Student A submitted before `0003`

1. Student A submitted while production was at `0002`.
2. The missing migration later added the column, backfilled existing rows, and made it non-null.
3. Current or older application code remained deployed or was redeployed.
4. Student B's later INSERT failed.

This requires the missing migration to have safely backfilled Student A's existing row.

### Other plausible explanations

- Student A's row was created manually or through another code path.
- Student A's “success” referred to local History rather than the PostgreSQL submission.
- Render temporarily targeted a different Neon branch or database.
- A deployed but never-pushed commit contained the missing code and migration.

### What requires Render evidence to prove

Only Render deployment history and logs could establish:

- Exact deployed commit SHAs.
- Deployment and rollback times.
- Whether a non-pushed build artifact contained `0003`.
- Whether `DATABASE_URL` changed between deployments.
- The exact time `0003` was applied.
- Whether Student A received HTTP 201 from the same service and database.
- The exact Student B traceback.

The repository alone cannot select one timeline conclusively.

## D. Intended `months_completed` semantics

### What current code proves

Submission is allowed after any positive number of completed months.

The only guard is:

```ts
if (completedMonths.length === 0 || submitting) return
```

Therefore the current frontend allows submission after:

- 1 month: yes.
- 2-11 months: yes.
- 12 months: yes.
- 0 months: no submission UI path.

However, the backend ignores the number of client-completed months and independently runs all 12 months:

```python
result = run_full_simulation(...)
```

Thus the persisted revenue always describes a server-computed 12-month result, even if the visible student UI contains only one month.

### Instructor Progress

Current Instructor Progress does not expect or expose a month count.

Its response includes only:

- Enrollment ID.
- Username.
- Nickname.
- Submission count.
- Latest revenue and timestamp.
- Best revenue.

No instructor TypeScript type, parser, table column, query, or response schema reads `months_completed`.

### Design-document evidence

The architectural design describes:

- `simulation_sessions.completed_months`.
- Class Progress showing months completed.
- Same-stage rankings grouped by completed month.
- Final leaderboard eligibility requiring 12 months.

The implementation-progress document says simulation persistence and same-stage rankings remain future phases.

That evidence supports the general concept of a completed-month count, but places it on a persisted session/stage snapshot—not necessarily this temporary summary `submissions` table.

### Best inference, with confidence limits

Two interpretations remain possible.

#### Interpretation 1: UI progress at submission time

```text
months_completed = completedMonths.length
```

Supporting evidence:

- Current UI has that count.
- Submission is enabled for partial runs.
- Design discusses same-stage comparisons.

Problem:

- The stored revenue is still recomputed over 12 months, so a value of 4 would describe UI progress while the associated revenue describes 12 months.

#### Interpretation 2: Months represented by the stored result

```text
months_completed = 12
```

Supporting evidence:

- The backend always computes 12 months.
- This value is server-derived and cannot be falsified by a client.
- It keeps the database row internally consistent.

Problem:

- It does not describe the student's visible progress when they click Submit.
- Every submission would have the same count, limiting its usefulness.

The missing `0003` implementation would have resolved this ambiguity, but it is not recoverable locally. The repository does not provide enough evidence to assert that the field was intended to accept client progress.

## E. Repair options

### Option 1 — Recreate `0003` and restore matching code support

Safest for the current incident.

Recreate a migration node with:

```python
revision = "0003_months_completed"
down_revision = "0002_submissions"
```

The migration should logically reproduce the actual production schema. For databases upgrading from `0002` that may already contain submissions, a safe implementation would:

1. Add `months_completed` as nullable.
2. Backfill legacy rows.
3. Alter it to non-null.

Production is already stamped `0003`, so Alembic would not execute the recreated migration there. It restores the missing graph node and makes fresh, test, and older databases reproducible.

Then restore code support:

- Add the mapped integer field.
- Assign it explicitly on every new submission.
- Add tests.

Advantages:

- Restores Git/Alembic/production revision consistency.
- Does not alter existing production rows.
- Stops the failing INSERT.
- Makes clean and test upgrades reach the real schema.
- Avoids a production migration for a column that already exists.

Risk:

- The exact historical migration/backfill logic is unknown.
- Field semantics must be selected explicitly.

### Option 2 — Restore a compatibility `0003`, then add a forward `0004`

Use this if the desired schema differs from production—for example, when adding a server default, check constraint, or changing nullability.

Sequence:

1. Recreate `0003` as the missing graph node matching current production.
2. Create `0004` with `down_revision = "0003_months_completed"`.
3. Make only forward changes in `0004`.

Advantages:

- Preserves the fact that production already reached `0003`.
- Makes future migration history linear and honest.
- Suitable if schema changes beyond code alignment are required.

Risks:

- More moving parts.
- Requires a real production migration.
- Unnecessary if the existing schema is acceptable.
- A default could mask missing application assignments rather than enforce correct behavior.

A new `0004` cannot safely bypass the missing `0003`; Alembic must be able to resolve the current production revision before traversing to a later revision.

### Option 3 — Remove or weaken the production column

Examples:

- Drop `months_completed`.
- Make it nullable.
- Add a server default without restoring code support.

This is the riskiest option.

Problems:

- Does not restore the missing Alembic revision in Git.
- Can destroy existing production information.
- Makes the database conform to accidentally older code.
- A nullable column would silently record incomplete data.
- A server default could hide future code/schema drift.
- Requires production DDL for a problem fixable in application compatibility.

This option is not recommended.

### Why downgrade, stamp, or direct DDL is unsafe

- **Downgrade:** The downgrade implementation is missing and the column contains production data.
- **Stamp to `0002`:** Changes only Alembic metadata; it does not remove the column. It would falsely describe the schema.
- **Stamp to a fabricated revision:** Also misrepresents applied operations.
- **Drop column:** Destructive and unnecessary.
- **Direct `ALTER TABLE`:** Creates more schema history outside Git/Alembic and deepens the mismatch.

## F. Recommended minimal fix

The smallest production-safe repair is Option 1:

1. Recreate `0003_months_completed.py` with the exact existing revision ID and parent.
2. Map `Submission.months_completed` as a required integer.
3. Explicitly assign it in `submit_result()`.
4. Leave the production column and all existing rows untouched.
5. Add migration, model, and endpoint tests.
6. Deploy code only after testing against a production-shaped test database.

For the minimal compatibility patch, define `months_completed` as **12**, derived on the server, because the stored result is produced by `run_full_simulation()` and always contains 12 months.

That choice:

- Requires no frontend or request-contract change.
- Does not trust client state.
- Makes every new row internally consistent with its stored totals.
- Stops the NOT NULL failure.
- Does not pretend partial session persistence already exists.

It should be documented as:

> Number of months represented by the server-computed submission result.

This does not solve the broader partial-progress mismatch. That remains part of the later persistence redesign.

Before implementation, one final read-only production query would be useful:

```sql
SELECT months_completed, COUNT(*)
FROM submissions
GROUP BY months_completed
ORDER BY months_completed;
```

If existing production rows include values below 12, that proves the lost implementation used a different semantic and the minimal assignment should be reconsidered before coding.

## G. Exact files that would need changes

### Minimal fix

#### New migration

```text
backend/alembic/versions/0003_months_completed.py
```

Purpose:

- Restore the missing revision node.
- Reproduce the actual column for clean and `0002` databases.
- Safely backfill preexisting `0002` submission rows.

#### Submission model

```text
backend/app/models/submission.py
```

Purpose:

- Add the required mapped integer field.

#### Submission route

```text
backend/app/routers/submissions.py
```

Purpose:

- Assign `months_completed=12` explicitly.

#### Migration tests

```text
backend/tests/test_migrations.py
```

Purpose:

- Change expected head from stale `0001` to `0003`.
- Include `submissions`.
- Verify the `0002 -> 0003` upgrade with an existing row.

#### Model tests

```text
backend/tests/test_account_models.py
```

Purpose:

- Include `submissions` and its actual columns in metadata assertions.
- Assert `months_completed` is integer and non-null.

#### New endpoint tests

```text
backend/tests/test_submissions.py
```

Purpose:

- Exercise authenticated successful inserts and failure rollback.

No frontend file or Pydantic schema needs to change for the recommended server-derived value.

If evidence proves `months_completed` should mean client UI progress, additional files would be required:

- `backend/app/schemas/submissions.py`
- `src/types/simulation.ts`
- `src/pages/SimulationPage.tsx`
- Possibly submission response types and parsers

That larger contract change is not recommended without stronger evidence.

## H. Exact tests to run before deployment

### Migration graph tests

1. `alembic heads` reports exactly:

   ```text
   0003_months_completed (head)
   ```

2. Fresh database upgrades through:

   ```text
   base -> 0001 -> 0002 -> 0003
   ```

3. Existing `0002` database with zero submissions upgrades successfully.
4. Existing `0002` database with at least one submission upgrades successfully and backfills that row.
5. `alembic current` reports `0003_months_completed`.
6. `alembic check` reports no model/schema drift.
7. Downgrade and re-upgrade are tested only on the protected `_test` database.

### Model tests

1. `Submission.__table__` includes `months_completed`.
2. Type is `Integer`.
3. `nullable is False`.
4. No accidental server default is introduced unless explicitly chosen.
5. Existing columns and foreign-key/index definitions remain unchanged.

### Endpoint tests

1. Authenticated Student A submission returns HTTP 201.
2. Authenticated Student B submission returns HTTP 201.
3. Both rows use their own enrollment IDs.
4. Both rows store `months_completed = 12`.
5. Repeated submissions remain allowed.
6. Missing or invalid authentication returns structured 401/403, not 500.
7. Policy compilation error returns 400.
8. Forced database failure rolls back the session.
9. Response serialization succeeds after commit and refresh.

### Production-shaped integration test

Against a disposable database with exactly the observed production schema:

1. Apply or recreate revision `0003`.
2. Confirm `months_completed INTEGER NOT NULL` with no server default.
3. Run `POST /api/submissions`.
4. Confirm the INSERT includes `months_completed`.
5. Confirm HTTP 201.
6. Confirm no existing rows were modified.

### Regression tests

Run:

```sh
cd backend
pytest
```

Also run:

```sh
npm run build
```

The current migration and model tests require correction before the suite can be considered trustworthy.

### Pre-deployment verification

1. Back up or branch Neon before deployment.
2. Confirm production remains at `0003_months_completed`.
3. Confirm existing `months_completed` distribution read-only.
4. Deploy to a staging or Neon branch first.
5. Test two distinct student enrollments.
6. Confirm Instructor Progress still reads submissions.
7. Confirm no production migration is attempted unnecessarily.
8. Deploy application code.
9. Verify one authorized submission and inspect the resulting row.

## Final conclusion

The production schema and current repository code are deterministically incompatible. The current ORM INSERT omits a required production column with no default, so PostgreSQL rejects every new submission with a NOT NULL violation. The missing `0003` migration and matching code are not recoverable from this clone. The safest minimal repair is to reconstruct the missing revision, restore the model field, assign a server-derived value explicitly, and validate the complete path against a production-shaped disposable database before deployment.
