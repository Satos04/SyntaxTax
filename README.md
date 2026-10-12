# SyntaxTax

Automated technical debt analyzer that quantifies code complexity into financial metrics.

CTOs and engineering managers use SyntaxTax to measure the monetary cost of maintenance burden across their Python repositories.

## Architecture

```
GitHub Webhook ──► FastAPI ──► ThreadPoolExecutor ──► Supabase
                       │                  │
                       └── GET /results/{id}  ◄──────┘  (in-process)
```

1. A GitHub push/PR event hits `POST /webhook/github`
2. The API validates the HMAC signature and submits the analysis to a `ThreadPoolExecutor`
3. The inline worker clones the repo and runs the static analyzer (parser → complexity → churn → cost)
4. The financial report is persisted to Supabase
5. Clients poll `GET /results/{delivery_id}` — returns `queued` → report or `failed`

## Key features

- **Debt in euros, not abstract scores:** every function gets a maintenance cost estimate (default €65/h per change).
- **Churn × complexity:** correlates `git log --follow` change frequency with cyclomatic complexity from the AST, so the costliest hotspots are the functions that are both complex *and* changed often.
- **Webhook-driven:** a GitHub App triggers an analysis on every push, with HMAC signature validation and support for private repositories.
- **Network-free core:** `core_analyzer/` only receives local paths and never imports from `api/`, which keeps it easy to test and reuse.
- **Read-only dashboard:** Streamlit + Plotly view with metrics, charts and a table of critical functions.

## Deployment status

> **The production server is no longer running.** The project was deployed on a VPS behind a Caddy reverse proxy (automatic HTTPS, Basic Auth on the dashboard), but I shut it down to save costs. The public URLs are offline.

The deployment setup is still in the repo and reproducible: `docker-compose.prod.yml` and the `Caddyfile` describe the full production stack (see the [deployment guide](docs/deployment.md)). To run it yourself you need your own Supabase project and a GitHub App.

## Quick start (local development)

```bash
cp .env.example .env
# edit .env with your Supabase credentials and webhook secret
docker compose up --build
```

The API is available at `http://localhost:8000`. Docs at `http://localhost:8000/docs`.
The Dashboard is available at `http://localhost:8501`.

## Project structure

```
├── api/                    # FastAPI application
│   ├── main.py             # App, lifespan, ThreadPoolExecutor, endpoints
│   ├── database.py         # Supabase client + CRUD
│   └── worker.py           # Analysis job (runs in ThreadPoolExecutor)
├── core_analyzer/          # Static analysis engine (network-free)
│   ├── parser.py           # AST parsing
│   ├── metrics.py          # Cyclomatic complexity, line metrics
│   └── financial_model.py  # Churn × complexity → cost
├── dashboard/              # Streamlit web dashboard
│   └── app.py              # Metrics, charts, critical functions table
├── database/migrations/    # Supabase SQL migrations
├── Dockerfile              # Multi-stage build
├── docker-compose.yml      # API + Dashboard (dev)
├── docker-compose.prod.yml # Production with Caddy reverse proxy
├── Caddyfile               # Caddy config (Basic Auth on /dashboard/)
└── docs/                   # Documentation
```

## Tech stack

| Layer | Technology |
|---|---|
| API | FastAPI (Python 3.12) |
| Async worker | ThreadPoolExecutor (in-process, no Redis) |
| Database | PostgreSQL via Supabase |
| Analyzer | Native `ast` module |
| Dashboard | Streamlit + Plotly |
| Reverse proxy | Caddy (auto HTTPS, Basic Auth) |
| Container | Docker + Docker Compose |

## Documentation

- [Architecture context](docs/architecture_context.md)
- [API reference](docs/api_reference.md)
- [Core analyzer guide](docs/core_analyzer_guide.md)
- [Development setup](docs/development.md)
- [Deployment guide](docs/deployment.md)
- [Database migrations](database/migrations/README.md)
