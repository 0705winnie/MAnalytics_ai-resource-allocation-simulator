# AI-Assisted Online Resource Allocation Simulator

A teaching dashboard for an online adaptive resource-allocation module. Students
inspect historical operating data, write an admission-and-routing policy, use an
AI assistant to reason through ideas and debug code, then run their policy
month-by-month against a real discrete-event simulator and compare results
against benchmark policies.

The platform models a cloud service with 10 heterogeneous server clusters
with capacities from 12 to 20 server-units. It serves VIP / Standard /
Economy requests at different unit prices, with real
reusable capacity and departure dynamics — a job only earns revenue if it's
admitted **and** completes before month-end.

## Architecture

A React/TypeScript dashboard talks to a FastAPI backend over a `/api` proxy:

```text
backend/app/
  main.py                       # FastAPI entry point — CORS, router registration, /health
  routers/
    ai_assistant.py             # POST /ai-assistant
    simulate.py                 # POST /simulate, POST /simulate/month
  services/
    llm_client.py                # Azure + mock LLM clients; provider via LLM_PROVIDER
    prompt_templates.py          # System prompt builder (injects live dashboard context)
    policy_sandbox.py            # Restricted exec() of a student's admission_policy code
    simulation_engine.py         # Poisson arrivals, Gamma service times, capacity/departure tracking
    baseline_policies.py         # 6 benchmark policies for student-policy comparison
backend/tests/                  # pytest suite for the engine, sandbox, benchmarks, both endpoints

src/
  App.tsx                       # Owns page routing + all state shared across pages
  components/NavBar.tsx
  pages/
    IntroDataPage.tsx           # 01 — case narrative, system params, historical-data charts
    PolicyAIPage.tsx            # 02 — policy editor, params editor, AI assistant chat
    SimulationPage.tsx          # 03 — month stepper, run control, monthly + cumulative results
    LeaderboardPage.tsx         # 04 — local submission history + leaderboard
  lib/
    api.ts                      # fetch wrappers: postChat, postSimulate, postSimulateMonth
    storage.ts                  # localStorage-only user identity + submission history
  data/historicalData.ts        # Static historical summary data bundled for Page 1
```

### Reference material (not yet wired into the app)

A few files carry over from an earlier exploration branch and are kept as
inert reference material — nothing in `backend/` or `src/` imports them:

- `src/agent/` — a standalone (non-FastAPI) AI-assistant client with its own
  mock fallback and prompt templates. **Not the assistant the dashboard uses**
  (that's `backend/app/services/llm_client.py` — see below). Consolidating the
  useful parts of `src/agent/prompt_templates.py`'s guardrail text into the
  canonical implementation is planned as a separate follow-up.
- `src/data/explore_historical_data.py`, `outputs/figures/*.png` — exploratory
  plots and the script that generated them.
- `src/simulator/.gitkeep` — empty placeholder, superseded by
  `backend/app/services/simulation_engine.py`.

## Setup

**Backend** (Python 3.11+):

```bash
pip install -r backend/requirements.txt
# (the root requirements.txt just points here: pip install -r requirements.txt also works)
```

**Frontend** (Node 18+):

```bash
npm install
```

## Running locally

Two processes, run in separate terminals from the repo root:

```bash
npm run dev:api   # FastAPI on http://127.0.0.1:8000
npm run dev       # Vite dev server — proxies /api/* to the backend (see vite.config.ts)
```

Then open the Vite dev server URL in a browser.

## Environment / AI assistant configuration

Copy `.env.example` to `.env` (gitignored — never commit it):

```text
# "mock" works locally with no API key and no network calls.
LLM_PROVIDER=mock

# Required only when LLM_PROVIDER=azure:
AZURE_OPENAI_ENDPOINT=https://YOUR-RESOURCE-NAME.openai.azure.com/
AZURE_OPENAI_API_KEY=your-azure-api-key-here
AZURE_OPENAI_DEPLOYMENT=gpt-4o-mini
AZURE_OPENAI_API_VERSION=2024-02-01
```

With `LLM_PROVIDER=mock`, `POST /ai-assistant` returns scripted keyword-matched
teaching responses — no API key needed. Set `LLM_PROVIDER=azure` and fill in
the `AZURE_OPENAI_*` variables to use a real Azure OpenAI / AI Foundry model.
(Plain, non-Azure OpenAI is not currently supported — this is being evaluated
as a follow-up, see "Reference material" above.)

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
python src/data/generate_historical_data.py
```

This writes CSVs under `data/generated/` and figures under `outputs/figures/`.
