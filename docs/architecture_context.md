# Architecture Context: SyntaxTax

## 1. Project Vision

SyntaxTax is a B2B Micro-SaaS that quantifies technical debt in financial terms. It is not a linter for developers — it is a financial audit tool for CTOs, engineering managers, and investors.

The system analyzes Python repositories, extracts cyclomatic complexity and churn frequency, and translates these static metrics into monetary cost estimates (e.g., "euros lost per month maintaining this file").

## 2. Tech Stack

| Layer | Technology | Rationale |
|---|---|---|
| Language | Python 3.12 | Native `ast` module, rich ecosystem |
| API framework | FastAPI | Async, Pydantic typing, auto-docs |
| Task queue | ARQ + Redis 7 | Lightweight async queue, built-in retry, result backend |
| Database | PostgreSQL (Supabase) | Managed Postgres, row-level security, JSONB for reports |
| Git integration | GitHub Apps (webhooks) | Push/PR events trigger analysis |
| Containerization | Docker + Compose | Dev/prod parity, multi-service orchestration |
| Frontend (future) | React / Next.js or Streamlit | Dashboard for financial metrics |

### Environment management

- Native `venv` + `pip` only. Anaconda/Conda is **forbidden** — it adds unnecessary bloat and conflicts with the slim deployment target.

## 3. Monorepo Structure

The project follows a strict monorepo architecture. The golden rule: **the core analyzer must not import anything from `api/`**. It must run standalone without network dependencies.

```
├── api/                          # Network layer
│   ├── main.py                   # FastAPI app, lifespan, 3 endpoints
│   ├── database.py               # Supabase singleton client + CRUD
│   ├── worker.py                 # ARQ job function (run_analysis_job)
│   └── run_worker.py             # Worker process entrypoint
├── core_analyzer/                # Pure static analyzer (network-free)
│   ├── parser.py                 # AST parsing via native `ast` module
│   ├── metrics.py                # Cyclomatic complexity, line metrics
│   └── financial_model.py        # Churn + complexity → cost matrix
├── database/
│   └── migrations/               # SQL migrations (cumulative, immutable)
├── tests/                        # Test fixtures and analysis tests
├── Dockerfile                    # Multi-stage: builder pip → runtime slim
├── docker-compose.yml            # 3 services: redis, api, worker
└── docs/                         # Documentation
```

### Key design decisions

- **No `routes/` directory yet** — the API surface is small enough (3 endpoints) for a single `main.py`. Refactor into `routes/` when the surface grows.
- **`dashboard/` directory reserved** for a future frontend. Not yet implemented.
- **Environment variables via `.env` only** — no hardcoded secrets anywhere.

## 4. Execution Flow (Analysis Lifecycle)

```
GitHub                     API                         Redis/ARQ                    Worker                   Supabase
  │                         │                            │                            │                        │
  │── push/PR event ──────► │                            │                            │                        │
  │                         │  validate HMAC             │                            │                        │
  │                         │  extract delivery_id       │                            │                        │
  │                         │  set status="queued" ─────►│                            │                        │
  │                         │  enqueue_job ─────────────►│                            │                        │
  │◄─── 202 accepted ────── │                            │                            │                        │
  │                         │                            │── job picked up ─────────►│                        │
  │                         │                            │◄─── status="running" ─────│                        │
  │                         │                            │                            │── git clone ──────────►│
  │                         │                            │                            │── parse AST            │
  │                         │                            │                            │── compute metrics      │
  │                         │                            │                            │── compute cost ───────►│── INSERT report
  │                         │                            │◄─── status="completed" ───│                        │
  │                         │                            │                            │                        │
  │── poll GET /results ──► │                            │                            │                        │
  │◄── 200 (report data) ───│                            │                            │                        │
```

### Step by step

