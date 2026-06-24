# AI Compute Dispatcher — Handover

This is a "how does it work" handover for whoever picks up the project next. The README already covers how to run it; this doc focuses on **how the internals fit together, why things are designed the way they are, and what to watch out for when changing them**.

---

## 1. One-line framing

A four-phase teaching simulator for GPU capacity planning and request routing. A student plays the ops lead of an AI inference business and makes two kinds of decisions over a simulated year (4 quarters × 3 months = 12 months):

1. **Capacity (Newsvendor)** — how many GPUs (N) to buy up front, and whether to add more each quarter.
2. **Routing (M/M/c-style queuing)** — which GPU each incoming request goes to.

After the year is done, a 5-dimensional radar chart scores the student.

---

## 2. The four phases (teaching flow)

The student walks down this line (matches the top nav `01–04`):

| Phase | File | What the student does |
|---|---|---|
| **01 Telemetry** | [TelemetryRoom.tsx](src/components/TelemetryRoom.tsx) | Reads 730 days of historical demand (with holiday peaks / maintenance troughs), then picks and locks initial N₀ |
| **02 Strategy** | [DualCoreWorkspace.tsx](src/components/DualCoreWorkspace.tsx) | Writes `route_request(job, servers)` on the left (Monaco editor), chats with the AI Dispatcher on the right; sets the current quarter's `vip_multiplier` and `sla_target`; may purchase extra GPUs for Q2/Q3/Q4 |
| **03 Simulator** | [ChaosSimulator.tsx](src/components/ChaosSimulator.tsx) | Runs the 3 months of the current quarter on the backend; reads monthly P&L, drops, SLA breaches |
| **04 Results** | [RadarLeaderboard.tsx](src/components/RadarLeaderboard.tsx) | After 12 months are done, shows the 5-dim radar score |

Phases 02 and 03 loop Q1 → Q2 → Q3 → Q4. At the end of each quarter, `advanceQuarter()` in `App.tsx` flushes `pendingMonths` into `completedMonths`, then snaps back to Phase 02 for the next quarter's setup.

**The state machine lives in [App.tsx](src/App.tsx)** — everything cross-phase (initialN, quarterN, procurementSpent, currentQ, qStrategy, routingCode, messages, completedMonths) is lifted up there. Children only receive props. The reason: Phase 02 actually unmounts and remounts on every quarter transition, so any state held inside it would be lost.

---

## 3. Architecture at a glance

```
┌──────────────── Frontend (Vite + React 18 + Tailwind) ────────────────┐
│  src/App.tsx           ← phase switching + cross-phase global state    │
│  src/components/*.tsx  ← UI for the 4 phases                           │
│  src/api.ts            ← fetch wrapper; defaults to /api proxy         │
└──────────────────────────────┬────────────────────────────────────────┘
                               │  /api/* (Vite dev proxy → :8000)
                               ▼
┌──────────────── Backend (FastAPI + uvicorn :8000) ────────────────────┐
│  app/main.py           ← registers 4 routers + CORS + DB init         │
│  app/routers/                                                          │
│    telemetry.py        ← /telemetry/{logs,history,stats}              │
│    agent.py            ← /agent/chat (OpenAI or mock)                 │
│    simulate.py         ← /simulate/run (the core entry point)         │
│    results.py          ← /results/{summary,scenario,run-log}          │
│  app/core/                                                             │
│    des_engine.py       ← discrete-event sim + per-server queues       │
│    storage.py          ← SQLite + JSON files                          │
│    demand_generator.py ← Poisson demand sampler (used only by script) │
│  app/services/                                                         │
│    openai_client.py    ← real OpenAI client                           │
│    llm_mock.py         ← fixed mock reply when no API key is set      │
│  backend/scripts/seed_telemetry.py ← generates the 730 days of data   │
└────────────────────────────────────────────────────────────────────────┘
                               │
                               ▼
                ┌───────── backend/data/ ─────────┐
                │  telemetry.db    (SQLite)        │
                │    api_logs      ← all request logs │
                │    daily_demand  ← 730-day seed     │
                │  scenario_config.json ← last run's strategy │
                │  run_log.json         ← last run's result    │
                └─────────────────────────────────┘
```

