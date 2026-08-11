# Local Neon Investigation for Student B Submission HTTP 500

Date: 2026-08-10

Scope: determine whether the production `POST /api/submissions` HTTP 500 can be reproduced from the local development environment against the same Neon configuration.

No migrations, submission requests, or production database mutations were performed during this investigation.

## Current outcome

The production 500 cannot currently be reproduced from this workspace for two reasons:

1. No root `.env`, `backend/.env`, or externally injected database/authentication variables are present.
2. Calling `POST /api/submissions` against production would insert a row because the route calls `db.commit()`. That would violate the instruction not to modify production records.

The safe investigation path is:

1. Perform read-only schema and connection checks against production Neon.
2. Test the full-year simulation path without submitting.
3. Reproduce actual Student A and Student B submissions only against a Neon branch/clone or dedicated test database copied from production.

## 1. Safest local startup procedure

### Current local prerequisites

Observed in this workspace:

- Root `.env`: absent.
- `backend/.env`: absent.
- `DATABASE_URL`: not injected.
- `JWT_SECRET`: not injected.
- `node_modules`: absent.
- Required Python packages: installed.
- Local Python: 3.13.7.
- Repository Alembic head: `0002_submissions`.

Do not start Docker if the goal is to use Neon. The backend always uses exactly `DATABASE_URL`; there is no automatic localhost fallback.

### Required local configuration

Obtain the intended Neon connection URL through a secure channel from the deployment/database owner. Do not paste it into chat or terminal output.

For local browser testing, the effective configuration should contain:

```text
DATABASE_URL=<Neon pooled postgresql+psycopg URL>
JWT_SECRET=<local-only random value of at least 32 characters>
AUTH_COOKIE_SECURE=false
FRONTEND_ORIGIN=http://localhost:5173
DISABLE_LEGACY_PROXY_ROUTES=false
LLM_PROVIDER=mock
```

Important details:

- The local `JWT_SECRET` does not need to match Render. The local backend issues and validates its own cookies.
- `AUTH_COOKIE_SECURE=false` is needed for local HTTP.
- `DISABLE_LEGACY_PROXY_ROUTES=false` is needed because Vite strips `/api` before proxying.
- `LLM_PROVIDER=mock` avoids requiring Azure credentials and does not affect simulation or submission calculations.

### Variables not required for this reproduction

- `DATABASE_DIRECT_URL`: not read by the current runtime or Alembic environment.
- `TEST_DATABASE_URL`: only for destructive integration tests.
- `POSTGRES_*`: only relevant to local Docker/Compose.
- `DEV_INSTRUCTOR_*`: only for seeding.
- `AZURE_OPENAI_*`: unnecessary when `LLM_PROVIDER=mock`.
- `ACCESS_TOKEN_MINUTES` and `ACTIVATION_TOKEN_MINUTES`: have defaults.

### Dependency installation

Because `node_modules` is absent, the frontend cannot currently start. Installing dependencies modifies the local filesystem, so it was not run under the current read-only investigation constraint.

When local dependency installation is authorized, use:

```sh
npm ci --legacy-peer-deps
```

Use a disposable checkout if the present workspace must remain untouched.

### Start commands

After configuration and dependencies are available, use two terminals from the repository root.

Backend:

```sh
npm run dev:api
```

Expected address:

```text
http://127.0.0.1:8000
```

Frontend:

```sh
npm run dev
```

Expected address:

```text
http://localhost:5173
```

Do not run these commands during the production-data investigation:

```sh
docker compose up
alembic upgrade head
python -m scripts.seed_instructor
pytest
```

They are unnecessary or potentially mutating for this investigation.

## 2. Confirm required environment variables without printing values

Run this from the repository root after configuring the environment:

```sh
python3 -c 'import os; names=["DATABASE_URL","JWT_SECRET","AUTH_COOKIE_SECURE","FRONTEND_ORIGIN","DISABLE_LEGACY_PROXY_ROUTES","LLM_PROVIDER"]; print(*[(n + ": " + ("set" if os.environ.get(n) else "unset")) for n in names], sep="\n")'
```

If the repository root `.env` is used, checking through application settings is more accurate:

