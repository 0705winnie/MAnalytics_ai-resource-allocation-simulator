# Student B Submission HTTP 500 — Reproduction and Diagnosis Guide

Date: 2026-08-10

Scope: isolate the production error returned by `POST /api/submissions` for Student B.

No application code, deployment configuration, migrations, or database records were changed during this investigation.

## A. Exact Render reproduction procedure

1. Open the Render Dashboard and select the web service named **`resource-allocation-simulator`**.

   This is the single-origin service that serves both FastAPI and the built React frontend. There is no separate backend service in the current `render.yaml`.

2. Open the service's **Logs** page.

3. Select **Live tail** in the time-range selector.

   Initially, do not apply `level:error` or a text filter. Filtering on `/api/submissions` can hide traceback lines that do not contain the URL.

4. In a separate browser tab:

   - Log in as Student B.
   - Open the simulator.
   - Run at least one month.
   - Open browser Developer Tools, select **Network**, and clear existing requests.
   - Click **Submit Result exactly once**.
   - Select the failed `submissions` network request and note:
     - Status `500`.
     - Response header `Rndr-Id`, if present. This is a request identifier, not a credential.
   - Do not copy request headers, cookies, or the request body.

5. Return immediately to Render Logs. Look for either form of request entry:

   ```text
   POST /api/submissions ... 500
   ```

   or Uvicorn's form:

   ```text
   "POST /api/submissions HTTP/1.1" 500 Internal Server Error
   ```

6. Around the same timestamp, find:

   ```text
   ERROR: Exception in ASGI application
   Traceback (most recent call last):
   ```

7. Copy back exactly:

   - The `POST /api/submissions ... 500` request line.
   - The `ERROR: Exception in ASGI application` line.
   - The entire traceback from `Traceback...` through the final exception type and message.
   - Every chained section beginning with:
     - `During handling of the above exception...`
     - `The above exception was the direct cause...`
   - Five log lines after the final exception, if any.
   - The `Rndr-Id` or Render `requestID`, if available.
   - The deploy commit SHA shown by Render.

Do not truncate the middle of the traceback. In particular, retain frames mentioning:

- `backend/app/routers/submissions.py`
- `run_full_simulation`
- `db.commit()`
- `db.refresh()`
- `sqlalchemy`
- `psycopg`

You may redact:

- Cookie or token values.
- Passwords or activation codes.
- Database host or user information.
- Policy source.
- SQL parameter values.
- Student UUIDs if desired.

Do not redact exception class names, constraint names, table names, column names, or traceback line numbers. Those are diagnostically important.

If the Render workspace supports HTTP request-log filters, use this to locate the request:

```text
method:POST path:/api/submissions status_code:500
```

Then clear the filter and use the timestamp to recover the surrounding application traceback. HTTP request-log filtering is available only on qualifying workspace plans. Live tail and application logs remain the primary source.

Official references:

- <https://render.com/docs/logging>
- <https://render.com/docs/free>
- <https://render.com/docs/ssh>

## B. Current migration and deployment configuration

The build command in `render.yaml` is:

```sh
npm ci --legacy-peer-deps && npm run build && pip install -r backend/requirements.txt
```

The start command is:

