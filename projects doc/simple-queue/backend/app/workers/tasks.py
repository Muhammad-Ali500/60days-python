import time
import random
import json
from datetime import datetime

from app.workers.celery_app import celery_app
from app.core.database import SessionLocal
from app.models.job import Job


def _get_db():
    """Get a DB session inside a Celery task (no FastAPI dependency injection here)."""
    return SessionLocal()


@celery_app.task(bind=True, name="app.workers.tasks.process_job")
def process_job(self, job_id: str, job_type: str):
    """
    Simulates a long-running background job.

    bind=True  → gives access to `self` (the task instance) so we can
                 update state / report progress mid-task.

    This is the core pattern:
      1. Mark job as running in DB
      2. Do the actual work (simulated here with sleep)
      3. Save result to DB
      4. Invalidate or update Redis cache
    """
    db = _get_db()
    try:
        # ── 1. Mark as RUNNING ──────────────────────────────────────
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            return {"error": "Job not found"}

        job.status = "running"
        job.celery_task_id = self.request.id
        db.commit()

        # ── 2. Simulate work with progress updates ───────────────────
        steps = _get_steps_for_type(job_type)
        for i, step in enumerate(steps):
            time.sleep(random.uniform(1.5, 3.0))   # simulate real work
            progress = round(((i + 1) / len(steps)) * 100, 1)

            # Update Celery task state (visible in Flower)
            self.update_state(state="PROGRESS", meta={"progress": progress, "step": step})

            # Update DB row
            job.progress = progress
            db.commit()

        # ── 3. Build a fake result ────────────────────────────────────
        result = {
            "job_type": job_type,
            "completed_at": datetime.utcnow().isoformat(),
            "records_processed": random.randint(500, 50_000),
            "output_file": f"reports/{job_id[:8]}_output.csv",
            "summary": f"{job_type.title()} job completed successfully.",
        }

        # ── 4. Save result & mark SUCCESS ─────────────────────────────
        job.status = "success"
        job.result = json.dumps(result)
        job.progress = 100.0
        db.commit()

        return result

    except Exception as exc:
        # Mark job as FAILED in DB
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            job.status = "failed"
            job.error = str(exc)
            db.commit()
        raise exc

    finally:
        db.close()


def _get_steps_for_type(job_type: str) -> list[str]:
    steps_map = {
        "report": ["Fetching data", "Aggregating rows", "Building charts", "Exporting PDF"],
        "email":  ["Rendering template", "Validating recipients", "Sending via SMTP"],
        "export": ["Querying database", "Transforming records", "Writing CSV", "Compressing file"],
        "sync":   ["Connecting to API", "Pulling delta records", "Reconciling", "Saving"],
    }
    return steps_map.get(job_type, ["Processing", "Finalizing"])
