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
