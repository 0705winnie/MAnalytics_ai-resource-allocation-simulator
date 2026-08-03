# AI-Assisted Online Resource Allocation Simulator

A teaching dashboard for an online adaptive resource-allocation module. Students
inspect historical operating data, write an admission-and-routing policy, use an
AI assistant to reason through ideas and debug code, then run their policy
month-by-month against a real discrete-event simulator and compare results
against benchmark policies.

The platform models a cloud service with 10 heterogeneous server clusters
with capacities from 12 to 20 server-units. It serves VIP / Standard /
Economy requests at different unit prices, with real
reusable capacity and departure dynamics: a job only earns revenue if it's
admitted **and** completes before month-end.

## Architecture

A React/TypeScript dashboard talks to a FastAPI backend over a `/api` proxy:

```text
ai-resource-allocation-simulator/
  README.md                         # Project overview, setup, run, and test instructions
  .gitignore                        # Keeps local secrets, caches, and build artifacts out of git
  .env.example                      # Template for database, auth, and AI assistant configuration
  requirements.txt                  # Repo-level Python dependencies for backend + data scripts
  compose.yaml                      # Docker Compose service for local PostgreSQL

  package.json                      # Frontend scripts and JavaScript dependencies
  package-lock.json                 # Locked JavaScript dependency versions
  index.html                        # Vite app entry HTML
  vite.config.ts                    # Vite config and /api proxy to FastAPI
  tsconfig.json                     # TypeScript compiler config
  tailwind.config.js                # Tailwind theme and design tokens
  postcss.config.js                 # PostCSS/Tailwind processing config

  backend/
    requirements.txt                # Backend-only Python dependencies
    pytest.ini                      # Backend pytest configuration
    alembic.ini                     # Alembic configuration (script_location = backend/alembic)
    alembic/
      env.py                        # Migration environment; reads DATABASE_URL from app settings
      versions/                     # Migration scripts (0001_create_users_courses_enrollments.py, ...)
    scripts/
      seed_instructor.py            # Idempotent local development instructor seed
    app/
      main.py                       # FastAPI entry point: CORS, router registration, /health
      core/
        config.py                   # Typed settings: database, auth, dev-instructor-seed
        security.py                 # Argon2 password/one-time-secret hashing
        auth.py                     # JWT issuance/verification, access-cookie helpers
        activation_auth.py          # Activation-token issuance/verification helpers
      db/
        base.py                     # SQLAlchemy DeclarativeBase and metadata
        session.py                  # Engine, session factory, get_db() dependency
      models/
        user.py                     # User (global identity, password hash, role)
        course_instance.py          # CourseInstance (instructor-owned course/semester)
        enrollment.py                # Enrollment (course-scoped nickname, activation state)
        enums.py                    # Role and enrollment-status enums
      schemas/
        auth.py                     # Login/activation request-response schemas
        activation.py               # Activation verify/complete schemas
        instructor_enrollments.py   # Instructor roster/enrollment schemas
      routers/
        ai_assistant.py             # POST /ai-assistant
        simulate.py                 # POST /simulate, POST /simulate/month
        auth.py                     # Student/instructor login, /auth/me, logout
        activation.py                # Student activation verify + complete
        instructor_courses.py       # Instructor course create/list/detail
        instructor_roster.py        # Instructor roster CSV import
        instructor_enrollments.py   # Instructor student list/status/regeneration
      services/
        hidden_environment.py       # Hidden ground-truth parameters for data + simulator
        simulation_engine.py        # Poisson arrivals, Gamma durations, capacity/departure tracking
        baseline_policies.py        # Benchmark policies for student-policy comparison
        policy_sandbox.py           # Restricted exec() of student admission_policy code
        llm_client.py               # Azure + mock LLM clients; provider via LLM_PROVIDER
        mock_agent.py                # Deterministic teaching assistant for mock mode
        prompt_templates.py         # Assistant system prompts and guardrails
        activation_codes.py         # Activation-code generation/hash/verify
        activation_completion.py    # First-time activation transaction (password + nickname)
        activation_verification.py  # Activation-code verification transaction
        student_authentication.py   # Student login lookup and session issuance
        instructor_enrollments.py   # Instructor enrollment list/status/regeneration logic
        roster_imports.py           # Roster CSV parsing, validation, enrollment creation
    tests/
      conftest.py                   # TEST_DATABASE_URL safety guard for destructive DB tests
      test_baseline_policies.py, test_simulation_engine.py,
      test_simulate_api.py, test_simulate_month.py,
      test_simulate_month_api.py    # Simulator/AI-assistant tests (no database required)
      test_database_config.py, test_migrations.py,
      test_account_models.py, test_security.py,
      test_seed_instructor.py, test_auth.py,
      test_activation_auth.py, test_activation_codes.py,
      test_activation_completion.py, test_student_login.py,
      test_instructor_courses.py, test_instructor_roster.py,
      test_instructor_enrollments.py  # Database-backed auth/course/roster tests (need Postgres)

  src/
    App.tsx                         # Dashboard page state; mounted at /app/* behind student auth
    main.tsx                        # React app bootstrap: BrowserRouter + AuthProvider + AppRoutes
    index.css                       # Tailwind layers and global styles
    auth/
      AppRoutes.tsx                 # All frontend routes: login, activate, /app/*, /instructor/*
      AuthProvider.tsx              # Session state, login/logout/activation calls, /auth/me refresh
      ProtectedRoute.tsx            # Role-gated route wrapper + loading/unavailable screens
      api.ts                        # Auth fetch wrappers and typed AuthApiError
      types.ts                      # Auth request/response types
    instructor/
      api.ts                        # Instructor course/roster/enrollment fetch wrappers
      types.ts                      # Instructor-facing types
      CourseSectionNavigation.tsx, InstructorBreadcrumbs.tsx,
      InstructorRosterManagement.tsx  # Instructor UI building blocks
    components/
      NavBar.tsx                    # Dashboard navigation + course/nickname display + sign out
    pages/
      IntroDataPage.tsx             # Case narrative, system params, historical-data charts
      PolicyAIPage.tsx              # Policy editor, params editor, AI assistant chat
      SimulationPage.tsx            # Month stepper, run control, monthly/cumulative results
      LeaderboardPage.tsx           # Local submission history and leaderboard view
      StudentLoginPage.tsx          # Course code + Berkeley username + password login
      StudentActivationPage.tsx     # First-time activation: verify code, set password + nickname
      InstructorLoginPage.tsx       # Instructor username + password login
      InstructorLayout.tsx          # Instructor shell (nav) for nested /instructor routes
      InstructorCoursesPage.tsx     # List instructor's courses
      InstructorCourseCreatePage.tsx  # Create a new course instance
      InstructorCourseDetailPage.tsx  # Course detail, roster, enrollment management
      InstructorRosterImportPage.tsx  # Roster CSV upload + activation-code CSV download
    lib/
      api.ts                        # fetch wrappers: postChat, postSimulate, postSimulateMonth
      storage.ts                    # localStorage-only local prototype profile + submission history
    data/
      historicalData.ts             # Static historical summary data bundled for Page 1
    types/
      simulation.ts                 # Frontend simulation-related types
      user.ts                       # Frontend local-prototype-profile types (not real auth identity)

  scripts/
    data/
      generate_historical_data.py   # Generates historical request CSVs and frontend data
      validate_historical_data.py   # Validates generated CSVs and summary consistency
      explore_historical_data.py    # Produces exploratory plots and summary outputs
      calibrate_hidden_environment.py # Internal policy checks for hidden-environment tuning

  data/
    generated/
      historical_requests.csv       # Generated historical request-level data
      summary_by_month.csv          # Generated monthly summary table
      summary_by_type.csv           # Generated request-type summary table
      summary_by_month_type.csv     # Generated month/request-type summary table

  outputs/
    figures/
      requests_by_month.png
      requests_by_type.png
      requests_by_month_type.png
      duration_by_type.png
      required_units_by_type.png
      revenue_by_type.png
      completion_rate_by_type.png

  docs/
    account-system-design.md        # Confirmed requirements for the account/course/auth system
    account-system-progress.md      # Implementation progress log for the account system
    data_dictionary.md              # Historical-data field definitions
    formulation_memo.md             # Problem formulation and hidden-environment design
    project_report.md               # Draft project report
    student_tutorial.md             # Self-contained student guide
    instructor_notes.md             # Instructor/course setup notes and open implementation items
    archive/                        # Superseded documents kept for history; see archive/README.md

  public/
    favicon.svg                     # Dashboard favicon
```

