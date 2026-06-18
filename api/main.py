import asyncio
import hashlib
import hmac
import json
import os
from contextlib import asynccontextmanager

from arq import create_pool
from api.database import get_latest_reports_by_org, get_report_by_delivery_id
from api.worker import REDIS_SETTINGS
from fastapi import FastAPI, HTTPException, Request


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        pool = await create_pool(REDIS_SETTINGS)
        app.state.redis = pool
    except Exception:
        app.state.redis = None
    yield
    if app.state.redis is not None:
        await app.state.redis.close()


app = FastAPI(title="SyntaxTax API", version="0.1.0", lifespan=lifespan)

WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET", "")


@app.get("/ping")
def health_check():
    return {"status": "ok", "service": "syntaxtax-api"}


@app.post("/webhook/github")
async def github_webhook(request: Request):
    body = await request.body()
    signature_header = request.headers.get("X-Hub-Signature-256")
    event = request.headers.get("X-GitHub-Event")

    if not signature_header or not signature_header.startswith("sha256="):
        raise HTTPException(status_code=401, detail="Invalid signature")

    expected_signature = "sha256=" + hmac.new(
        WEBHOOK_SECRET.encode(), body, hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(signature_header, expected_signature):
        raise HTTPException(status_code=401, detail="Invalid signature")

    if event == "ping":
        return {"message": "pong"}

    payload = json.loads(body)
    delivery_id = request.headers.get("X-GitHub-Delivery", "")

    try:
        repo = payload["repository"]
        clone_url = repo["clone_url"]
        repo_name = repo["name"]
    except KeyError:
        raise HTTPException(status_code=400, detail="Missing repository data in payload")

    org = payload.get("organization")
    if org:
        github_org_id = org["id"]
        org_name = org["login"]
    else:
        owner = repo.get("owner", {})
        github_org_id = owner.get("id", 0)
        org_name = owner.get("login", "unknown")

    if request.app.state.redis is None:
        raise HTTPException(status_code=503, detail="Redis not available")

    job = await request.app.state.redis.enqueue_job(
        "run_analysis_job",
        clone_url,
        delivery_id,
        repo_name,
        github_org_id,
        org_name,
    )

    if job:
        await request.app.state.redis.set(
            f"syntaxtax:status:{delivery_id}",
            json.dumps({"status": "queued", "delivery_id": delivery_id}),
            ex=3600,
            nx=True,
        )

    return {"status": "accepted", "delivery_id": delivery_id}


@app.get("/api/reports/{org_id}")
async def get_org_reports(org_id: int):
    reports = await asyncio.to_thread(get_latest_reports_by_org, org_id)
    if not reports:
        raise HTTPException(status_code=404, detail="No reports found")
    return reports


@app.get("/results/{delivery_id}")
async def get_result(delivery_id: str, request: Request):
    report = await asyncio.to_thread(get_report_by_delivery_id, delivery_id)
    if report is not None:
        return report

    if request.app.state.redis is not None:
        status_raw = await request.app.state.redis.get(
            f"syntaxtax:status:{delivery_id}"
        )
        if status_raw:
            return json.loads(status_raw)

    raise HTTPException(status_code=404, detail="No report or job found for this delivery ID")
