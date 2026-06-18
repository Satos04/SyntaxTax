import asyncio
import json
import os
import shutil
import tempfile

from arq import Retry
from arq.connections import RedisSettings
from arq.constants import retry_key_prefix

from api.database import save_report, upsert_organization
from core_analyzer.financial_model import compute_financial_impact

REDIS_SETTINGS = RedisSettings(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", "6379")),
)

MAX_JOBS_PER_ORG = int(os.getenv("MAX_JOBS_PER_ORG", "2"))


async def run_analysis_job(
    ctx: dict,
    clone_url: str,
    delivery_id: str,
    repo_name: str,
    github_org_id: int,
    org_name: str,
) -> dict | None:
    redis = ctx["redis"]
    status_key = f"syntaxtax:status:{delivery_id}"
    org_active_key = f"syntaxtax:org:{github_org_id}:active"

    active_count = await redis.scard(org_active_key)
    if active_count >= MAX_JOBS_PER_ORG:
        await redis.set(
            status_key,
            json.dumps({"status": "queued", "delivery_id": delivery_id}),
            ex=3600,
        )
        await redis.delete(retry_key_prefix + ctx["job_id"])
        raise Retry(defer=30)

    await redis.sadd(org_active_key, delivery_id)
    await redis.expire(org_active_key, 3600)

    await redis.set(
        status_key,
        json.dumps({"status": "running", "delivery_id": delivery_id}),
        ex=3600,
    )

    temp_dir = tempfile.mkdtemp(prefix="syntaxtax_")
    try:
        process = await asyncio.create_subprocess_exec(
            "git", "clone", clone_url, temp_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(process.communicate(), timeout=120)
        if process.returncode != 0:
            raise RuntimeError(f"Git clone failed: {stderr.decode().strip()}")

        report = await asyncio.to_thread(compute_financial_impact, temp_dir)
        org_uuid = await asyncio.to_thread(
            upsert_organization, github_org_id, org_name
        )
        await asyncio.to_thread(
            save_report, org_uuid, delivery_id, repo_name, report
        )

        await redis.set(
            status_key,
            json.dumps({"status": "completed", "delivery_id": delivery_id}),
            ex=3600,
        )
        return report
    except Exception as e:
        await redis.set(
            status_key,
            json.dumps({
                "status": "failed",
                "delivery_id": delivery_id,
                "error": str(e),
            }),
            ex=3600,
        )
        raise
    finally:
        await redis.srem(org_active_key, delivery_id)
        await asyncio.to_thread(shutil.rmtree, temp_dir, ignore_errors=True)


class WorkerSettings:
    functions = [run_analysis_job]
    redis_settings = REDIS_SETTINGS
    max_jobs = int(os.getenv("MAX_JOBS_PER_WORKER", "4"))
    max_tries = 3
    job_timeout = 300