## Setup

**Backend** (Python 3.11+):

```bash
pip install -r backend/requirements.txt
# Or install backend plus Stream A script dependencies from the repo root:
# pip install -r requirements.txt
```

**Frontend** (Node 18+):

```bash
npm install
```

### Environment variables reference

Copy `.env.example` to `.env` at the repo root (gitignored; never commit it)
and fill in the values below. Each is explained in more detail in the
sections that follow.

| Variable | Required for | Purpose |
|---|---|---|
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_PORT` | Local Postgres via Docker Compose | Credentials/port for the `db` service in `compose.yaml`. |
| `DATABASE_URL` | Backend startup (all routes, not just auth) | SQLAlchemy connection string for the development database; must use the `postgresql+psycopg` driver. |
| `TEST_DATABASE_URL` | Running `pytest` on database-backed tests | Separate connection string for destructive test runs; database name must end in `_test`. |
| `DEV_INSTRUCTOR_USERNAME`, `DEV_INSTRUCTOR_PASSWORD` | `python -m scripts.seed_instructor` | Local-only instructor account seed; password must be at least 12 characters. |
| `JWT_SECRET` | Backend startup | Signs access/activation tokens; must be at least 32 characters. |
| `AUTH_COOKIE_SECURE` | Backend startup | `false` for local HTTP development; must be `true` behind HTTPS. |
| `ACCESS_TOKEN_MINUTES` | Optional | Access-token lifetime; default 30, allowed range 5–1440. |
| `ACTIVATION_TOKEN_MINUTES` | Optional | Activation-session lifetime; default 10, allowed range 5–30. |
| `FRONTEND_ORIGIN` | Backend startup | The single origin allowed by CORS with credentials; `http://localhost:5173` for local dev. This is the variable that actually controls CORS — the older `CORS_ALLOW_ORIGINS` name still present in `.env.example` is not read by the current backend. |
| `LLM_PROVIDER` | AI assistant | `mock` (no API key, scripted responses) or `azure` (real Azure OpenAI). |
| `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_DEPLOYMENT`, `AZURE_OPENAI_API_VERSION` | Only when `LLM_PROVIDER=azure` | Azure OpenAI / AI Foundry credentials and deployment. |