```sh
cd backend
python3 -c 'from app.core.config import get_database_settings,get_auth_settings; d=get_database_settings(); a=get_auth_settings(); print("DATABASE_URL: set"); print("JWT_SECRET:", "set" if a.jwt_secret else "unset"); print("AUTH_COOKIE_SECURE:", a.auth_cookie_secure); print("FRONTEND_ORIGIN configured:", bool(a.frontend_origin)); print("DISABLE_LEGACY_PROXY_ROUTES:", a.disable_legacy_proxy_routes)'
```

Neither command prints secret values.

## 3. Confirm the backend targets Neon instead of Docker PostgreSQL

Run from `backend/`:

```sh
python3 -c 'from sqlalchemy.engine import make_url; from app.core.config import get_database_settings; u=make_url(get_database_settings().database_url); h=(u.host or "").lower(); print("driver is postgresql+psycopg:", u.drivername=="postgresql+psycopg"); print("host is Neon:", h.endswith(".neon.tech")); print("host looks pooled:", "-pooler" in h); print("host is localhost:", h in {"localhost","127.0.0.1","::1"})'
```

For the intended configuration, expect:

```text
driver is postgresql+psycopg: True
host is Neon: True
host looks pooled: True
host is localhost: False
```

The backend engine is created directly from `database_settings.database_url` in `backend/app/db/session.py`. `POSTGRES_PORT` and Docker Compose do not override it.

A safe connectivity check is:

```sh
cd backend
python3 -c 'from sqlalchemy import text; from app.db.session import engine; c=engine.connect(); print("database SELECT 1:", c.scalar(text("SELECT 1"))); c.close(); engine.dispose()'
```

This reads only and prints no connection information.

## 4. Read-only Alembic and schema verification

### Current database revision

```sh
cd backend
alembic current
```

Expected:

```text
0002_submissions (head)
```

### Repository head

```sh
cd backend
alembic heads
```

Confirmed locally:

```text
0002_submissions (head)
```

### `submissions` table existence

```sh
cd backend
python3 -c 'from sqlalchemy import inspect; from app.db.session import engine; print("submissions exists:", inspect(engine).has_table("submissions")); engine.dispose()'
```

### `submissions` columns

```sh
cd backend
python3 -c 'from sqlalchemy import inspect; from app.db.session import engine; i=inspect(engine); print(*[(c["name"],str(c["type"]),c["nullable"],c.get("default")) for c in i.get_columns("submissions")],sep="\n"); engine.dispose()'
```

Expected names:

```text
id
enrollment_id
total_revenue
total_unfinished_requests
total_unfinished_value
warnings_count
submitted_at
```

### Constraints and indexes

```sh
cd backend
python3 -c 'from sqlalchemy import inspect; from app.db.session import engine; i=inspect(engine); print("PK:",i.get_pk_constraint("submissions")); print("FK:",i.get_foreign_keys("submissions")); print("UNIQUE:",i.get_unique_constraints("submissions")); print("INDEXES:",i.get_indexes("submissions")); engine.dispose()'
```

Expected important names:

```text
pk_submissions
fk_submissions_enrollment_id_enrollments
ix_submissions_enrollment_id
```

There should be no unique constraint preventing repeated submissions.

## 5. Safe Student A and Student B reproduction procedure

### Production database: allowed read-only actions

With the local backend pointed to production Neon, these actions do not modify PostgreSQL:

1. Start the backend.
2. Start the frontend.
3. Log in as Student A.
4. Verify `GET /api/auth/me` returns 200.
5. Run simulation months.
6. Log out.
7. Repeat for Student B.
8. Verify `GET /api/auth/me` returns 200.
9. Run simulation months.

Student login reads PostgreSQL and sets only a browser cookie. `/api/simulate/month` is stateless and does not write PostgreSQL.

Do not click **Submit Result** against production. The route calls `db.commit()` in `backend/app/routers/submissions.py` and creates a permanent submission row.

### Read-only policy-path isolation

A useful intermediate test is to run the same policy through the full-year `/api/simulate` endpoint. It invokes `run_full_simulation`, like submission does, but performs no database insert.

Interpretation:

- If Student B's full-year `/api/simulate` also returns 500, focus on policy or full-year simulation behavior.
- If it succeeds, the remaining difference is authentication or PostgreSQL insertion/refresh.

This does not fully reproduce submission, but it isolates the important non-database part safely.