No external DB, no auth, no background job queue. The whole thing runs end-to-end on a single laptop.

---

## 4. The core: the DES engine

**This is the single most important file in the project.** Understand this and you understand 80% of the system. Code: [backend/app/core/des_engine.py](backend/app/core/des_engine.py).

### 4.1 Simulation granularity

- **Time unit**: 1 day = 1 simulation tick
- **One month** = 30 days (constant `_ROUNDS = 30`)
- **One quarter** = 3 months = 90 days

### 4.2 What a month-long simulation does

`DESEngine.run_month(month, strategy, n_gpus, routing_fn)` calls `_run_des()`, which:

1. **Generates the arrival stream**: per day, sample job count from `Poisson(λ_queries)`; for each job, sample tokens from `Poisson(λ_query_length)` and assign a tier by historical proportions (VIP 18% / Premium 35% / Standard 47%). A random `offset ∈ [0,1)` puts each job at a sub-day arrival time.
2. **Sort** all jobs by arrival_time ascending.
3. **Process them one by one**: for each job,
   - Compute every server's current queue length as `ceil(remaining_work / avg_service_time)`;
   - Pass the `ServerState` list to `routing_fn(job, servers)`, which picks a server;
   - If that server's queue is full (≥ `queue_capacity=10`), **drop the job** and charge a tier-specific penalty;
   - Otherwise append the job to that server, update `server_next_free[chosen]`;
   - If `t_end ≤ T(=30)`, count it as completed and credit tier revenue.
4. **SLA breach charge**: at month end, if `served_frac < sla_target`, charge an extra `(sla_target − served_frac) × sla_breach_cost × n_arrivals`.

### 4.3 The numbers that matter (steady state)

Defaults give `λ=18 jobs/day`, `avg_tokens=1200`, `service_rate=1200 tokens/day`, `n_gpus=20` → ρ ≈ 0.9 per server (heavy load but stable). Drop below ~18 servers and the cluster tips into overload — queues fill, drops pile up, revenue collapses. That tipping point is exactly the tension the student is supposed to feel.

### 4.4 How the student's routing function gets executed

`_build_routing_fn(code)` in [simulate.py:27-58](backend/app/routers/simulate.py) compiles the student's Python string inside a **whitelisted sandbox**:

- Exposes only `math`, `random`, and a small set of safe builtins (no `import`, no filesystem, no network, no env).
- Student defines `route_request(job, servers) -> int`.
- Any failure (compile error, runtime error, non-int return) falls back to JSQ (Join-Shortest-Queue).
- The return value is clamped to `[0, n_gpus-1]`.

⚠️ **This sandbox is not adversarial-grade.** A motivated student can escape the builtin whitelist with enough patience. Fine for classroom use; if you ever expose this to the public internet, replace it with subprocess/container isolation.

---

## 5. Data flow and persistence

### 5.1 SQLite (`backend/data/telemetry.db`)

Two tables:

- **`daily_demand`** — 730 days of synthetic history, loaded once by `python -m scripts.seed_telemetry`. Both the Phase 01 visualization and the newsvendor recommendation in `/telemetry/stats` read from here. **If you change the generator, you must run `--reset` to reload it.**
- **`api_logs`** — a rolling audit log; every `/simulate/run` and `/agent/chat` appends a row. Only used by the "Live API logs" panel in Phase 01; no business logic depends on it.

### 5.2 JSON caches (`backend/data/`)

- **`scenario_config.json`** — strategy + quarterly overrides from the last simulation (only used by `/results/scenario`; no business logic depends on it).
- **`run_log.json`** — full result of the last simulation.

**Note**: the Phase 04 radar does **not** read `run_log.json`. It computes scores from `App.tsx`'s in-memory `completedMonths`. The `/results/*` endpoints are mostly there for debugging and external scripts (e.g. `run_student_sim.py`); the frontend doesn't strongly depend on them.

### 5.3 Full lifecycle of a session

