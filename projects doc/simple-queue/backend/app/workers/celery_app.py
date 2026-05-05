from celery import Celery
from app.core.config import settings

# One Celery app instance shared by worker + the API (for .delay() calls)
celery_app = Celery(
    "jobflow",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,          # lets us see "running" state in Flower
    result_expires=3600,              # results auto-deleted from Redis after 1h
    worker_prefetch_multiplier=1,     # fair dispatch — one task per worker at a time
)

# Auto-discover tasks in the workers package
celery_app.autodiscover_tasks(["app.workers"])