### Actual submission reproduction

Use a Neon branch/clone or dedicated test database containing copies of:

- Student A's user.
- Student A's enrollment and course.
- Student B's user.
- Student B's enrollment and course.
- Matching schema and `alembic_version`.

Point local `DATABASE_URL` to that isolated database. Then:

1. Record the baseline submission counts in the clone.
2. Start the backend and frontend.
3. Log in as Student A.
4. Confirm `/api/auth/me` returns 200.
5. Run at least one month.
6. Click **Submit Result** once.
7. Expect `POST /api/submissions` to return 201.
8. Log out.
9. Log in as Student B.
10. Confirm `/api/auth/me` returns 200.
11. Run the same number of months.
12. Click **Submit Result** once.
13. Record the response and backend output.
14. Confirm only the isolated database received new rows.

This is the safe way to reproduce the complete commit path without changing production records.

## 6. Backend traceback to capture

Run the backend in its own terminal:

```sh
npm run dev:api
```

If Student B fails, capture all of the following.

### Request line

```text
"POST /submissions HTTP/1.1" 500 Internal Server Error
```

Because Vite strips `/api`, local Uvicorn will probably log `/submissions`, not `/api/submissions`.

### Exception block

Copy:

1. The `ERROR: Exception in ASGI application` line.
2. The complete traceback through the final exception line.
3. Every chained section beginning with:

   ```text
   During handling of the above exception...
   The above exception was the direct cause...
   ```

4. Frames mentioning:

   ```text
   app/routers/submissions.py
   app/core/auth.py
   run_full_simulation
   db.commit
   db.refresh
   sqlalchemy
   psycopg
   ```

5. Five terminal lines after the final exception.

Redact:

- Database URL, host, or user.
- Passwords.
- Cookies and JWTs.
- Policy source.
- SQL parameter values.
- Student UUIDs if desired.

Keep:

- Exception type and message.
- Constraint, table, and column names.
- Source filenames and line numbers.
- PostgreSQL SQLSTATE, if present.

Also check Instructor Progress after a 500 in the isolated database. If Student B's row exists, the insert committed and the failure occurred during `db.refresh()` or response serialization.

## 7. If local Student B submission succeeds but Render fails

Investigate these Render-only differences in order.

### 1. Different database or Neon branch

Render's `DATABASE_URL` may target another Neon project, branch, database, or role. Compare only safe metadata: Alembic revision, table existence, columns, and constraints.

### 2. Different deployed Git revision

Compare Render's deployed commit SHA with local commit `be80bc2`. An older deploy may contain a different model, route, or migration set.

### 3. Migration drift

Render does not automatically run Alembic. Local Neon may be at `0002_submissions` while Render's target database is at `0001_account_foundation`.

### 4. Dependency version drift

Backend requirements mostly specify lower bounds rather than exact versions. A fresh Render build can install newer FastAPI, Uvicorn, NumPy, SQLAlchemy, Alembic, or psycopg versions than local.

Compare `python --version` and `pip freeze` without exposing environment variables.

### 5. Python runtime difference

The repository has no `.python-version` or `runtime.txt`. Local Python is 3.13.7; Render may select a different version.

### 6. Render-to-Neon networking

Pooler behavior, SSL interruptions, connection limits, region latency, or transient Neon failures can affect Render while local access succeeds.

### 7. Render resource limits

The configured service uses a free instance. Full-year simulation may encounter CPU, memory, cold-start, or request-duration pressure not present locally.

### 8. Route topology

Local Vite rewrites `/api/submissions` to `/submissions`. Production sends `/api/submissions` directly with legacy proxy routes disabled. Both register the same handler, but this comparison confirms whether production is running the expected route configuration.

### 9. Cookie settings

Production uses `AUTH_COOKIE_SECURE=true`; local uses false. Cookie failures should normally produce a structured 401 rather than 500, so this is lower priority.

### 10. Concurrent production state

Enrollment modification, database maintenance, or a write race may exist only during the production request.

## Final conclusion

The local workspace is not currently configured with a Neon URL, so no same-database checks have run. The metadata commands in this report are safe. A real submission must wait for either:

1. Explicit authorization to create a production submission row, or
2. An isolated Neon branch/clone or dedicated test database.