```
seed_telemetry.py (once)
    ↓ writes
SQLite.daily_demand (730 days)
    ↓ read by Phase 01 + /stats recommendation
Browser
    ↓ POST /simulate/run (once per quarter, 4 times total)
DES engine
    ↓ returns
Browser memory (completedMonths accumulates 12 months)
    ↓ computes
Phase 04 radar score
```

---

## 6. Newsvendor and scoring

### 6.1 Where the recommended N comes from

In [telemetry.py:34-60](backend/app/routers/telemetry.py), the `/telemetry/stats` endpoint:

- Weights underage costs by the historical 18/35/47 tier mix → `c_u_blend`.
- Computes the critical fractile `F* = c_u / (c_u + c_o)` ≈ 0.96.
- Reads the F\*-th percentile of historical demand as the target, then divides by "100 reqs/day per node" to back out N\*.
- Returns `recommended_n_min = round(N* × 0.85)` and `recommended_n_max = round(N* × 1.10)`.

The comment in the code calls out that a node can theoretically serve more than 100 req/day; the value is deliberately compressed to land the recommended N in the pedagogically clean 10–16 range. Changing this number shifts the "correct answer" of the game.

### 6.2 The five score dimensions

Formulas live in `computeScores()` in [RadarLeaderboard.tsx](src/components/RadarLeaderboard.tsx) and match the README table. `nStar = 15` is a fallback; the real value is `(recommended_n_min + recommended_n_max) / 2` from `/telemetry/stats`.

**Capacity Accuracy uses the average N across the four quarters** (`avgQuarterN` in `App.tsx`), not `initialN`. That way mid-year purchases also show up in the score.

---

## 7. Frontend design notes

### 7.1 Why state lives in App.tsx

`AnimatePresence mode="wait"` genuinely unmounts components on phase transitions. So routingCode, chat history, and the current quarter's N all have to live in `App.tsx` — otherwise they vanish when the student moves from Phase 02 to Phase 03 and back. We've been burned by this before (see commit `8fcccf9 fix(ui): sync Phase 01 N input with locked initialN on remount`).

### 7.2 How N evolves

- Phase 01 locks `initialN` (immutable), which also seeds `quarterN[1]`.
- Phase 02 (Q2/Q3/Q4) can adjust `quarterN[Q]`, but **only upward** — billing uses `Math.max(0, n - prev)`.
- Downsizing N does not refund. (Pedagogical premise: CapEx is irreversible.)
- Each additional GPU costs `18 × 100 = $1800` against the budget (`UNIT_COST × COST_SCALE`).

### 7.3 The AI Dispatcher chat

The right half of Phase 02 is a chat panel that POSTs to `/ai-assistant`. The backend logic is intentionally minimal:

- If `LLM_PROVIDER=azure` → call Azure OpenAI via [llm_client.py](backend/app/services/llm_client.py).
- If `LLM_PROVIDER=mock` (default) → return a scripted keyword-matched reply — no API key needed.