### PostgreSQL for local development

Copy `.env.example` to `.env` and replace the development-only database
password before sharing or deploying the environment. `DATABASE_URL` is the
SQLAlchemy connection string used by the backend; it must use the
`postgresql+psycopg` driver and correspond to `POSTGRES_DB`, `POSTGRES_USER`,
`POSTGRES_PASSWORD`, and `POSTGRES_PORT`. The team-default host port is `5432`.

Before changing or stopping anything already using port `5432`, identify that
service and confirm whether it contains data that must be preserved. Developers
who already have a service on that port can set:

```text
POSTGRES_PORT=55432
```

When overriding the port, `DATABASE_URL` must use the same host port.
`TEST_DATABASE_URL` is the separate connection string used by destructive
database integration tests and must use that host port as well.

Start PostgreSQL and check its health:

```bash
docker compose up -d db
docker compose ps
```

Apply migrations to the development database (`DATABASE_URL`). This creates
the `users`, `course_instances`, and `enrollments` tables and must be run
before starting the backend or seeding an instructor:

```bash
cd backend && alembic upgrade head
```

Create the dedicated test database idempotently:

```bash
docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname = '\''resource_allocation_test'\''" | grep -q 1 || createdb -U "$POSTGRES_USER" -O "$POSTGRES_USER" resource_allocation_test'
```

Destructive database tests refuse to run unless the database name in
`TEST_DATABASE_URL` ends exactly in `_test`. Never point `TEST_DATABASE_URL` at
the development database, a production database, or any database whose data
must be retained. You do not need to run migrations against the test database
yourself — an autouse pytest fixture applies `alembic upgrade head` to
`TEST_DATABASE_URL` automatically at the start of each test module that needs
it.

Stop PostgreSQL without deleting its data:

```bash
docker compose down
```

Delete the named development volume only when intentionally resetting all
local database data:

```bash
docker compose down --volumes
```

The Compose file runs PostgreSQL only. The frontend and backend continue to run
as local processes.

### Local development instructor

The development instructor account is only for local development. Add its
credentials to the gitignored root `.env`; never commit that file:

```text
DEV_INSTRUCTOR_USERNAME=
DEV_INSTRUCTOR_PASSWORD=
```

After applying migrations, run the idempotent seed from `backend/`:

```bash
python -m scripts.seed_instructor
```

The username is trimmed and normalized to lowercase. Re-running the seed does
not create a duplicate account and does not reset an existing instructor
password. The development password must contain at least 12 characters. If the
username already belongs to a student or a disabled instructor, the seed fails
without changing that user.

### Instructor authentication