```sh
cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Findings:

- `alembic upgrade head` does not run in the build command.
- It does not run in the start command.
- `render.yaml` has no `preDeployCommand`.
- No other automatic production migration hook exists in the repository.
- The README documents `alembic upgrade head` as a manual local operation.
- Test setup applies migrations only to the protected test database. It does not affect production.
- Current repository Alembic head: **`0002_submissions`**.
- Its parent is `0001_account_foundation`.

Render supports `preDeployCommand` for migration tasks, but none is configured here:

- <https://render.com/docs/blueprint-spec>
- <https://render.com/docs/deploys>

### Can the backend start with an outdated schema?

Yes.

Application startup:

- Creates a SQLAlchemy engine lazily.
- Imports the models.
- Does not call `Base.metadata.create_all()`.
- Does not run Alembic.
- Does not query or validate the schema.
- Exposes `/health`, which returns `{"status": "ok"}` without touching PostgreSQL.

The service can therefore build, start, and pass its health check while `alembic_version` remains at `0001_account_foundation` or while `submissions` is absent.

A confirmed successful `POST /api/submissions` against the same deployed version and the same Neon database proves that `submissions` existed at that time. It does not prove the currently deployed service points to the same database or that the schema still matches the ORM model.

## C. Safe read-only verification commands

The repository declares a free Render web-service plan. Free Render web services currently do not provide Dashboard Shell or SSH access. If the actual service is still free, the Shell page will be unavailable.

If a shell is available because the service was upgraded, run these commands from the repository root.

### 1. Current Alembic database revision

```sh
cd backend
alembic current
```

Expected if fully migrated:

```text
0002_submissions (head)
```

If it reports `0001_account_foundation`, production is behind. Empty output or an error concerning `alembic_version` suggests the database was not Alembic-stamped or is inaccessible.

### 2. Expected repository head

```sh
cd backend
alembic heads
```

Expected:

```text
0002_submissions (head)
```

Neither command prints the configured database URL under normal Alembic logging.

### 3. Check whether `submissions` exists

```sh
cd backend
python -c 'from sqlalchemy import inspect; from app.db.session import engine; print("submissions exists:", inspect(engine).has_table("submissions")); engine.dispose()'
```

Expected:

```text
submissions exists: True
```

### 4. Inspect columns

Run this only if the table exists:

```sh
cd backend
python -c 'from sqlalchemy import inspect; from app.db.session import engine; i=inspect(engine); print(*[(c["name"], str(c["type"]), c["nullable"], c.get("default")) for c in i.get_columns("submissions")], sep="\n"); engine.dispose()'
```

Expected columns:

```text
id
enrollment_id
total_revenue
total_unfinished_requests
total_unfinished_value
warnings_count
submitted_at
```

### 5. Inspect constraints and indexes

Primary key:

```sh
cd backend
python -c 'from sqlalchemy import inspect; from app.db.session import engine; i=inspect(engine); print(i.get_pk_constraint("submissions")); engine.dispose()'
```

Foreign keys:

```sh
cd backend
python -c 'from sqlalchemy import inspect; from app.db.session import engine; i=inspect(engine); print(*i.get_foreign_keys("submissions"), sep="\n"); engine.dispose()'
```

Unique constraints:

```sh
cd backend
python -c 'from sqlalchemy import inspect; from app.db.session import engine; i=inspect(engine); print(i.get_unique_constraints("submissions")); engine.dispose()'
```

Indexes:

```sh
cd backend
python -c 'from sqlalchemy import inspect; from app.db.session import engine; i=inspect(engine); print(*i.get_indexes("submissions"), sep="\n"); engine.dispose()'
```

Expected important objects:

```text
pk_submissions
fk_submissions_enrollment_id_enrollments
ix_submissions_enrollment_id
```

There should be no unique constraint on `enrollment_id`.

### Neon SQL Editor alternative

If Render Shell is unavailable, these queries are safe to run in the Neon SQL Editor.

Current revision:

```sql
SELECT version_num
FROM alembic_version;
```

Table existence:

```sql
SELECT to_regclass('public.submissions') AS submissions_table;
```

Columns:

```sql
SELECT
    ordinal_position,
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'submissions'
ORDER BY ordinal_position;
```

Constraints:

```sql
SELECT
    tc.constraint_name,
    tc.constraint_type,
    kcu.column_name,
    ccu.table_name AS referenced_table,
    ccu.column_name AS referenced_column
FROM information_schema.table_constraints AS tc
LEFT JOIN information_schema.key_column_usage AS kcu
  ON tc.constraint_catalog = kcu.constraint_catalog
 AND tc.constraint_schema = kcu.constraint_schema
 AND tc.constraint_name = kcu.constraint_name
LEFT JOIN information_schema.constraint_column_usage AS ccu
  ON tc.constraint_catalog = ccu.constraint_catalog
 AND tc.constraint_schema = ccu.constraint_schema
 AND tc.constraint_name = ccu.constraint_name
WHERE tc.table_schema = 'public'
  AND tc.table_name = 'submissions'
ORDER BY tc.constraint_name, kcu.ordinal_position;
```

Indexes:

```sql
SELECT indexname, indexdef
FROM pg_indexes
WHERE schemaname = 'public'
  AND tablename = 'submissions'
ORDER BY indexname;
```

These are metadata reads only. They do not modify or migrate the database.

## D. Student B database prerequisites

The ownership chain is:

```text
users.id
   -> enrollments.user_id
enrollments.id
   -> enrollments.course_id
course_instances.id
   -> submissions.enrollment_id