The active provider is read once per request via `get_llm_client()` in [llm_client.py](backend/app/services/llm_client.py). The system prompt (injecting the student's current dashboard state) is built in [prompt_templates.py](backend/app/services/prompt_templates.py).

No RAG, no function calling — just history + system prompt concatenated and sent to the model.

---

## 8. Running it locally

The README covers most of this. A few things it doesn't emphasize:

```bash
# First-time setup: you MUST seed, otherwise Phase 01 is empty
cd backend && python3 -m scripts.seed_telemetry && cd ..

# If you change the seed generator, re-seed with --reset
python3 -m scripts.seed_telemetry --reset

# Both processes must be running
npm run dev:api    # backend on :8000
npm run dev        # frontend on :5173

# Smoke test: start the backend, then
python3 run_student_sim.py
```

No `.env` is required — the chat falls back to a mock reply if `OPENAI_API_KEY` is missing.

---

## 9. Gotchas and likely-future-fixes

1. **The sandbox is not adversarial-grade.** Fine for class; replace before exposing publicly.
2. **`seed=42` is hard-coded in the frontend** ([App.tsx:88](src/App.tsx)). Every student's "random" demand is the same sequence — good for fair comparison, but an observant student can over-fit. If you switch to a real random seed, remember to also update `_random.seed()` in [simulate.py:81](backend/app/routers/simulate.py).
3. **`reqs_per_node_per_day = 100` is hand-tuned** ([telemetry.py:55](backend/app/routers/telemetry.py)). Changing it moves the recommended-N range, which directly changes the Capacity Accuracy score.
4. **JSON caches have no concurrency protection.** Two concurrent `/simulate/run` requests will clobber each other's `run_log.json`. Single-user classroom use is fine.
5. **`daily_demand` uses `INSERT OR IGNORE`** — re-running the seeder neither errors nor updates existing rows; only `--reset` actually replaces them.
6. **`api_logs` is never pruned.** Doesn't break anything, but the file grows forever. Add a cleanup job if you deploy long-term.
7. **CORS defaults to the Vite dev ports only.** If you deploy elsewhere, set `CORS_ALLOW_ORIGINS`.
8. **No automated test suite.** `run_student_sim.py` is the only end-to-end smoke test. No unit tests, no CI.

---

## 10. "Where do I change X" cheat sheet

| Want to change... | Edit... |
|---|---|
| Historical demand curve (peaks, troughs, anomalies) | `ANOMALY_WINDOWS` + `BASE_LAMBDA` in [seed_telemetry.py](backend/scripts/seed_telemetry.py), then `--reset` |
| Default sim parameters (λ, prices, penalties) | `DEFAULT_STRATEGY` in [simulate.py](backend/app/routers/simulate.py) and the `strategy.get(..., default)` calls in [des_engine.py:run_month](backend/app/core/des_engine.py) |
| Tier proportions | `_TIER_CUMPROBS` in [des_engine.py:12-14](backend/app/core/des_engine.py) |
| Scoring formulas | `computeScores` in [RadarLeaderboard.tsx](src/components/RadarLeaderboard.tsx) |
| Recommended-N range | The `n_min/n_max` math at the end of `/stats` in [telemetry.py](backend/app/routers/telemetry.py) |
| Sandbox whitelist | `_SAFE_BUILTINS_NAMES` in [simulate.py](backend/app/routers/simulate.py) |
| Phase order / count | `PHASES` in [App.tsx](src/App.tsx) plus `runQuarter`/`advanceQuarter` |
| LLM provider / model | [llm_client.py](backend/app/services/llm_client.py) + `LLM_PROVIDER` / `AZURE_OPENAI_*` env vars |

---

## 11. Design choices worth preserving (don't reflexively refactor)

- **N is irreversible.** "Sunk CapEx" is the core tension of the newsvendor lesson. Don't add a "sell GPUs back" feature.
- **The DES has per-server queues, not one global queue.** That's what makes routing decisions matter. If you collapse it to a single-queue M/M/c, the whole Phase 02 lesson loses its point.
- **`routing_code` is compiled once per request.** All 12 months share one compiled function — the student can't change strategy mid-year, which matches the "write one good policy" pedagogy.
- **All cross-phase state lives in App.tsx.** We tried putting `routingCode` inside `DualCoreWorkspace` once; it got destroyed on every quarter transition. Don't push it back down.

---

## 12. Debugging entry points

```bash
# Is the backend up?
curl http://localhost:8000/health
curl http://localhost:8000/telemetry/stats | jq

# What did the last simulation return?
cat backend/data/run_log.json | jq

# Tail the request log
sqlite3 backend/data/telemetry.db "select * from api_logs order by id desc limit 20"

# End-to-end run of all 12 months
python3 run_student_sim.py
```

The backend runs with `--reload`, so `.py` edits hot-reload. The frontend has Vite HMR.

---

If you only have time to read three files, read these in order:

1. [src/App.tsx](src/App.tsx) — how the whole flow is orchestrated.
2. [backend/app/core/des_engine.py](backend/app/core/des_engine.py) — what the simulation actually computes.
3. [backend/app/routers/simulate.py](backend/app/routers/simulate.py) — how student input gets into the simulation.

Those three are the skeleton. Everything else is a shell around them.
