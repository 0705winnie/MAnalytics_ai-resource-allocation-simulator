# AI-Assisted Online Resource Allocation Simulator

Teaching simulator project for an online adaptive resource allocation module.
Students will inspect historical operating data, design an admission and routing
policy, use an AI assistant for reasoning and debugging, and eventually run
month-by-month simulations against benchmark policies.

## Current Status

This repository is being rebuilt around the new online resource allocation
formulation. The current codebase includes:

- Stream A: hidden synthetic environment, historical data generation, summary
  tables, and exploratory plots.
- Stream D: mock assistant, prompt guardrails, and an API-backed LLM client with
  mock fallback.


## Repository Layout

```text
data/generated/
  historical_requests.csv
  summary_by_month.csv
  summary_by_month_type.csv
  summary_by_type.csv

outputs/figures/
  completion_rate_by_type.png
  duration_by_type.png
  requests_by_month.png
  requests_by_month_type.png
  requests_by_type.png
  required_units_by_type.png
  revenue_by_type.png

src/agent/
  llm_client.py          # OpenAI-backed assistant with mock fallback
  mock_agent.py          # deterministic no-key fallback assistant
  prompt_templates.py    # assistant rules and guardrails

src/data/
  hidden_environment.py          # development-only hidden synthetic parameters
  generate_historical_data.py    # creates historical data and summary tables
  explore_historical_data.py     # prints summaries and saves plots

src/simulator/
  .gitkeep              # placeholder for Stream B simulator work
```

### What Each File Is For

- `src/data/hidden_environment.py` defines the synthetic ground-truth setup used
  to generate data. This is for development and should not be exposed to
  students in the dashboard.
- `src/data/generate_historical_data.py` creates the historical request dataset
  and summary CSV files.
- `src/data/explore_historical_data.py` loads the generated dataset, prints
  validation summaries, and saves exploratory plots.
- `data/generated/historical_requests.csv` is the student-facing historical
  request-level dataset.
- `data/generated/summary_by_month.csv`, `summary_by_type.csv`, and
  `summary_by_month_type.csv` are aggregated views of the historical data.
- `outputs/figures/` contains plots for demand, request mix, duration, required
  units, revenue, and completion rates.
- `src/agent/mock_agent.py` is the no-key fallback assistant used for demos,
  local testing, or API failures.
- `src/agent/prompt_templates.py` contains the assistant's rules and guardrails,
  including not revealing hidden parameters or future simulation data.
- `src/agent/llm_client.py` calls the OpenAI API when `OPENAI_API_KEY` is
  configured and falls back to the mock assistant otherwise.
- `.env.example` shows the environment variables needed for local LLM mode.
- `src/simulator/.gitkeep` keeps the simulator folder in Git until Stream B adds
  simulator code.

## Setup

Use Python 3.11 or newer.

```bash
python -m pip install -r requirements.txt
```

## Generate Historical Data

From the repository root:

```bash
python src/data/generate_historical_data.py
python src/data/explore_historical_data.py
```

This writes CSV files under `data/generated/` and figures under
`outputs/figures/`.

## Assistant Configuration

The assistant can run in two modes:

- Real LLM mode when `OPENAI_API_KEY` is available.
- Mock mode when no key is available or the API call fails.

Create a local `.env` file from `.env.example`:

```text
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
OPENAI_BASE_URL=https://api.openai.com/v1
```

Do not commit `.env`. It is ignored by Git.

Quick local check:

```bash
python -m src.agent.llm_client
```

The assistant is designed to help students brainstorm policies, write and debug
policy code, interpret visible data, and compare against benchmarks. It must not
reveal hidden simulator parameters, future simulation data, or other students'
submissions.
