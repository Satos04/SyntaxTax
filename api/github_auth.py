import base64
import logging
import os
import time

import jwt
import requests

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"


def _get_private_key() -> bytes | None:
    encoded = os.getenv("GITHUB_APP_PRIVATE_KEY")
    if not encoded:
        return None
    return base64.b64decode(encoded)


def _generate_jwt(app_id: str, private_key: bytes) -> str:
    now = int(time.time())
    payload = {
        "iat": now - 60,
        "exp": now + 600,
        "iss": app_id,
    }
    return jwt.encode(payload, private_key, algorithm="RS256")


def get_installation_token(installation_id: int) -> str | None:
    app_id = os.getenv("GITHUB_APP_ID")
    private_key = _get_private_key()
    if not app_id or not private_key:
        logger.warning("GITHUB_APP_ID or GITHUB_APP_PRIVATE_KEY not set, skipping auth")
        return None

    jwt_token = _generate_jwt(app_id, private_key)
    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Accept": "application/vnd.github+json",
    }
    resp = requests.post(
        f"{GITHUB_API}/app/installations/{installation_id}/access_tokens",
        headers=headers,
        timeout=15,
    )
    if resp.status_code != 201:
        logger.error(
            "Failed to get installation token: %s %s", resp.status_code, resp.text
        )
        return None

    return resp.json()["token"]


def patch_clone_url(clone_url: str, token: str) -> str:
    return clone_url.replace("https://", f"https://x-access-token:{token}@")
