import hashlib
import hmac
import json
import os
import shutil
import subprocess
import tempfile
from asyncio import get_event_loop
from concurrent.futures import ThreadPoolExecutor

from core_analyzer.financial_model import compute_financial_impact
from api.database import save_report, upsert_organization
from fastapi import FastAPI, HTTPException, Request

app = FastAPI(title="SyntaxTax API", version="0.1.0")

WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET", "")
_executor = ThreadPoolExecutor(max_workers=4)
analysis_results: dict[str, dict] = {}


def run_analysis(
    clone_url: str,
    delivery_id: str,
    repo_name: str,
    github_org_id: int,
    org_name: str,
) -> None:
    temp_dir = tempfile.mkdtemp(prefix="syntaxtax_")
    try:
        subprocess.run(
            ["git", "clone", clone_url, temp_dir],
            capture_output=True, text=True, check=True,
        )
        report = compute_financial_impact(temp_dir)
        org_uuid = upsert_organization(github_org_id, org_name)
        save_report(org_uuid, delivery_id, repo_name, report)
        analysis_results[delivery_id] = {"status": "done", "result": report}
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.strip()
        analysis_results[delivery_id] = {
            "status": "error", "detail": f"Git clone failed: {stderr}"
        }
    except Exception as e:
        analysis_results[delivery_id] = {
            "status": "error", "detail": str(e)
        }
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


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

    analysis_results[delivery_id] = {"status": "pending"}
    loop = get_event_loop()
    loop.run_in_executor(
        _executor, run_analysis,
        clone_url, delivery_id, repo_name, github_org_id, org_name,
    )

    return {"status": "accepted", "delivery_id": delivery_id}
