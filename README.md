# SyntaxTax

Automated technical debt analyzer that quantifies code complexity into financial metrics.

CTOs and engineering managers use SyntaxTax to measure the monetary cost of maintenance burden across their Python repositories.

## Architecture

```
GitHub Webhook ──► FastAPI ──► ARQ/Redis ──► Worker ──► Supabase
                      │                        │
                      └── GET /results/{id}  ◄──┘  (polling)
```

1. A GitHub push/PR event hits `POST /webhook/github`
2. The API validates the HMAC signature and enqueues an analysis job in Redis via ARQ
3. A background worker picks up the job, clones the repo, runs the static analyzer
4. The financial report is persisted to Supabase
5. Clients poll `GET /results/{delivery_id}` — returns `queued` → `running` → report or `failed`

## Quick start

```bash
cp .env.example .env
# edit .env with your Supabase credentials and webhook secret
docker compose up --build
```

The API is available at `http://localhost:8000`. Docs at `http://localhost:8000/docs`.

## Project structure

```
├── api/                    # FastAPI application
│   ├── main.py             # App, lifespan, endpoints
│   ├── database.py         # Supabase client + CRUD
│   ├── worker.py           # ARQ job definition + WorkerSettings
│   └── run_worker.py       # Worker entrypoint
├── core_analyzer/          # Static analysis engine (network-free)
│   ├── parser.py           # AST parsing
│   ├── metrics.py          # Cyclomatic complexity, line metrics
│   └── financial_model.py  # Churn × complexity → cost
├── database/migrations/    # Supabase SQL migrations
├── Dockerfile              # Multi-stage build
├── docker-compose.yml      # Redis + API + Worker
└── docs/                   # Documentation
```

## Tech stack

| Layer | Technology |
|---|---|
| API | FastAPI (Python 3.12) |
| Queue | ARQ + Redis 7 |
| Database | PostgreSQL via Supabase |
| Analyzer | Native `ast` module |
| Container | Docker + Docker Compose |

## Documentation

- [Architecture context](docs/architecture_context.md)
- [API reference](docs/api_reference.md)
- [Core analyzer guide](docs/core_analyzer_guide.md)
- [Development setup](docs/development.md)
- [Database migrations](database/migrations/README.md)
