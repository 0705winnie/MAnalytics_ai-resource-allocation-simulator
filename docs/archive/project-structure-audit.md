> **Archived.** This audit describes the codebase at commit `0b7c0f4`,
> before the account/course/authentication system existed. Statements below
> such as "no active database layer exists" and "no authentication or
> authorization implementation" are no longer true. For the current
> architecture, setup, and instructor/student workflow, see the root
> `README.md`. Kept for history only — see `docs/archive/README.md`.

# Project Structure Audit

**Audited branch:** `integration/main-dashboard`  
**Audited commit:** `0b7c0f4`  
**Specification:** `docs/account-system-design.md` (currently untracked)

## 1. Root structure

| Path | Purpose |
|---|---|
| `backend/` | FastAPI application, simulation and AI services, Python dependencies, and pytest tests. |
| `src/` | React/TypeScript frontend plus inactive Python exploration/reference code. |
| `data/generated/` | Offline-generated historical request and summary CSV files; not application persistence. |
| `outputs/figures/` | Offline-generated PNG charts; not used by the active dashboard. |
| `public/` | Vite static assets, currently `public/favicon.svg`. |
| `docs/` | Design and audit documents. |
| `index.html` | Browser shell; loads `/src/main.tsx`. |
| `package.json`, `package-lock.json` | Frontend dependencies and npm scripts. |
| `vite.config.ts` | Vite React configuration and development `/api` proxy. |
| `tailwind.config.js`, `postcss.config.js` | Tailwind theme and CSS processing. |
| `tsconfig.json` | Strict TypeScript compiler configuration. |
| `requirements.txt` | Redirects installation to `backend/requirements.txt`. |
| `.env.example` | Environment-variable name template for LLM and CORS settings. |
| `.gitignore` | Python, Node, environment, cache, build, and OS exclusions. |
| `README.md` | Current setup and architecture documentation. |
| `HANDOVER.md` | Stale handover for a different implementation; it references absent routes, files, SQLite, and JSON persistence. |
| `src/simulator/.gitkeep` | Empty placeholder superseded by `backend/app/services/simulation_engine.py`. |

## 2. Frontend

### Stack

- React 18.3.1 and React DOM 18.3.1.
- TypeScript 5.6.3 with strict checking.
- Vite 8.1.0.
- Tailwind CSS 3.4.19 with PostCSS and Autoprefixer.
- Recharts 2.15.4 for active charts.
- `@monaco-editor/react`, Framer Motion, Lucide React, React Markdown, and `remark-gfm` are installed but unused by current frontend source.
- No React Router, Redux, Zustand, Context-based global store, or query library.

### Entry files and navigation

1. `index.html` provides `#root` and loads `/src/main.tsx`.
2. `src/main.tsx:createRoot()` renders `App` under `StrictMode`.
3. `src/App.tsx:App()` owns page selection and cross-page state.

There are no URL routes. `src/components/NavBar.tsx:Page` is `1 | 2 | 3 | 4`; `NavBar()` changes `App.currentPage`.

| Page | Component | Responsibility |
|---|---|---|
| `1` — Introduction | `src/pages/IntroDataPage.tsx:IntroDataPage()` | Narrative, system parameters, and static historical-data charts. |
| `2` — Policy & AI | `src/pages/PolicyAIPage.tsx:PolicyAIPage()` | Policy textarea, parameter editor, in-memory AI chat, and latest-month context. |
| `3` — Simulation | `src/pages/SimulationPage.tsx:SimulationPage()` | Sequential monthly execution, results, warnings, benchmarks, reset, and history save. |
| `4` — History | `src/pages/LeaderboardPage.tsx:LeaderboardPage()` | Browser-local identity and history plus mocked classmates. |

The only standalone shared UI component is `src/components/NavBar.tsx:NavBar()`. Helpers including `SectionCard`, `StatTile`, `MonthStepper`, `BenchmarkComparisonTable`, and `ParamsEditor` are local to page files. The policy editor is a `<textarea>`, not Monaco.

