# Development Guide

## Prerequisites

- Python 3.12+
- Docker and Docker Compose
- Git
- A Supabase project (free tier works)
- A GitHub App with webhook enabled (for testing webhooks)

## Quick start with Docker (recommended)

```bash
# 1. Clone the repository
git clone <repo-url> && cd syntaxtax

# 2. Configure environment
cp .env.example .env
# Edit .env with your Supabase credentials and webhook secret

# 3. Build and start all services
docker compose up --build
```

This starts three containers:
- `redis` on port 6379
- `api` on port 8000 (with `--reload` for hot-reloading)
- `worker` (no exposed ports)

The API is available at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

## Setup without Docker

### 1. Python environment

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Redis

You need a Redis server running locally. With Docker:

```bash
docker run -d -p 6379:6379 redis:7-alpine
```

Or install Redis natively (not covered here).

### 3. Environment variables

```bash
cp .env.example .env
```

Required variables:

| Variable | Description |
|---|---|
| `GITHUB_WEBHOOK_SECRET` | Secret used to sign webhook payloads (HMAC-SHA256) |
| `SUPABASE_URL` | Your Supabase project URL (`https://xxxxx.supabase.co`) |
| `SUPABASE_SERVICE_ROLE_KEY` | Service role key (bypasses RLS) |
| `SUPABASE_DATABASE_URL` | Direct PostgreSQL connection string (for `psql` migrations) |

Optional variables:

| Variable | Default | Description |
|---|---|---|
| `REDIS_HOST` | `localhost` | Redis hostname |
| `REDIS_PORT` | `6379` | Redis port |
| `MAX_JOBS_PER_WORKER` | `4` | Max concurrent jobs per worker process |
| `MAX_JOBS_PER_ORG` | `2` | Max concurrent jobs per GitHub organization |

### 4. Run database migrations

Paste the contents of `database/migrations/001_create_organizations_and_reports.sql` into the Supabase SQL Editor, or use `psql`:

```bash
psql "$SUPABASE_DATABASE_URL" -f database/migrations/001_create_organizations_and_reports.sql
```

### 5. Start services

In separate terminals:

```bash
# Terminal 1: API
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2: Worker
python -m api.run_worker
```

## Streamlit Dashboard

The dashboard is a Streamlit app that consumes the API. It shows cost metrics per repository and an interactive table of critical functions.

With Docker (4 services now):

```bash
docker compose up --build
```

The dashboard is at `http://localhost:8501`.

Without Docker:

```bash
# Install dependencies (one time)
pip install streamlit requests plotly

# Start the API and worker first, then:
API_BASE_URL=http://localhost:8000 streamlit run dashboard/app.py
```

## Running tests

```bash
# Run the core analyzer end-to-end test
python -m tests.test_financial_impact
```

The test creates a temporary git repository, runs the full analysis pipeline, and asserts the expected metrics.

## GitHub App setup

To test webhooks locally you need a GitHub App:

1. Go to GitHub Settings → Developer settings → GitHub Apps → New GitHub App
2. Set the webhook URL to your public endpoint (see SSH tunnel below)
3. Set a webhook secret and copy it to `GITHUB_WEBHOOK_SECRET` in `.env`
4. Subscribe to at least the `push` event
5. Install the app on a test repository

### Exposing localhost with SSH tunnel

GitHub cannot reach `localhost`. Use an SSH tunnel to expose your local server:

```bash
ssh -R 80:localhost:8000 localhost.run
```

This gives you a public URL like `https://abc123.localhost.run`. Use this as the webhook URL in your GitHub App settings.

## Coding conventions

### Mandatory

- **Strict typing**: Every function signature must have type hints.
- **No secrets in code**: All secrets via `os.getenv()` with clear fallback behavior.
- **Domain isolation**: `core_analyzer/` must never import from `api/`.

### Architecture rules

- The core analyzer (`core_analyzer/`) is pure logic — it receives file paths and returns JSON. No network calls, no database access.
- The API layer (`api/`) handles HTTP, Redis, and database operations.
- The worker (`api/worker.py`) bridges the gap — it receives a clone URL, calls the analyzer, and persists results.

### Git conventions

- Commit messages in English, imperative mood ("Add feature", not "Added feature" or "Adding feature")
- One logical change per commit
- Squash fixup commits before PR
