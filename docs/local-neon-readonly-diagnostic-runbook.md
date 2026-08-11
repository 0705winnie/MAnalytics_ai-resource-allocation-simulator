# Local Neon Read-Only Diagnostic Runbook

Date: 2026-08-10

Status: Part A, Step 1 — inspect local configuration without printing values.

Constraints:

- Do not modify application code or migrations.
- Do not run `alembic upgrade head`.
- Do not create test submissions against production.
- Database checks must be read-only.
- Full-year isolation must use `/api/simulate`, not `/api/submissions`.
- Proceed one command or action at a time.

## Where the backend expects `.env`

The backend expects the project-root file:

```text
/Users/starrism/Documents/GitHub/MAnalytics_ai-resource-allocation-simulator/.env
```

This is established in two places:

- `backend/app/core/config.py` defines `PROJECT_ROOT` and configures Pydantic Settings with `PROJECT_ROOT / ".env"`.
- `backend/app/main.py` calls `load_dotenv(PROJECT_ROOT / ".env")` before importing application configuration and routers.

The backend does not expect `backend/.env`.

Repository inspection found that the project-root `.env` is currently absent in the shared workspace and the relevant variables are not injected into the current Codex shell. The VS Code terminal may have a different environment, so Step 1 verifies its actual state.

## Part A — Step 1

Open a VS Code terminal at the repository root:

```text
/Users/starrism/Documents/GitHub/MAnalytics_ai-resource-allocation-simulator
```

Run this single command:

```sh
python3 -c 'import os; from pathlib import Path; from dotenv import dotenv_values; p=Path(".env"); f=dotenv_values(p) if p.is_file() else {}; names=["DATABASE_URL","JWT_SECRET","AUTH_COOKIE_SECURE","FRONTEND_ORIGIN","DISABLE_LEGACY_PROXY_ROUTES","LLM_PROVIDER"]; print("project-root .env exists:", p.is_file()); print(*[(n + ": " + ("configured" if os.environ.get(n) is not None or f.get(n) is not None else "not configured")) for n in names], sep="\n")'
```

This command prints only whether the file and variable names are configured. It does not print any values.

### Expected result based on current inspection

```text
project-root .env exists: False
DATABASE_URL: not configured
JWT_SECRET: not configured
AUTH_COOKIE_SECURE: not configured
FRONTEND_ORIGIN: not configured
DISABLE_LEGACY_PROXY_ROUTES: not configured
LLM_PROVIDER: not configured
```

If the VS Code output differs, its result takes precedence because that terminal may have injected environment variables not visible to Codex.

### Meaning of unexpected results

- `.env exists: True`: a local root configuration already exists; do not print or share its contents.
- A variable is `configured` while `.env` is absent: the variable is injected by the VS Code shell, launch configuration, or parent process.
- `DATABASE_URL` is configured: it still must be classified safely as Neon versus localhost in the next step; configured does not prove it targets Neon.
- `JWT_SECRET` is not configured: read-only database checks can still run, but local student login cannot issue an access cookie.

## Minimum configuration if `.env` is absent

For Part B read-only database verification, only this is strictly required:

```text
DATABASE_URL=<authorized Neon pooled URL using postgresql+psycopg>
```

For later local login and UI isolation, configure:

```text
DATABASE_URL=<authorized Neon pooled URL using postgresql+psycopg>
JWT_SECRET=<local-only random secret of at least 32 characters>
AUTH_COOKIE_SECURE=false
FRONTEND_ORIGIN=http://localhost:5173
DISABLE_LEGACY_PROXY_ROUTES=false
LLM_PROVIDER=mock
```

Notes:

- Obtain the Neon URL from the database/deployment owner through an approved secure channel.
- Do not paste the URL into chat, screenshots, shell output, Git, or committed files.
- A local-only JWT secret is sufficient; the production Render JWT secret is not required.
- The repository already ignores `.env`, but verify it remains untracked before any later Git operation.
- Do not configure `TEST_DATABASE_URL` to point at production Neon.

## Next step

Paste back only the Step 1 status output. Do not paste `.env` contents or variable values. The next command will safely classify `DATABASE_URL` as Neon versus localhost without printing its host or credentials.