### State management

`src/App.tsx:App()` uses React `useState` for:

- `currentPage`
- `policyCode`
- `policyParams`
- AI `messages`
- LLM `provider`
- `completedMonths`
- browser-generated `currentUser`
- `submissionHistory`

Relevant functions:

- `src/App.tsx:handleMonthCompleted()` appends a monthly result.
- `src/App.tsx:handleResetSession()` clears active monthly results.
- `src/App.tsx:handleSaveSubmission()` prepends and persists a saved run.
- `src/pages/SimulationPage.tsx:runMonth()` submits the next sequential month.
- `src/pages/SimulationPage.tsx:resetSession()` discards the active session.
- `src/pages/SimulationPage.tsx:saveToHistory()` aggregates and saves the current partial or complete run.

Active session progress, policy edits, parameters, and chat disappear on refresh.

### API client

`src/lib/api.ts` defines:

- `postChat()` → `POST /api/ai-assistant`
- `postSimulate()` → `POST /api/simulate`
- `postSimulateMonth()` → `POST /api/simulate/month`

`vite.config.ts` proxies `/api` to the FastAPI development server and strips the prefix. The actual FastAPI routes do not use `/api`.

## 3. `localStorage`

All executable use is in `src/lib/storage.ts`.

| Key | Functions | Stored data |
|---|---|---|
| `currentUser` | `getOrCreateCurrentUser()` | `{ userId, anonymousName, createdAt }`; generated independently per browser. |
| `submissionHistory` | `loadSubmissionHistory()`, `saveSubmissionHistory()` | `Submission[]`: aggregated result, generated ID, timestamp, policy-code snapshot, and parameters. |

`createSubmission()` creates saved-run objects.

Limitations:

- `completedMonths`, policy drafts, parameters, and chat are not persisted.
- Saved histories may be partial runs.
- Only the policy present at save time is stored; policies used for earlier months are not recoverable after between-month edits.
- Clearing browser storage removes the identity and all saved histories.

## 4. Backend

### Entry point

`backend/app/main.py`:

- Loads the repository-root environment file.
- Creates the FastAPI `app`.
- Configures CORS through `CORS_ALLOW_ORIGINS`.
- Includes `ai_assistant.router` and `simulate.router`.
- Defines `health_check()` at `GET /health`.

The health route does not check a database or external service.

### Routes

| Route | Function | Behavior |
|---|---|---|
| `GET /health` | `backend/app/main.py:health_check()` | Returns basic process health. |
| `POST /ai-assistant` | `backend/app/routers/ai_assistant.py:chat()` | Selects an Azure or mock LLM client and returns an assistant response. |
| `POST /simulate` | `backend/app/routers/simulate.py:simulate()` | Compiles a policy, simulates 12 months, and runs all benchmark policies. |
| `POST /simulate/month` | `backend/app/routers/simulate.py:simulate_single_month()` | Compiles a policy and simulates one month plus same-month benchmarks. |

No account, authentication, course, instructor, session-history, export, submission, progress, or leaderboard routes exist.

### Services

| File | Important symbols | Responsibility |
|---|---|---|
| `backend/app/services/simulation_engine.py` | `_generate_month_arrivals()`, `_run_month()`, `_simulate_month_from_arrivals()`, `simulate_month()`, `run_full_simulation()` | Synthetic demand, admissions, departures, capacity, utilization, revenue, warnings, and aggregation. |
| `backend/app/services/policy_sandbox.py` | `compile_policy()`, `call_policy()` | Restricted in-process execution of submitted policy code; not adversarial-grade isolation. |
| `backend/app/services/baseline_policies.py` | Six policy functions, `BASELINE_POLICIES` | Fixed comparison policies. |
| `backend/app/services/hidden_environment.py` | Environment constants | Cluster capacity, demand, pricing, duration, seasonality, and seed definitions. |
| `backend/app/services/llm_client.py` | `BaseLLMClient`, `AzureLLMClient`, `MockLLMClient`, `get_llm_client()` | Active LLM integration and mock responses. |
| `backend/app/services/prompt_templates.py` | `build_system_prompt()` | Assistant system prompt and optional dashboard context. |