Set a random `JWT_SECRET` of at least 32 characters in the gitignored root
`.env`; never commit that file. Access tokens expire after 30 minutes by
default, configurable with `ACCESS_TOKEN_MINUTES`.

For local HTTP development, use:

```text
AUTH_COOKIE_SECURE=false
FRONTEND_ORIGIN=http://localhost:5173
```

HTTPS deployments must set `AUTH_COOKIE_SECURE=true`. The API stores the access
token only in an HttpOnly, SameSite=Lax cookie. Future state-changing APIs that
use this cookie must continue to evaluate and implement appropriate CSRF
protection.

Browser clients use `/api/auth/*`. The existing Vite development proxy removes
the `/api` prefix before forwarding requests, so FastAPI also registers the
internal `/auth/*` compatibility paths. These are two paths to the same
authentication handlers, not separate authentication systems.

Authenticated instructors can create and list course instances through
`/api/instructor/courses`, then retrieve an owned course by ID. Instructors can
only see courses they created. Course codes are globally unique without regard
to letter case or surrounding whitespace. As with authentication, Vite removes
the browser-facing `/api` prefix and forwards these requests to the same hidden
`/instructor/courses` compatibility handlers.

### Instructor roster import

An instructor can upload an owned, active course roster to
`POST /api/instructor/courses/{course_id}/roster/import` as
`multipart/form-data` using the field name `file`. The UTF-8 CSV must be no
larger than 1 MB, contain at most 1000 non-empty data rows, and have exactly one
column:

```csv
berkeley_username
yguo
abc123
wenchia
```

The response is a non-cacheable CSV download. A newly created enrollment's
plaintext activation code appears in that download once; only its secure hash
is stored. Existing enrollments are not changed and do not receive replacement
codes. Instructors must save the download securely and immediately. A lost
code cannot be recovered; a future Instructor regenerate feature must create a
new code and invalidate the old one.

The Vite proxy removes `/api`, so the backend also exposes the same handler at
`/instructor/courses/{course_id}/roster/import` without duplicating the import
system.

### Instructor enrollment management

Instructors can list students in an owned course and manage each course
enrollment through `/api/instructor/courses/{course_id}`. Disabling an
enrollment affects only that course and never disables the global user or the
student's enrollment in another course. Restoring a previously activated
enrollment returns it to `active`; an enrollment without a recorded activation
returns to `pending` without automatically issuing a code.

Activation codes can only be regenerated for pending students. Regeneration
immediately invalidates the old code, restarts the 14-day validity period, and
returns the new plaintext code once in a non-cacheable CSV download. Active
students must use the future password-reset flow instead of being reactivated.
The Vite proxy exposes the same handlers without the browser-facing `/api`
prefix.

### Student activation verification

`POST /api/auth/activate/verify` validates an active course, pending student
enrollment, and its one-time activation code. Successful verification sets a
separate HttpOnly, SameSite=Lax `ra_activation_token` cookie for 10 minutes by
default (`ACTIVATION_TOKEN_MINUTES`, allowed range 5–30). The token is bound to
the current activation-code hash, so regenerating, consuming, or clearing the
code immediately invalidates an older activation session. It does not create a
normal access session or consume the activation code.

Completing first-time activation creates a global User password when none
exists. When the same User activates another course, the existing global
password must be confirmed and is never replaced. The chosen nickname belongs
only to that course Enrollment, so another course can use a different
nickname. Successful completion consumes the one-time code, clears the
activation Cookie, and establishes a course-scoped Student access session.

Production deployments must rate-limit activation verification at the reverse
proxy or a shared-storage enforcement layer. A process-local counter is not
complete protection for multiple application instances.

### Student regular login

After first-time activation, a student signs in through
`POST /api/auth/student/login` with the course code, Berkeley username, and
global User password. The selected active Enrollment determines the
course-specific nickname and the scope of the Student access session. The
access token remains only in the existing HttpOnly cookie; it is not returned
in the response or stored in `localStorage`.

The Vite proxy exposes the same handler internally at `/auth/student/login`.
Production deployment must add shared or proxy-level login rate limiting during
the later security phase; this MVP does not treat a process-local counter as
complete protection.

## Running locally