1. **Webhook ingestion** — GitHub sends a push/PR event to `POST /webhook/github`. The API validates the `X-Hub-Signature-256` HMAC, extracts the repository and organization data, and enqueues the job.
2. **Job queuing** — The ARQ pool stores the job in a Redis sorted set. A status key `syntaxtax:status:{delivery_id}` is set to `"queued"` so clients can poll immediately.
3. **Background analysis** — A worker process picks up the job, sets status to `"running"`, clones the repository with `git clone`, runs the core analyzer (AST parsing → complexity metrics → financial model), and persists the report to Supabase.
4. **Result polling** — Clients call `GET /results/{delivery_id}` and get the full report when complete, or a status object while the job is in progress.
5. **Status cleanup** — Status keys expire after 1 hour. Report data lives permanently in Supabase.

## 5. API Endpoints

See the [API reference](api_reference.md) for full documentation.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/ping` | Health check |
| `POST` | `/webhook/github` | Ingest GitHub webhook events |
| `GET` | `/results/{delivery_id}` | Poll analysis results by delivery ID |

## 6. Task Queue Architecture (ARQ + Redis)

The `ThreadPoolExecutor` from the prototype was replaced by ARQ (Async RQ) backed by Redis.

### Worker settings (`api/worker.py`)

| Setting | Value | Purpose |
|---|---|---|
| `max_jobs` | `MAX_JOBS_PER_WORKER` (default 4) | Concurrent jobs per worker process |
| `max_tries` | 3 | Retry count for non-retryable errors |
| `job_timeout` | 300s | Max wall-clock time per job |
| `max_tries` | 3 | Error retries before permanent failure |

### Per-organization concurrency

A Redis SET (`syntaxtax:org:{org_id}:active`) tracks active jobs per organization. Before starting analysis, the worker checks `SCARD` — if it equals or exceeds `MAX_JOBS_PER_ORG` (default 2), it raises `Retry(defer=30)`, which re-queues the job for 30 seconds later without consuming the error retry budget.

### Job timeout on git clone

The `git clone` subprocess has a 120-second timeout via `asyncio.wait_for`. If the clone hangs, the job fails fast and releases the slot instead of waiting for the full 300s `job_timeout`.

## 7. Status Polling System

Since analysis is asynchronous (the webhook returns a `202` immediately), a polling mechanism lets clients track progress.

### Status keys

Each delivery gets a Redis key `syntaxtax:status:{delivery_id}` with a 1-hour TTL:

| Value | Set by |
|---|---|
| `{"status": "queued"}` | Webhook handler (via `SET NX`) |
| `{"status": "running"}` | Worker at job start |
| `{"status": "completed"}` | Worker after Supabase persist |
| `{"status": "failed", "error": "..."}` | Worker in except block |

### Client polling strategy

1. Call `GET /results/{delivery_id}`
2. If response contains a full report: analysis is done
3. If response has `status: "queued"` or `"running"`: wait 2-5 seconds and retry
4. If response has `status: "failed"`: analysis failed, check `error` field
5. If `404`: delivery ID does not exist — possibly a bad request

## 8. Docker Infrastructure

Three services in `docker-compose.yml`:

| Service | Image / Build | Port | Command |
|---|---|---|---|
| `redis` | `redis:7-alpine` | 6379 | default |
| `api` | `.` (Dockerfile) | 8000 | `uvicorn api.main:app --reload` |
| `worker` | `.` (Dockerfile) | — | `python -m api.run_worker` |

The Dockerfile uses a multi-stage build:
1. **builder** — installs pip dependencies
2. **runtime** — slim image + git (needed for `git clone`), copies dependencies from builder

## 9. Development Guidelines

- **Domain isolation**: Never import `api/` from `core_analyzer/`. The analyzer must run standalone.
- **Strict typing**: All function signatures must have type hints.
- **Secrets**: Never hardcode. Always `os.getenv()` with a fallback or explicit error.
- **Modularity over premature optimization**: Write readable, pure functions. Optimize AST traversal when profiling proves it necessary.