### Dependencies

`backend/requirements.txt` contains FastAPI, Uvicorn, OpenAI, python-dotenv, NumPy, and pytest.

It does not contain SQLAlchemy, psycopg, Alembic, pwdlib, PyJWT, pandas, or matplotlib. The offline data scripts import pandas and matplotlib, so those script dependencies are undeclared.

## 5. Database and persistence

No active database layer exists:

- No SQLAlchemy models or declarative base.
- No engine, session factory, database dependency, repository, or transactions.
- No PostgreSQL driver or database URL.
- No Alembic configuration or migrations.
- No active SQLite or JSON persistence.

Current lifetimes:

| Data | Current source of truth |
|---|---|
| Simulation execution | Backend memory for one request. |
| Cross-month session | React memory; the browser resubmits prior results. |
| Saved runs | Browser `localStorage`. |
| User identity | Browser `localStorage`. |
| Classmates/leaderboard | Hardcoded frontend constants. |
| Historical telemetry | Static TypeScript data and offline CSV artifacts. |

`backend/app/routers/simulate.py:SimulateMonthRequest.previous_months` accepts prior results from the client without verifying their shape or provenance. The client can alter prior-month history.

`HANDOVER.md` describes SQLite and JSON files that do not exist on this branch.

## 6. Business-concept file map

| Concept | Current files |
|---|---|
| Simulation sessions | `src/App.tsx` (`completedMonths`, `handleMonthCompleted()`, `handleResetSession()`); `src/pages/SimulationPage.tsx` (`runMonth()`, `resetSession()`). No backend session ID or record. |
| Monthly results | `backend/app/services/simulation_engine.py`; `backend/app/routers/simulate.py:MonthDetailResponse`; `src/types/simulation.ts:MonthDetailResult`; `src/pages/SimulationPage.tsx`. |
| Policies | `src/pages/PolicyAIPage.tsx:POLICY_TEMPLATE`, `PolicyAIPage()`; `src/App.tsx:policyCode`; `backend/app/services/policy_sandbox.py:compile_policy()`. No policy versions. |
| Warnings | `backend/app/services/simulation_engine.py:_run_month()` generates capped strings; `src/pages/SimulationPage.tsx` displays them; saved browser submissions include them. No structured run events. |
| Saved runs | `src/pages/SimulationPage.tsx:saveToHistory()`; `src/lib/storage.ts:createSubmission()`; `src/App.tsx:handleSaveSubmission()`; `submissionHistory` localStorage. |
| Accounts/profile | `src/lib/storage.ts:getOrCreateCurrentUser()`; `src/types/user.ts:CurrentUser`; `src/pages/LeaderboardPage.tsx`. Browser identity only. |
| Leaderboards | `src/pages/LeaderboardPage.tsx`; `MOCK_CLASSMATES` is hardcoded and rows are sorted by best revenue. |
| Historical data | `src/data/historicalData.ts`; `src/pages/IntroDataPage.tsx`; generation in `src/data/generate_historical_data.py`. |

Warnings lack severity, event type, payload, invalid-action count, and total-action count. `MAX_WARNINGS = 50` can also prevent complete event traceability.

## 7. Authentication and profiles

There is no authentication or authorization implementation:

- No login, logout, activation, reset, or `/auth/me`.
- No password or activation-code hashing.
- No cookies, access tokens, or server sessions.
- No authentication dependencies or middleware.
- No role, course, enrollment, or ownership checks.
- No protected frontend routes or instructor interface.

`src/types/user.ts:CurrentUser` contains only `userId`, `anonymousName`, and `createdAt`.

