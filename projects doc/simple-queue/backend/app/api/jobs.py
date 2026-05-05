from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.redis_client import get_redis
from app.services.job_service import (
    JobCreate, JobRead, StatsRead,
    create_job, get_job, list_jobs, get_stats,
    invalidate_stats_cache,
)

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("/", response_model=JobRead, status_code=201)
def submit_job(payload: JobCreate, db: Session = Depends(get_db), redis=Depends(get_redis)):
    """
    Submit a new background job.
    Creates a DB row, fires a Celery task, invalidates the stats cache.
    """
    job = create_job(db, payload)
    invalidate_stats_cache(redis)   # stats changed → bust cache
    return _to_read(job)


@router.get("/", response_model=list[JobRead])
def fetch_jobs(limit: int = 50, db: Session = Depends(get_db)):
    """List all jobs, newest first."""
    return [_to_read(j) for j in list_jobs(db, limit)]


@router.get("/stats", response_model=StatsRead)
def fetch_stats(db: Session = Depends(get_db), redis=Depends(get_redis)):
    """
    Return aggregate counts.
    Result is cached in Redis for CACHE_TTL seconds (default 300s).
    """
    return get_stats(db, redis)


@router.get("/{job_id}", response_model=JobRead)
def fetch_job(job_id: str, db: Session = Depends(get_db)):
    """Fetch a single job by UUID."""
    job = get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return _to_read(job)


# ── Helpers ───────────────────────────────────────────────────────────────────

import json

def _to_read(job) -> JobRead:
    """Convert ORM model to Pydantic schema, parsing the result JSON string."""
    return JobRead(
        id=str(job.id),
        name=job.name,
        job_type=job.job_type,
        status=job.status,
        progress=job.progress or 0.0,
        result=json.loads(job.result) if job.result else None,
        error=job.error,
        created_at=job.created_at,
        updated_at=job.updated_at,
        celery_task_id=job.celery_task_id,
    )
