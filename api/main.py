import asyncio
import hashlib
import hmac
import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager

from api.database import get_latest_reports_by_org_name, get_report_by_delivery_id
from api.worker import run_analysis_job
from fastapi import FastAPI, HTTPException, Request


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.executor = ThreadPoolExecutor(
        max_workers=int(os.getenv("MAX_JOBS_PER_WORKER", "4"))
    )
    app.state.job_status = {}
    app.state.status_lock = threading.Lock()
    yield
    app.state.executor.shutdown(wait=False)


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

    installation_id: int | None = None
    installation = payload.get("installation")
    if installation:
        installation_id = installation["id"]

    with request.app.state.status_lock:
        request.app.state.job_status[delivery_id] = {
            "status": "queued",
            "delivery_id": delivery_id,
        }

    request.app.state.executor.submit(
        run_analysis_job,
        request.app.state.job_status,
        request.app.state.status_lock,
        clone_url,
        delivery_id,
        repo_name,
        github_org_id,
        org_name,
        installation_id,
    )

    return {"status": "accepted", "delivery_id": delivery_id}


@app.get("/api/reports/{org_name}")
async def get_org_reports(org_name: str):
    reports = await asyncio.to_thread(get_latest_reports_by_org_name, org_name)
    if not reports:
        raise HTTPException(status_code=404, detail="No reports found")
    return reports


@app.get("/results/{delivery_id}")
async def get_result(delivery_id: str, request: Request):
    report = await asyncio.to_thread(get_report_by_delivery_id, delivery_id)
    if report is not None:
        return report

    with request.app.state.status_lock:
        status = request.app.state.job_status.get(delivery_id)
    if status:
        return status

    raise HTTPException(status_code=404, detail="No report or job found for this delivery ID")