## 8. Differences from `docs/account-system-design.md`

| Design | Existing implementation |
|---|---|
| PostgreSQL source of truth | Browser memory and localStorage. |
| SQLAlchemy, psycopg, Alembic | Absent. |
| Users, courses, enrollments, reset tokens | Absent. |
| Roster-based account activation | Random browser identity. |
| Secure password and code hashes | No credentials. |
| HttpOnly authenticated session | No authentication. |
| Backend-derived ownership | Client submits policy, month, parameters, and prior history; no ownership. |
| Persistent simulation sessions | React state only. |
| Atomic monthly save | Monthly requests write nothing. |
| Exact policy version per month | Only the policy at history-save time is retained. |
| Required monthly schema | Missing explicit VIP fields, invalid-action counts, total-action counts, and policy-version linkage. |
| Structured run events | Capped warning strings only. |
| Practice and selected final runs | Local histories only; no type, eligibility, or final selection. |
| Cross-browser recovery | Impossible. |
| Same-stage leaderboard | Absent; benchmark policies are not student rankings. |
| Eligible final leaderboard | Mock local page only. |
| VIP admission and post-admission completion | UI computes completed VIP/all VIP arrivals only. |
| Invalid-action penalty | Invalid choices are rejected and warned, but not separately counted or scored. |
| URL routes and route protection | Numeric in-memory page selection. |
| Instructor tools and audit events | Absent. |
| CSV/JSON and policy export | Absent. |
| Stable account error codes | FastAPI validation or string `detail` responses only. |
| Development instructor seed | Absent. |
| Deployment/security configuration | CORS only; no database, cookies, HTTPS, or release configuration. |

The design explicitly rejects migration of prototype localStorage records. Existing `currentUser` and `submissionHistory` data should not be imported into PostgreSQL.

## 9. Phase 1 file plan

Phase 1 should establish PostgreSQL, SQLAlchemy, Alembic, the user/course/enrollment schema, and a development instructor seed. Business tables owned by later phases should be deferred unless the team deliberately chooses a full-schema first migration.

### Modify

| File | Change |
|---|---|
| `backend/requirements.txt` | Add SQLAlchemy 2.x, Alembic, psycopg, and `pwdlib[argon2]` if the instructor seed has a password. |
| `.env.example` | Add the `DATABASE_URL` variable name and any development seed variable names, without committed values. |
| `README.md` | Document PostgreSQL setup, migrations, downgrade policy, and instructor seeding. |
| `.gitignore` | Existing `.env` coverage is sufficient; change only if new local database or seed artifacts require exclusions. |
| `backend/app/main.py` | Optional database-readiness integration. Do not call `Base.metadata.create_all()`; Alembic must own schema creation. |

### Add

```text
backend/app/core/__init__.py
backend/app/core/config.py

backend/app/db/__init__.py
backend/app/db/base.py
backend/app/db/session.py

backend/app/models/__init__.py
backend/app/models/enums.py
backend/app/models/user.py
backend/app/models/course_instance.py
backend/app/models/enrollment.py

backend/alembic.ini
backend/alembic/env.py
backend/alembic/script.py.mako
backend/alembic/versions/0001_create_users_courses_enrollments.py

backend/scripts/__init__.py
backend/scripts/seed_instructor.py

backend/tests/test_database_config.py
backend/tests/test_account_models.py
backend/tests/test_migrations.py
backend/tests/test_seed_instructor.py
```

Responsibilities:

