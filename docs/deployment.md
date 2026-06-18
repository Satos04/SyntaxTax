# Deployment Guide

## Prerequisites

- A VPS with Docker and Docker Compose installed (Ubuntu 22.04+ recommended)
- A registered GitHub App (or the development one reconfigured for production)
- A Supabase project (already set up)

## Architecture

```
Internet :80
    │
    ▼
  Caddy (reverse proxy, Basic Auth on /dashboard/*)
    ├── /dashboard/*  ──►  Streamlit (dashboard:8501)
    └── /*             ──►  FastAPI   (api:8000)
                                │
                          ┌─────┴─────┐
                          ▼           ▼
                        Redis       Supabase
                        (queue)     (persistence)
```

Only port 80 is exposed. All internal services communicate over Docker's internal network.

## Step-by-step

### 1. Provision a VPS

Create a VPS with Ubuntu 22.04 or 24.04 (the cheapest tier is enough to start — 1 CPU, 1 GB RAM).

### 2. Install Docker and Docker Compose

```bash
# Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# Log out and back in, or run: newgrp docker

# Verify
docker --version
docker compose version
```

### 3. Clone the repository

```bash
git clone <your-repo-url> /opt/syntaxtax
cd /opt/syntaxtax
```

### 4. Configure environment variables

```bash
cp .env.example .env
nano .env
```

Fill in the required values:

| Variable | Description |
|----------|-------------|
| `GITHUB_WEBHOOK_SECRET` | Must match the secret configured in your GitHub App |
| `SUPABASE_URL` | Your Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase service role key |
| `SUPABASE_DATABASE_URL` | Full PostgreSQL connection string |
| `MAX_JOBS_PER_WORKER` | Concurrent jobs per worker (default: `4`) |
| `MAX_JOBS_PER_ORG` | Concurrent jobs per organization (default: `2`) |
| `DASHBOARD_USER` | Username for Basic Auth on the dashboard |
| `DASHBOARD_PASSWORD_HASH` | **See next section** |

### 5. Generate the dashboard password hash

```bash
docker run --rm caddy:2-alpine caddy hash-password --plaintext "your_actual_password"
```

Copy the output (starts with `$2a$`) and set it as `DASHBOARD_PASSWORD_HASH` in `.env`:

```bash
DASHBOARD_USER=admin
DASHBOARD_PASSWORD_HASH='$2a$14$xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
```

> The single quotes around the hash prevent shell expansion of the `$` characters.

### 6. Start the services

```bash
docker compose -f docker-compose.prod.yml up -d
```

Check that everything started correctly:

```bash
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs --tail=20
```

### 7. Verify the deployment

```bash
# Health check
curl http://<your-server-ip>/ping

# Expected: {"status":"ok","service":"syntaxtax-api"}

# Dashboard (should prompt for username/password)
curl -u admin:your_password http://<your-server-ip>/dashboard/
```

### 8. Configure the GitHub App webhook

In your GitHub App settings:

- **Webhook URL**: `http://<your-server-ip>/webhook/github`
- **Webhook secret**: The value of `GITHUB_WEBHOOK_SECRET` from your `.env`
- **Events**: Select the events you want to trigger analysis (e.g., `push`, `pull_request`)

### 9. Monitor

```bash
# View logs for all services
docker compose -f docker-compose.prod.yml logs -f

# View logs for a specific service
docker compose -f docker-compose.prod.yml logs -f api
docker compose -f docker-compose.prod.yml logs -f worker
```

## Updating

```bash
cd /opt/syntaxtax
git pull
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d
```

## Adding a domain later

1. Point your domain's A record to the VPS IP.
2. Update `Caddyfile`:

```caddyfile
yourdomain.com {
    basicauth /dashboard* {
        {$DASHBOARD_USER} {$DASHBOARD_PASSWORD_HASH}
    }

    handle /dashboard* {
        reverse_proxy dashboard:8501
    }

    handle {
        reverse_proxy api:8000
    }
}
```

3. Add port 443 to the Caddy service in `docker-compose.prod.yml`:

```yaml
  caddy:
    ports:
      - "80:80"
      - "443:443"
```

4. Restart:

```bash
docker compose -f docker-compose.prod.yml up -d
```

Caddy will automatically provision and renew TLS certificates via Let's Encrypt.

## Troubleshooting

| Problem | Likely cause | Fix |
|---------|-------------|-----|
| Dashboard shows 502 | API not ready | Wait a few seconds, or check `docker compose logs api` |
| Webhook returns 401 | Wrong secret | Verify `GITHUB_WEBHOOK_SECRET` matches GitHub App config |
| Worker not processing jobs | Redis connection | Check `docker compose logs worker` — verify `REDIS_HOST=redis` |
| Jobs stuck in "queued" | Worker crashed or OOM | Check `docker compose logs worker`; consider increasing VPS RAM |
| Caddy won't start | Bad hash format | Regenerate hash with `caddy hash-password` and ensure it's wrapped in single quotes in `.env` |
