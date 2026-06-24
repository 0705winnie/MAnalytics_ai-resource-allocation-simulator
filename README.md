# AI Compute Dispatcher

A four-phase teaching simulator for GPU capacity planning under the newsvendor
model and routing under M/M/c-style queuing. Students iterate Telemetry →
Strategy → Simulator → Results across four quarters.

## Quick start

Requirements: Node 18+, Python 3.11+.

```bash
# 1. Frontend deps
npm install

# 2. Backend deps
cd backend && python3 -m pip install -r requirements.txt && cd ..

# 3. Seed the SQLite telemetry (730 days of synthetic demand)
#    Re-seed after changing the generator: append --reset.
cd backend && python3 -m scripts.seed_telemetry && cd ..

# 4. Run backend and frontend in two terminals
npm run dev:api   # FastAPI on :8000
npm run dev       # Vite on :5173 (proxies /api → :8000)
```

Open http://localhost:5173.

## Environment

Copy `.env.example` to `.env` and fill in your values. The `.env` file is gitignored — never commit it.

```
# Which provider to use — "mock" works locally with no API key.
LLM_PROVIDER=mock

# Required only when LLM_PROVIDER=azure:
AZURE_OPENAI_ENDPOINT=https://YOUR-RESOURCE-NAME.openai.azure.com/
AZURE_OPENAI_API_KEY=your-azure-api-key-here
AZURE_OPENAI_DEPLOYMENT=gpt-4o-mini
AZURE_OPENAI_API_VERSION=2024-02-01

VITE_API_BASE_URL=/api       # frontend → backend. /api works with the Vite proxy.
```

With `LLM_PROVIDER=mock` the `/ai-assistant` endpoint returns scripted replies — no API key needed. Set `LLM_PROVIDER=azure` and fill in the `AZURE_OPENAI_*` vars to use a real model.

## Layout

```
backend/app/
  main.py               # FastAPI entry point, CORS setup, router registration
  routers/
    ai_assistant.py     # POST /ai-assistant — receives student message, returns AI reply
  services/
    llm_client.py       # Azure + Mock LLM clients; provider selected via LLM_PROVIDER
    prompt_templates.py # System prompt builder (injects current dashboard context)
src/
  App.tsx                              # phase switching
  components/TelemetryRoom.tsx         # Phase 1 — read the demand data
  components/DualCoreWorkspace.tsx     # Phase 2 — strategy + AI dispatcher
  components/ChaosSimulator.tsx        # Phase 3 — month-by-month replay
  components/RadarLeaderboard.tsx      # Phase 4 — scoring
```

## Scoring (Phase 4)

Five dimensions, each scored 0–100:

| Dimension              | Formula                                  |
|------------------------|------------------------------------------|
| Capacity Accuracy      | 1 − \|N − 15\| / 15                      |
| VIP Protection Rate    | VIP served / VIP total                   |
| Peak Resilience        | peak-month profit / normal-month profit  |
| Cost Efficiency        | revenue / (compute + SLA penalty)        |
| Overage Control        | 1 − idle / total cost                    |

## End-to-end sanity check

`run_student_sim.py` exercises the full Q1→Q4 path against a running backend
and prints a quarterly P&L + radar scorecard. Useful as a smoke test:

```bash
npm run dev:api          # in one terminal
python3 run_student_sim.py
```

## Notes for graders / reviewers

- N is locked once on Phase 2 and carried across all four quarters
  (newsvendor: a single CapEx decision).
- Per-quarter levers `vip_multiplier` and `sla_target` are passed to the
  simulator and affect VIP revenue/penalty and the SLA-breach charge.
- The Strategy editor compiles `route_request(job, servers) -> int` in a
  restricted Python namespace (no `import`, no filesystem/network/env access).
  Errors fall back to Join-Shortest-Queue.