- `core/config.py`: validate database and environment settings.
- `db/base.py`: SQLAlchemy `DeclarativeBase` and deterministic constraint naming.
- `db/session.py`: psycopg engine, session factory, and future FastAPI `get_db()` dependency.
- `models/enums.py`: account-role and enrollment-status values.
- `models/user.py`: normalized unique Berkeley username, password hash, role, active state, timestamps.
- `models/course_instance.py`: unique course code, creator relationship, active state, timestamps.
- `models/enrollment.py`: course/user foreign keys, nickname normalization, activation hash/expiry/use timestamps, status, and required unique constraints.
- `alembic/env.py`: import the full model registry and obtain the database URL from configuration.
- Initial migration: create PostgreSQL types, tables, indexes, foreign keys, constraints, and timestamp defaults.
- `seed_instructor.py`: idempotently create a development instructor with a securely hashed password.

Later model files:

```text
backend/app/models/password_reset_token.py
backend/app/models/simulation_session.py
backend/app/models/monthly_result.py
backend/app/models/policy_version.py
backend/app/models/run_event.py
backend/app/models/final_submission.py
backend/app/models/admin_audit_event.py
```

## 10. Tests, commands, environment, and deployment

### Tests

| File | Coverage |
|---|---|
| `backend/tests/test_baseline_policies.py` | Baseline selection, feasibility, tie-breaking, and full-year execution. |
| `backend/tests/test_simulate_api.py` | Full-year endpoint, seed rejection, and default-seed equivalence. |
| `backend/tests/test_simulate_month.py` | Monthly shape, validation, reproducibility, resets, capacity, and history forwarding. |
| `backend/tests/test_simulate_month_api.py` | Monthly API validation, history forwarding, seed rejection, and regressions. |
| `backend/tests/test_simulation_engine.py` | Revenue, utilization, capacity safety, reproducibility, unfinished jobs, and policy warnings. |
| `backend/pytest.ini` | Sets `pythonpath = .` and `testpaths = tests`. |

There are no frontend, browser/E2E, database, authentication, authorization, leaderboard, or migration tests, and no CI workflow.

### Commands

```text
npm install
pip install -r backend/requirements.txt

npm run dev
npm run dev:api
npm run build
npm run preview

cd backend && pytest
npx tsc --noEmit

python src/data/generate_historical_data.py
```

### Environment variable names

Active backend:

- `LLM_PROVIDER`
- `AZURE_OPENAI_ENDPOINT`
- `AZURE_OPENAI_API_KEY`
- `AZURE_OPENAI_DEPLOYMENT`
- `AZURE_OPENAI_API_VERSION`
- `CORS_ALLOW_ORIGINS`

Inactive reference module `src/agent/llm_client.py` also recognizes:

- `OPENAI_PROVIDER`
- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `OPENAI_BASE_URL`

`DATABASE_URL`, signing-secret, cookie, and seed-account variables do not yet exist. The documented LLM default and `backend/app/services/llm_client.py:get_llm_client()` default are inconsistent.

### Deployment

No Dockerfile, Compose file, Kubernetes manifest, Procfile, cloud-host configuration, GitHub Actions workflow, production reverse proxy, migration release command, PostgreSQL service declaration, or production HTTPS/cookie configuration exists. Deployment-specific support is limited to configurable CORS.

## Recommended implementation order

1. Freeze ID types, normalization, PostgreSQL enum strategy, timestamp behavior, nickname uniqueness, foreign-key delete behavior, and constraint names.
2. Add database dependencies and `DATABASE_URL` configuration.
3. Add the SQLAlchemy base, engine/session factory, and `get_db()` dependency.
4. Implement `User`, `CourseInstance`, and `Enrollment` with database-enforced constraints.
5. Configure Alembic and create a reviewed initial migration; do not use `create_all()`.
6. Add database-model and migration tests.
7. Add the idempotent, securely hashed development instructor seed.
8. Update `.env.example` and `README.md`.
9. Verify migration upgrade from an empty database and downgrade back to empty.
10. Implement Phase 2 authentication and protected frontend URL routes.
11. Implement Phase 3 session, monthly-result, policy-version, run-event, and final-submission persistence in one monthly transaction.
12. Replace localStorage identity/history only after backend recovery APIs work; retain localStorage solely for permitted unsaved UI state.
