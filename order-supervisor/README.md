# Order Supervisor

A POC long-running AI supervisor that oversees a single e-commerce order from
creation to completion. One **Temporal workflow per order** receives lifecycle
events as **signals**; an LLM agent (running as a Temporal **activity**) decides
when to act, which of 5 business actions to take, and when to sleep/wake. The
**workflow owns completion** — the agent may only recommend it.

## Stack

- **Frontend:** Next.js (App Router) + Tailwind CSS
- **Backend:** Python + FastAPI
- **Orchestration:** Temporal Python SDK (`temporalio`)
- **Persistence:** PostgreSQL (single `activity_log` table approach)
- **LLM:** provider-pluggable (`LLM_PROVIDER` = `groq` / `openai` / `anthropic` / `mock`)

> **`mock` runs the whole product with no API key** (deterministic policy) and is
> also the automatic fallback if a real provider errors. Set `LLM_PROVIDER=groq`
> + `LLM_API_KEY` to use a real LLM.

## Prerequisites

- Docker Desktop (running)
- Python 3.11+
- Node 18+

## 1. Start infrastructure (Temporal + UI + Postgres)

```bash
cd order-supervisor
docker compose up -d
```

- Temporal server: `localhost:7233`
- Temporal Web UI: http://localhost:8080
- App Postgres: `localhost:5432` (db `order_supervisor`, user/pass `supervisor`)

## 2. Backend

```bash
cd backend
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# bash:               source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env        # set LLM_PROVIDER + LLM_API_KEY (or leave as mock)

# Terminal A — Temporal worker (runs the workflow + activities)
python -m app.temporal.worker

# Terminal B — FastAPI (creates tables + seeds 2 supervisor templates on boot)
uvicorn app.main:app --reload --port 8000
```

## 3. Frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev        # http://localhost:3000
```

## 4. Use it

Open http://localhost:3000:

1. **Supervisors** tab — two templates are seeded; create more if you like.
2. **Runs** tab — pick a template, give an order id, **Start run**.
3. Open the run — **inject events**, **add instructions**, **pause/resume/
   interrupt/terminate**. The timeline, memory, and activity log refresh live.
4. Inject **`delivered`** (or Terminate) to end the run and see the LLM-authored
   **final summary, learnings, and recommendations**.
5. Watch the same workflow in the Temporal UI (http://localhost:8080).

### Time scaling for the demo

The agent reasons in "hours" but real sleeps are compressed by `TIME_SCALE`
(real seconds per simulated hour). Default `1` => a "6-hour" sleep is ~6 seconds,
so sleep→wake is visible on video. `no_update_for_n_hours` is also injectable on
demand from the UI.

## Scripts

All run from `backend/` with the venv python:

| Script | Needs | Purpose |
|---|---|---|
| `python -m scripts.check_llm` | LLM only | One live `agent_step` against the configured provider |
| `python -m scripts.test_workflow` | nothing (in-memory) | Validates the full workflow (signals, sleep/wake, classifier, completion) in Temporal's time-skipping test env |
| `python -m scripts.demo` | full stack up | Seeded event generator — starts a run and injects a realistic event sequence |

## API

`POST/GET /api/supervisors`, `GET /api/supervisors/{id}`,
`POST/GET /api/runs`, `GET /api/runs/{run_id}`,
`POST /api/runs/{run_id}/events|instructions|interrupt|pause|resume|terminate`.

## Architecture

See [ARCHITECTURE.md](./ARCHITECTURE.md).
