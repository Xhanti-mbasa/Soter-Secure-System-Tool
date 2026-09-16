import asyncio

from celery import Celery

from secure.config import get_settings
from secure.scan.orchestrator import run_scan

settings = get_settings()
celery_app = Celery("secure", broker=settings.celery_broker_url, backend=settings.celery_result_backend)
celery_app.conf.update(task_track_started=True, task_time_limit=330, task_soft_time_limit=300)


@celery_app.task(name="secure.run_scan", bind=True)
def run_scan_task(self, scan_id: str) -> None:
    asyncio.run(run_scan(scan_id))