submissions
```

Before submission can reach `db.commit()`, Student B must satisfy the following conditions.

### User

- A `users` row matches the authenticated `user_id`.
- `is_active = true`.
- `role = student`.

### Enrollment

- An `enrollments` row matches the authenticated `enrollment_id`.
- `enrollment.user_id` matches the JWT `user_id`.
- `enrollment.course_id` matches the JWT `course_id`.
- `status = active`.
- Nickname is not null.
- `activation_used_at` is not null.
- `activation_code_hash` is null.

### Course

- A `course_instances` row matches the JWT `course_id`.
- `is_active = true`.

### Submission

The frontend supplies only:

```json
{
  "policy_code": "...",
  "params": {}
}
```

It does not supply:

- `student_id`
- `user_id`
- `course_id`
- `enrollment_id`
- `submission_id`
- Revenue or payoff totals

The JWT cookie contains `user_id`, `course_id`, and `enrollment_id`. The backend validates those claims against PostgreSQL.

The submitted row uses:

```python
enrollment_id=context.enrollment.id
```

The submission UUID is generated by SQLAlchemy/Python. All result totals are recomputed by the backend.

### Student-specific scenarios

#### Valid login but inconsistent enrollment

Database foreign keys and authentication make this unlikely. Login joins the enrollment, user, and course. A malformed enum value or schema drift could still raise an unhandled database error.

#### Student B is enrolled in a different course

This is valid and does not inherently cause an error. Student B's login course selects a course-scoped enrollment, and the submission belongs to that enrollment.

#### Stale or inactive enrollment

Each authenticated submission rereads the enrollment. This should fail with structured `401 Authentication required`, not a plain 500.

#### Deleted course or user

Normal `ON DELETE RESTRICT` constraints prevent deletion while an enrollment references the record.

#### Deleted enrollment

Deletion is possible only if nothing references the enrollment. A rare race in which it is deleted after authentication but before the insert could cause `ForeignKeyViolation`.

#### Nickname or status

They affect authentication eligibility. Once `require_student` succeeds, they are not copied into the submission and cannot directly violate a submission constraint.

#### `/api/auth/me` passes but commit fails

This is possible because authentication success does not validate the `submissions` table, its migration state, or database write health. A concurrent enrollment deletion or write-specific database problem could also intervene.

#### Simulator works but submission authentication is bad

This is possible because `/api/simulate/month` is not backend-authenticated. Successfully running a month proves the simulation endpoint works, but it does not prove the submission cookie, database authentication query, or write path works.

A useful non-secret check immediately before reproduction is the browser Network entry for:

```text
GET /api/auth/me
```

It should return `200`. If submission then returns `500`, authentication probably succeeded and the failure is later in the full-year calculation or database write.

## E. Most likely causes ranked

### 1. Unhandled PostgreSQL schema or write error at `db.commit()`

Most likely code boundary: `backend/app/routers/submissions.py:53`.

The endpoint has no `SQLAlchemyError` handling or rollback. A missing table, mismatched column, foreign-key failure, or another write exception becomes the plain HTTP 500 shown by the frontend.

Migration drift is particularly plausible because production never automatically runs Alembic. It becomes less likely if Student A's confirmed success occurred against the exact same deployment and database.

### 2. Transient Neon or pooled-connection failure during commit or refresh

Examples include:

- Closed SSL connection.
- Connection timeout.
- Neon restart.
- Pooler interruption.

These exceptions also escape the route and become plain 500 responses. If Student B fails every time while Student A can still submit now, this cause moves lower.

### 3. Full-year simulation failure specific to Student B's current policy

Submission runs all 12 months in one request, while Student B may only have tested individual months.

Ordinary policy exceptions and invalid return values are converted to warnings and should not cause 500. Remaining possibilities include:

- Resource exhaustion.
- Pathological computation.
- An engine-level exception outside the protected policy call.
- Stateful policy behavior that appears only during a continuous 12-month run.

If Student B repeatedly fails with one policy but succeeds after using the untouched template policy, this cause becomes substantially more likely. The policy source is not needed unless the traceback specifically implicates it.

### 4. Authentication database query raises an unhandled database exception

A connection error, unexpected enum value, or schema mismatch while `get_auth_context` queries the enrollment can produce a 500. Missing, inactive, stale, or mismatched claims normally produce a 401 instead.

Checking that `/api/auth/me` returns 200 immediately before submission helps distinguish this case.

### 5. Enrollment deleted between authentication and insert

This could produce `ForeignKeyViolation`, but it requires a narrow concurrent race. Normal foreign keys prevent dangling enrollment-to-user or enrollment-to-course references.

### 6. `db.refresh()` or response serialization failure after a successful insert

This is possible but unlikely. In this case, the browser can receive a 500 even though the submission row committed. Instructor Progress may show Student B's new row despite the frontend error.

### Effectively ruled out

- Repeated-submission uniqueness violation.
- Duplicate student/session/month key.
- Missing simulation-session row.
- Missing frontend course ID.
- Client-generated duplicate submission ID.
- Nickname uniqueness during submission.

None of those constraints or inputs exists on the current submission path.
