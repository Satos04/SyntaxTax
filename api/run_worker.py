"""Entrypoint para el worker ARQ.

Uso:
    python -m api.run_worker
"""
from arq import run_worker
from api.worker import WorkerSettings

if __name__ == "__main__":
    run_worker(WorkerSettings)