The backend now requires PostgreSQL to start — `DATABASE_URL` is read as soon
as the FastAPI app is imported, so `npm run dev:api` will fail immediately
with a configuration error if Postgres isn't running and migrated yet, even if
you only intend to use the AI assistant or simulator. Before starting either
process for the first time, complete the [PostgreSQL setup](#postgresql-for-local-development)
above: copy `.env.example` to `.env`, `docker compose up -d db`, and
`alembic upgrade head`.

Once Postgres is running and migrated, two processes, run in separate
terminals from the repo root:

```bash
npm run dev:api   # FastAPI on http://127.0.0.1:8000
npm run dev       # Vite dev server: proxies /api/* to the backend (see vite.config.ts)
```

Then open the Vite dev server URL in a browser. It redirects to `/login` (or
`/instructor/login`) until you sign in — see
[Instructor and student workflow](#instructor-and-student-workflow) below for
how to reach the dashboard for the first time.

On Windows, make sure Node.js is on your `PATH`. If PowerShell cannot find
`npm`, temporarily add it in the current terminal:

```powershell
$env:Path += ";C:\Program Files\nodejs"
```

## Instructor and student workflow

This walks through reaching the dashboard for the first time on a freshly
migrated, empty database. All steps happen in the browser at the Vite dev
server URL unless noted otherwise.

1. **Seed a development instructor.** With `DEV_INSTRUCTOR_USERNAME` /
   `DEV_INSTRUCTOR_PASSWORD` set in `.env` and migrations applied, run
   `python -m scripts.seed_instructor` from `backend/` (see
   [Local development instructor](#local-development-instructor)).
2. **Instructor logs in.** Visit `/instructor/login` and sign in with the
   seeded username/password. This sets an HttpOnly instructor session cookie
   and redirects to `/instructor/courses`.
3. **Instructor creates a course.** From `/instructor/courses`, create a new
   course instance with a unique course code (e.g. `IEOR150-Fall2026`).
4. **Instructor imports a roster.** Open the new course and import a
   one-column `berkeley_username` CSV (see
   [Instructor roster import](#instructor-roster-import)). The response is a
   CSV download containing each new enrollment's one-time plaintext
   activation code — save it immediately; it cannot be recovered later.
5. **Student activates their account.** A student visits `/activate` and
   enters the course code, their Berkeley username, and the activation code
   from that CSV, then chooses a password and a leaderboard nickname. This
   creates their global `User` password (or confirms it, if they already have
   one from another course) and signs them in immediately.
6. **Student reaches the dashboard.** After activation, the student is
   redirected to `/app`, the same four-page simulator dashboard (Historical
   Data → Policy & AI → Simulation → Leaderboard) described above.
7. **Student returns later.** On a future visit, the student signs in
   directly at `/login` with the course code, Berkeley username, and the
   password they chose during activation — no activation code needed again.

Both instructor and student sessions are plain HttpOnly cookies; signing out
uses the "Sign Out" control in the dashboard nav bar (student) or the
instructor layout (instructor).

## Environment / AI assistant configuration

The `LLM_PROVIDER`/`AZURE_OPENAI_*` variables were already added to `.env` in
[Setup](#environment-variables-reference) above; this section covers what
they do:

```text
# "mock" works locally with no API key and no network calls.
LLM_PROVIDER=mock

# Required only when LLM_PROVIDER=azure:
AZURE_OPENAI_ENDPOINT=https://YOUR-RESOURCE-NAME.openai.azure.com/openai/v1
AZURE_OPENAI_API_KEY=your-azure-api-key-here
AZURE_OPENAI_DEPLOYMENT=gpt-4.1-mini
AZURE_OPENAI_API_VERSION=v1
```

With `LLM_PROVIDER=mock`, `POST /ai-assistant` returns scripted keyword-matched
teaching responses; no API key needed. Set `LLM_PROVIDER=azure` and fill in
the `AZURE_OPENAI_*` variables to use a real Azure OpenAI / AI Foundry model.
The backend supports the Azure `/openai/v1` endpoint form shown above.
(Plain, non-Azure OpenAI is not currently supported.)

## Testing

```bash
cd backend && pytest
```

The simulator/AI-assistant tests run with no database. The auth/course/roster
tests require `DATABASE_URL` and `TEST_DATABASE_URL` to be set and PostgreSQL
to be running (see [PostgreSQL for local development](#postgresql-for-local-development));
without it they fail at collection or fixture setup with a
`TEST_DATABASE_URL is required` error rather than a code failure.

```bash
npx tsc --noEmit
npm run build
```

## Historical data generation

The dataset shown on Page 1 (`src/data/historicalData.ts`) was generated
offline from a hidden ground-truth environment and is bundled as static data
rather than served by an endpoint:

```bash
python scripts/data/generate_historical_data.py
```

This writes CSVs under `data/generated/` and figures under `outputs/figures/`.
