# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

**Development (Docker)**
```bash
docker compose up --build          # Start all services: Redis, API, Worker, Dashboard
docker compose up api worker       # Start only backend services
docker compose down
```

**Run without Docker**
```bash
python -m uvicorn api.main:app --reload --port 8000   # API server (includes background thread pool)
python -m streamlit run dashboard/app.py               # Dashboard on :8501
```

**Tests**
```bash
python -m tests.test_financial_impact   # Full end-to-end test (creates a temp git repo)
```

No pytest is configured — tests run as plain Python scripts.

**Production**
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d   # Includes Caddy proxy
```

## Architecture

SyntaxTax is a GitHub webhook receiver that analyzes Python repositories and produces a financial cost estimate of technical debt. The core insight: functions that are both frequently changed (git churn) and complex (cyclomatic complexity) impose the highest ongoing maintenance cost.

**Domain isolation rule:** `core_analyzer/` must never import from `api/`. The analyzer is network-free; it receives local file paths only. Git cloning happens in `api/worker.py`, not inside the analyzer.

**Request flow:**
1. GitHub sends a push event to `POST /webhook/github` — HMAC-validated, org/repo extracted
2. `api/main.py` enqueues an ARQ job (via Redis) and returns a `delivery_id`
3. `api/worker.py` picks up the job: clones the repo to a temp dir, calls the analyzer
4. `core_analyzer/financial_model.py` orchestrates: parse → complexity → churn → cost matrix
5. Result saved to Supabase (`organizations` + `financial_reports` tables)
6. Client polls `GET /results/{delivery_id}` until status is `completed`

**Core analyzer pipeline** (`core_analyzer/`):
- `parser.py` — walks a directory tree, extracts function definitions via Python's `ast` module
- `metrics.py` — `CyclomaticComplexityVisitor` counts branch nodes; also tracks LOC per function
- `financial_model.py` — correlates AST data with `git log --follow` churn counts, applies a cost-per-change rate (€65/h default) to produce a per-function EUR cost

**Database schema** (Supabase/PostgreSQL):
- `organizations` — GitHub org name, API key
- `financial_reports` — JSONB `report_data` column, linked to org via FK, `delivery_id` for polling
- RLS enabled; use `SUPABASE_SERVICE_ROLE_KEY` from the backend (bypasses RLS)
- Migrations in `database/migrations/` are append-only — never edit existing migration files

## Environment

Copy `.env.example` to `.env`. Required variables:
- `GITHUB_WEBHOOK_SECRET` — must match the secret configured in GitHub
- `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_DATABASE_URL`

Optional (have defaults): `MAX_JOBS_PER_WORKER` (4) — número de hilos del ThreadPoolExecutor.

Production only: `DASHBOARD_USER`, `DASHBOARD_PASSWORD_HASH` (bcrypt) — used by Caddy basic auth for `/dashboard`.

## Key Conventions

- Type hints are required on all function signatures.
- The `api/database.py` Supabase client is a module-level singleton initialized on first import via `get_db()`.
- ARQ job retry logic is in `WorkerSettings` in `api/worker.py`; job concurrency limits are enforced there.
- The Streamlit dashboard (`dashboard/app.py`) reads directly from Supabase — it is read-only and has no write path.
