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
  .env.example                      # Template for local mock/Azure AI assistant configuration
  requirements.txt                  # Repo-level Python dependencies for backend + data scripts

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
    app/
      main.py                       # FastAPI entry point: CORS, router registration, /health
      routers/
        ai_assistant.py             # POST /ai-assistant
        simulate.py                 # POST /simulate, POST /simulate/month
      services/
        hidden_environment.py       # Hidden ground-truth parameters for data + simulator
        simulation_engine.py        # Poisson arrivals, Gamma durations, capacity/departure tracking
        baseline_policies.py        # Benchmark policies for student-policy comparison
        policy_sandbox.py           # Restricted exec() of student admission_policy code
        llm_client.py               # Azure + mock LLM clients; provider via LLM_PROVIDER
        mock_agent.py               # Deterministic teaching assistant for mock mode
        prompt_templates.py         # Assistant system prompts and guardrails
    tests/
      test_baseline_policies.py
      test_simulation_engine.py
      test_simulate_api.py
      test_simulate_month.py
      test_simulate_month_api.py

  src/
    App.tsx                         # Owns page routing and state shared across pages
    main.tsx                        # React app bootstrap
    index.css                       # Tailwind layers and global styles
    components/
      NavBar.tsx                    # Dashboard navigation
    pages/
      IntroDataPage.tsx             # Case narrative, system params, historical-data charts
      PolicyAIPage.tsx              # Policy editor, params editor, AI assistant chat
      SimulationPage.tsx            # Month stepper, run control, monthly/cumulative results
      LeaderboardPage.tsx           # Local submission history and leaderboard view
    lib/
      api.ts                        # fetch wrappers: postChat, postSimulate, postSimulateMonth
      storage.ts                    # localStorage-only user identity + submission history
    data/
      historicalData.ts             # Static historical summary data bundled for Page 1
    types/
      simulation.ts                 # Frontend simulation-related types
      user.ts                       # Frontend user/submission types

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
    data_dictionary.md              # Historical-data field definitions
    formulation_memo.md             # Problem formulation and hidden-environment design
    project_report.md               # Draft project report
    student_tutorial.md             # Self-contained student guide
    instructor_notes.md             # Instructor/course setup notes

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

Create the dedicated test database idempotently:

```bash
docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname = '\''resource_allocation_test'\''" | grep -q 1 || createdb -U "$POSTGRES_USER" -O "$POSTGRES_USER" resource_allocation_test'
```

Destructive database tests refuse to run unless the database name in
`TEST_DATABASE_URL` ends exactly in `_test`. Never point `TEST_DATABASE_URL` at
the development database, a production database, or any database whose data
must be retained.

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

Two processes, run in separate terminals from the repo root:

```bash
npm run dev:api   # FastAPI on http://127.0.0.1:8000
npm run dev       # Vite dev server: proxies /api/* to the backend (see vite.config.ts)
```

Then open the Vite dev server URL in a browser.

On Windows, make sure Node.js is on your `PATH`. If PowerShell cannot find
`npm`, temporarily add it in the current terminal:

```powershell
$env:Path += ";C:\Program Files\nodejs"
```

## Environment / AI assistant configuration

Copy `.env.example` to `.env` (gitignored; never commit it):

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
