# Prompt 10 — Celery App, Tasks & Queue Configuration

## Goal
Set up the Celery application, define all task functions with retry logic, configure two queues (GPU and CPU), and wire up Celery Beat for MinIO polling.

## Files to create

---

### `app/workers/celery_app.py`

```python
from celery import Celery
from app.config import settings

celery_app = Celery(
    "aip",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,           # ack only after task completes (safe retries)
    worker_prefetch_multiplier=1,  # one task at a time per worker slot
    task_routes={
        "app.workers.tasks.run_transcription": {"queue": "gpu_queue"},
        "app.workers.tasks.run_segmentation":  {"queue": "gpu_queue"},
        "app.workers.tasks.run_pipeline":      {"queue": "gpu_queue"},
        "app.workers.tasks.run_sentiment":     {"queue": "cpu_queue"},
        "app.workers.tasks.poll_minio":        {"queue": "celery"},      # default queue
    },
    beat_schedule={
        "poll-minio": {
            "task": "app.workers.tasks.poll_minio",
            "schedule": settings.minio_poll_interval_seconds,  # seconds
            "options": {"queue": "celery"},
        }
    },
    task_default_retry_delay=settings.celery_retry_backoff,
)
```

---

### `app/workers/tasks.py`

Import the services at the top of the file (not inside task functions — this triggers model loading at worker startup):

```python
# At module level — triggers preload when worker starts
from app.services.transcription import preload_model as preload_whisper
from app.services.segmentation import preload_pipeline as preload_pyannote
from app.services.sentiment import preload_model as preload_sentiment
from app.workers.celery_app import celery_app

# Preload on worker init
@celery_app.on_after_finalize.connect
def preload_models(sender, **kwargs):
    preload_whisper()
    preload_pyannote()
    preload_sentiment()
```

---

#### Task: `run_pipeline`

This is the primary task dispatched for MinIO jobs. Runs all requested task types for a single job.

```python
@celery_app.task(
    bind=True,
    name="app.workers.tasks.run_pipeline",
    max_retries=settings.celery_max_retries,
    default_retry_delay=settings.celery_retry_backoff,
    queue="gpu_queue",
)
def run_pipeline(self, job_id: str) -> dict:
    """
    Full processing pipeline for a job.

    Steps:
    1. Load job from DB (sync session). If not found, raise ValueError (no retry).
    2. Update job status to 'processing', set started_at=now()
    3. Determine audio source:
       a. If job.source == 'minio': download from MinIO to temp file
       b. If job.source == 'realtime': file should be in a temp path stored in job metadata
    4. Normalise audio via audio_utils.normalise_audio()
    5. Get audio duration, update job.audio_duration_seconds
    6. For each task_type in job.task_types (in order: transcription → segmentation → sentiment):
       a. 'transcription': call transcription_service.transcribe_with_chunking()
          → save result to transcriptions table
       b. 'segmentation': call segmentation_service.diarise_with_chunking()
          → if transcription was also run: call align_segments_with_transcript()
          → save results to segments table
       c. 'sentiment':
          → if segments exist: call sentiment_service.analyse_segments()
          → else: call sentiment_service.analyse_chunks(transcription.text)
          → save results to sentiment_results table
    7. Update job status to 'success', set completed_at=now()
    8. If job.source == 'minio': call minio_service.mark_processed()
    9. Clean up temp files
    10. Return { "job_id": job_id, "status": "success" }
    """
```

**Error handling:**
```python
except Exception as exc:
    # Update job retry_count += 1
    # If self.request.retries >= max_retries:
    #     Set job.status = 'dead', job.error_message = str(exc)
    # Else:
    #     Set job.status = 'failed', job.error_message = str(exc)
    #     raise self.retry(exc=exc, countdown=backoff_delay(self.request.retries))
    ...

def backoff_delay(retry_number: int) -> int:
    # [60, 300, 900] seconds
    delays = [60, 300, 900]
    return delays[min(retry_number, len(delays) - 1)]
```

---

#### Task: `run_transcription`

Thin wrapper — creates a job record with `task_types=['transcription']` then calls `run_pipeline`.

```python
@celery_app.task(name="app.workers.tasks.run_transcription", queue="gpu_queue")
def run_transcription(job_id: str) -> dict:
    return run_pipeline(job_id)
```

---

#### Task: `run_segmentation`

Same pattern, `task_types=['segmentation']`.

---

#### Task: `run_sentiment`

```python
@celery_app.task(
    bind=True,
    name="app.workers.tasks.run_sentiment",
    max_retries=settings.celery_max_retries,
    queue="cpu_queue",
)
def run_sentiment(self, job_id: str) -> dict:
    # Loads existing transcription for job, runs sentiment analysis
    # Updates sentiment_results table
    ...
```

---

#### Task: `poll_minio`

```python
@celery_app.task(name="app.workers.tasks.poll_minio", queue="celery")
def poll_minio() -> dict:
    from app.services.minio_poller import poll_minio_for_new_files
    result = poll_minio_for_new_files()
    return result  # { "dispatched": N, "skipped": N }
```

---

### `app/workers/db_session.py`

Synchronous SQLAlchemy session for use inside Celery tasks (Celery is not async).

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config import settings

sync_engine = create_engine(
    settings.sync_database_url,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
)

SyncSession = sessionmaker(bind=sync_engine, autocommit=False, autoflush=False)

def get_sync_db():
    db = SyncSession()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
```

---

## Constraints
- Task functions must use the sync session from `db_session.py` — NOT the async session from `database.py`
- `task_acks_late=True` means if a worker crashes mid-task, the task is re-queued automatically
- Temp files must be cleaned up in a `finally` block — never leave orphan WAV files on retry
- Job status transitions: `pending → processing → success | failed → dead` — no other transitions
- Log every state transition with `structlog` including `job_id`, `retry_count`, `task_type`
