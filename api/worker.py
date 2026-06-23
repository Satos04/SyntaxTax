import logging
import shutil
import subprocess
import tempfile
import threading

from api.database import save_report, upsert_organization
from core_analyzer.financial_model import compute_financial_impact

logger = logging.getLogger(__name__)


def run_analysis_job(
    job_status: dict,
    status_lock: threading.Lock,
    clone_url: str,
    delivery_id: str,
    repo_name: str,
    github_org_id: int,
    org_name: str,
) -> None:
    logger.info("Starting analysis for delivery_id=%s repo=%s", delivery_id, repo_name)
    with status_lock:
        job_status[delivery_id] = {"status": "running", "delivery_id": delivery_id}

    temp_dir = tempfile.mkdtemp(prefix="syntaxtax_")
    try:
        logger.info("Cloning %s into %s", clone_url, temp_dir)
        result = subprocess.run(
            ["git", "clone", clone_url, temp_dir],
            capture_output=True,
            timeout=120,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Git clone failed: {result.stderr.decode().strip()}")

        logger.info("Clone successful, running analysis")
        report = compute_financial_impact(temp_dir)
        logger.info("Analysis complete, saving to database")
        org_uuid = upsert_organization(github_org_id, org_name)
        save_report(org_uuid, delivery_id, repo_name, report)

        with status_lock:
            job_status[delivery_id] = {"status": "completed", "delivery_id": delivery_id}
        logger.info("Analysis completed successfully for %s", delivery_id)
    except Exception as e:
        logger.error("Analysis failed for %s: %s", delivery_id, str(e), exc_info=True)
        with status_lock:
            job_status[delivery_id] = {
                "status": "failed",
                "delivery_id": delivery_id,
                "error": str(e),
            }
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
