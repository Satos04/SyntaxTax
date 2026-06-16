import hashlib
import hmac
import os

from fastapi import FastAPI, HTTPException, Request

app = FastAPI(title="SyntaxTax API", version="0.1.0")

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

    print(f"Received event: {event}, payload: {body.decode()}")
    return {"message": "Event received"}
