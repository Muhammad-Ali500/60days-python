import json
import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.models.job import Job
from app.core.config import settings
from app.workers.tasks import process_job


STATS_CACHE_KEY = "jobflow:stats"


# ── Pydantic schemas (defined here for simplicity) ────────────────────────────
from pydantic import BaseModel
from datetime import datetime


class JobCreate(BaseModel):
    name: str
    job_type: str   # report | email | export | sync


class JobRead(BaseModel):
    id: str
    name: str
    job_type: str
    status: str
    progress: float
    result: Optional[dict] = None
    error: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    celery_task_id: Optional[str] = None

    class Config:
        from_attributes = True


class StatsRead(BaseModel):
    total: int
    pending: int
    running: int
    success: int
    failed: int


# ── Service functions ─────────────────────────────────────────────────────────

def create_job(db: Session, payload: JobCreate) -> Job:
    """Create DB row → dispatch Celery task → return the row."""
    job = Job(
        id=uuid.uuid4(),
        name=payload.name,
        job_type=payload.job_type,
        status="pending",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # Fire the Celery task asynchronously
    # .delay() puts the message on the Redis broker queue
    process_job.delay(str(job.id), job.job_type)

    return job


def get_job(db: Session, job_id: str) -> Optional[Job]:
    return db.query(Job).filter(Job.id == job_id).first()


def list_jobs(db: Session, limit: int = 50) -> list[Job]:
    return db.query(Job).order_by(Job.created_at.desc()).limit(limit).all()


def get_stats(db: Session, redis_client) -> StatsRead:
    """
    Return job counts — cached in Redis to avoid hitting DB on every poll.

    Pattern:
      1. Try to read from Redis cache
      2. On cache miss → query DB → write back to Redis with TTL
      3. Return data

    This is the classic cache-aside pattern.
    """
    cached = redis_client.get(STATS_CACHE_KEY)
    if cached:
        data = json.loads(cached)
        return StatsRead(**data)

    # Cache miss — query the database
    jobs = db.query(Job).all()
    stats = StatsRead(
        total=len(jobs),
        pending=sum(1 for j in jobs if j.status == "pending"),
        running=sum(1 for j in jobs if j.status == "running"),
        success=sum(1 for j in jobs if j.status == "success"),
        failed=sum(1 for j in jobs if j.status == "failed"),
    )

    # Write to Redis with TTL
    redis_client.setex(STATS_CACHE_KEY, settings.CACHE_TTL, json.dumps(stats.model_dump()))

    return stats


def invalidate_stats_cache(redis_client):
    """Call this whenever a job changes state so stats stay fresh."""
    redis_client.delete(STATS_CACHE_KEY)
