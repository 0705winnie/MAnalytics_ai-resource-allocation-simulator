# Online Database Migration Progress

## 1. Purpose

The project is moving from a PostgreSQL database running in local Docker to a
shared Neon PostgreSQL database. This is the first step toward:

- shared course and roster data;
- cross-device data access;
- instructor progress monitoring;
- same-stage and final leaderboards; and
- eventual online deployment of the FastAPI backend and React frontend.

Deploying only the database does not make the full application publicly
accessible. During this stage, the frontend and backend still run locally.

## 2. Current Architecture

```text
Local React/Vite Frontend
        |
        v
Local FastAPI Backend
        |
        v
Neon PostgreSQL Database
```

React/Vite and FastAPI still run locally, while PostgreSQL is being moved to
Neon. The backend database remains the source of truth. A later phase will
deploy the backend and frontend online.

## 3. Completed Work

### 3.1 PostgreSQL Driver and Configuration

- SQLAlchemy is used for database access.
- psycopg 3 is used as the PostgreSQL driver.
- Valid database URLs must begin with `postgresql+psycopg://`.
- Pydantic Settings loads the project-root `.env` file.
- `backend/app/core/config.py` validates the database URL driver.

### 3.2 Neon Connection Variables

- `DATABASE_URL`
  - Uses the Neon pooled connection.
  - Intended for normal FastAPI runtime queries.
- `DATABASE_DIRECT_URL`
  - Uses the Neon direct connection.
  - Intended for Alembic migrations, `pg_dump`, `pg_restore`, and maintenance
    operations.

Real connection URLs are not stored in this repository.

### 3.3 Local Configuration Validation

A local configuration check confirmed that:

- `DATABASE_URL` is loaded;
- the psycopg dialect is used;
- the target is Neon;
- the runtime URL is pooled; and
- SSL is required.

This configuration check did not establish that the complete application
workflow can connect to and use Neon. The actual Neon connection and full
read/write application workflow still require final verification.

### 3.4 Secret Protection

- `.env` is ignored.
- `.env.local-backup` is ignored through the `.env.*` rule.
- Database backup directories and dump files are ignored.
- `.env.example` contains placeholders only.
- Secrets must be configured locally or through a deployment platform's secret
  manager.

## 4. Database Migration Workflow

The intended migration flow is:

1. Back up the local Docker PostgreSQL database with `pg_dump`.
2. Create a Neon project, database, and role.
3. Restore the local dump into Neon using the direct connection.
4. Compare schemas, tables, and important row counts.
5. Configure the local FastAPI backend with the Neon pooled `DATABASE_URL`.
6. Confirm the backend can read and write cloud data.
7. Stop the local PostgreSQL container temporarily and retest.
8. Test shared data from a second machine.
9. Later deploy the FastAPI backend and React frontend.

Not every workflow step is complete. In particular, the actual Neon connection,
the full application workflow, and cross-device behavior still require final
verification.

## 5. Local Development Setup

1. Create a project-root `.env` from `.env.example`.
2. Add the real Neon pooled and direct URLs locally.
3. Install backend dependencies:

   ```bash
   python3 -m pip install -r backend/requirements.txt
   ```

4. Start the backend:

   ```bash
   npm run dev:api
   ```

5. Start the frontend:

   ```bash
   npm run dev
   ```

6. Open <http://localhost:5173>.

Real connection URLs must never be committed.

## 6. Safe Configuration Check

The following check validates expected URL properties without printing the
connection string:

```python
from backend.app.core.config import get_database_settings

settings = get_database_settings()
url = settings.database_url

print("Backend loaded DATABASE_URL:", bool(url))
print("Uses psycopg:", url.startswith("postgresql+psycopg://"))
print("Uses Neon:", "neon.tech" in url)
print("Looks pooled:", "-pooler" in url)
print("SSL required:", "sslmode=require" in url)
```
