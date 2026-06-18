# API Reference

Base URL: `http://localhost:8000` (development) or your deployed URL.

## `GET /ping`

Health check endpoint. Returns service status.

**Response `200`:**

```json
{
  "status": "ok",
  "service": "syntaxtax-api"
}
```

---

## `POST /webhook/github`

Ingests GitHub webhook events (push, pull_request, ping). Validates the payload HMAC-SHA256 signature, enqueues an analysis job, and returns immediately.

### Headers

| Header | Required | Description |
|---|---|---|
| `X-Hub-Signature-256` | Yes | HMAC-SHA256 of the raw body, signed with your webhook secret |
| `X-GitHub-Event` | Yes | Event type (`push`, `pull_request`, `ping`) |
| `X-GitHub-Delivery` | Yes | Unique delivery ID (used as job identifier) |

### Request body

Standard GitHub webhook payload. Must include at minimum:

```json
{
  "repository": {
    "name": "my-repo",
    "clone_url": "https://github.com/org/my-repo.git",
    "owner": {
      "id": 12345,
      "login": "my-org"
    }
  },
  "organization": {
    "id": 12345,
    "login": "my-org"
  }
}
```

- `organization` is optional. If absent, the owner data from `repository.owner` is used.
- Only the `clone_url`, `name`, and org `id`/`login` are extracted.

### Response `202`

```json
{
  "status": "accepted",
  "delivery_id": "abc123..."
}
```

The client should use `delivery_id` to poll `GET /results/{delivery_id}`.

### Response `401`

Invalid or missing `X-Hub-Signature-256` header.

```json
{
  "detail": "Invalid signature"
}
```

### Response `400`

Missing repository data in the payload.

```json
{
  "detail": "Missing repository data in payload"
}
```

### Response `503`

Redis is not available — the job cannot be queued.

```json
{
  "detail": "Redis not available"
}
```

### Special event: `ping`

GitHub sends a `ping` event when the webhook is first configured. The endpoint returns immediately without queuing a job:

```json
{
  "message": "pong"
}
```

---

## `GET /results/{delivery_id}`

Returns the analysis result for a given GitHub delivery ID. Since analysis is async, the response depends on the job state.

### Response states

| HTTP | `status` field | Meaning |
|---|---|---|
| `200` | *(none — report object)* | Analysis completed. Full report from Supabase. |
| `200` | `"queued"` | Job accepted but waiting for a worker slot (per-org concurrency limit). |
| `200` | `"running"` | Analysis in progress. |
| `200` | `"failed"` | Analysis failed. `error` field contains details. |
| `404` | — | No job or report exists for this delivery ID. |

### Completed response (`200`)

The full financial report from Supabase. Structure:

```json
{
  "id": "uuid",
  "organization_id": "uuid",
  "github_delivery_id": "abc123...",
  "repository_name": "my-repo",
  "report_data": {
    "repo": "/tmp/syntaxtax_xxx/my-repo",
    "since_days": 30,
    "cost_per_hour": 50.0,
    "hours_per_point": 0.5,
    "total_files_analyzed": 10,
    "files_with_churn": 10,
    "total_functions_analyzed": 87,
    "total_extra_points": 45,
    "total_cost_eur": 1425.0,
    "top_files": [
      {
        "file": "src/complex_module.py",
        "cost_eur": 700.0,
        "file_metadata": {
          "total_functions_count": 5,
          "clean_functions_count": 2,
          "critical_functions_count": 3
        },
        "critical_functions": [
          {
            "name": "process_data",
            "complexity": 12,
            "extra_complexity": 11,
            "lines": 84,
            "cost_eur": 300.0
          }
        ]
      }
    ]
  },
  "created_at": "2026-06-18T12:00:00+00:00"
}
```

### In-progress response (`200`)

```json
{
  "status": "running",
  "delivery_id": "abc123..."
}
```

### Failed response (`200`)

```json
{
  "status": "failed",
  "delivery_id": "abc123...",
  "error": "Git clone failed: ..."
}
```

### Not found (`404`)

```json
{
  "detail": "No report or job found for this delivery ID"
}
```

### Client polling example

```python
import time, requests

BASE = "http://localhost:8000"

def wait_for_result(delivery_id: str, interval: int = 3, timeout: int = 600) -> dict:
    start = time.time()
    while True:
        resp = requests.get(f"{BASE}/results/{delivery_id}")
        if resp.status_code == 404:
            raise ValueError("Delivery ID not found")

        data = resp.json()
        status = data.get("status", "completed")

        if status == "completed":
            return data
        if status == "failed":
            raise RuntimeError(data.get("error", "Unknown error"))
        if time.time() - start > timeout:
            raise TimeoutError("Analysis did not complete in time")

        time.sleep(interval)
```
