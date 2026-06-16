# Order Supervisor

A POC long-running AI supervisor that oversees a single e-commerce order from
creation to completion. One **Temporal workflow per order** receives lifecycle
events as **signals**; an LLM agent (running as a Temporal **activity**) decides
when to act, what business actions to take, and when to sleep/wake.

> **Status:** Phase 0 — scaffold. FastAPI ⇄ Temporal ⇄ Worker round trip works
> end-to-end; full supervisor logic lands in later phases.

## Stack

- **Frontend:** Next.js (App Router) + Tailwind CSS
- **Backend:** Python + FastAPI
- **Orchestration:** Temporal Python SDK (`temporalio`)
- **Persistence:** PostgreSQL
- **LLM:** provider-pluggable (`LLM_PROVIDER` = groq / openai / anthropic / mock)

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
cp ../.env.example .env        # edit LLM_API_KEY later; defaults work for Phase 0

# Terminal A — Temporal worker
python -m app.temporal.worker

# Terminal B — FastAPI
uvicorn app.main:app --reload --port 8000
```

## 3. Frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev        # http://localhost:3000
```

## 4. Verify Phase 0 end-to-end

1. Open http://localhost:3000 and click **Run HelloWorkflow** — you should see a
   greeting with a workflow id.
2. Or via curl: `curl -X POST "http://localhost:8000/hello?name=world"`.
3. Open the Temporal UI (http://localhost:8080) and confirm the `hello-*`
   workflow appears as **Completed**.

## Architecture

See [ARCHITECTURE.md](./ARCHITECTURE.md).
