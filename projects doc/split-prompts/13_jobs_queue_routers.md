# Prompt 13 — Jobs Router & Queue Management Router

## Goal
Implement the REST endpoints for job management (CRUD, retry) and queue management (stats, MinIO controls, Flower link). These are pure database/Celery-interaction endpoints — no ML code here.

## Files to create

---

### `app/routers/jobs.py`

#### `GET /api/v1/jobs`

```python
@router.get("/", response_model=JobListResponse)
async def list_jobs(
    status: JobStatus | None = Query(default=None),
    source: JobSource | None = Query(default=None),
    search: str | None = Query(default=None, max_length=200),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    Build SQLAlchemy query:
    - Base: SELECT * FROM jobs ORDER BY created_at DESC
    - Filter by status if provided
    - Filter by source if provided
    - Filter by original_filename ILIKE %search% if provided
    - Filter by created_at >= date_from if provided
    - Filter by created_at <= date_to if provided
    - COUNT(*) for total (same filters, no pagination)
    - Apply OFFSET (page-1)*limit LIMIT limit
    - Return JobListResponse with items, total, page, limit, pages=ceil(total/limit)
    """
```

#### `GET /api/v1/jobs/{job_id}`

```python
@router.get("/{job_id}", response_model=JobDetail)
async def get_job(job_id: UUID, db: AsyncSession = Depends(get_db)):
    """
    SELECT job with:
    - LEFT JOIN transcription (one-to-one)
    - LEFT JOIN segments (one-to-many), ORDER BY segment_index
    - LEFT JOIN sentiment_results JOIN'd to segments

    Build JobDetail response:
    - For each segment, attach matching sentiment result (where segment_id = segment.id)
    - Compute SentimentSummary from all sentiment results for the job:
        positive_pct = count(label='positive') / total * 100
        dominant label = label with highest percentage
    - If transcription.words_json is not None, deserialise JSONB to list[WordTimestamp]

    Raise HTTP 404 if job not found.
    """
```

#### `DELETE /api/v1/jobs/{job_id}`

```python
@router.delete("/{job_id}", status_code=204)
async def delete_job(job_id: UUID, db: AsyncSession = Depends(get_db)):
    """
    - Find job, raise 404 if not found
    - If job.status == 'processing': raise HTTP 409 "Cannot delete a job that is currently processing"
    - DELETE FROM jobs WHERE id = job_id (CASCADE handles related rows)
    - Commit
    - Return 204 No Content
    """
```

#### `POST /api/v1/jobs/{job_id}/retry`

```python
@router.post("/{job_id}/retry", response_model=JobSummary)
async def retry_job(job_id: UUID, db: AsyncSession = Depends(get_db)):
    """
    - Find job, raise 404 if not found
    - If job.status not in ('failed', 'dead'): raise HTTP 409 "Only failed or dead jobs can be retried"
    - Reset job: status='pending', retry_count=0, error_message=None, started_at=None, completed_at=None
    - Delete existing results: transcription, segments, sentiment for this job
    - Dispatch Celery task: run_pipeline.delay(str(job_id))
    - Update job.celery_task_id = task.id
    - Commit
    - Return updated JobSummary
    """
```

#### `GET /api/v1/jobs/{job_id}/export`

```python
@router.get("/{job_id}/export")
async def export_job(
    job_id: UUID,
    format: str = Query(default="json", pattern="^(json|txt|srt)$"),
    db: AsyncSession = Depends(get_db),
):
    """
    Fetch job detail (same as GET /{job_id}).
    Raise 404 if not found. Raise 400 if job not 'success' status.

    format=json:
        Return full JobDetail as JSON file download
        Content-Disposition: attachment; filename="{original_filename}_{job_id}.json"

    format=txt:
        Return plain text transcript
        If no transcription: 400 "No transcription available"
        Content: full_text only
        Content-Disposition: attachment; filename="{stem}.txt"

    format=srt:
        Return SRT subtitle file built from segments
        If no segments: 400 "No segments available"
        SRT format:
            1
            00:00:01,234 --> 00:00:04,567
            SPEAKER_00: text here
            (blank line)
            2
            ...
        Content-Disposition: attachment; filename="{stem}.srt"

    Use StreamingResponse with appropriate media type.
    """
```

---

### `app/routers/queue.py`

#### `GET /api/v1/queue/stats`

```python
@router.get("/stats", response_model=QueueStats)
async def queue_stats():
    """
    Connect to Celery via celery_app.control.inspect()
    - active() → count active tasks across all workers
    - reserved() → count reserved (queued) tasks
    - scheduled() → count scheduled tasks
    Get failed task count from Redis result backend:
        celery_app.backend.client.keys("celery-task-meta-*") filtered by state==FAILURE
    Get total processed from DB: COUNT(*) FROM jobs WHERE status='success'
    Count active workers from inspect().ping()
    Return QueueStats(...)
    """
```

#### `POST /api/v1/queue/purge`

```python
@router.post("/purge", status_code=200)
async def purge_queue(db: AsyncSession = Depends(get_db)):
    """
    Purge all pending Celery tasks: celery_app.control.purge()
    Update all jobs with status='pending' → status='failed', error_message='Purged by admin'
    Return { "purged_tasks": N, "updated_jobs": N }
    """
```

#### `GET /api/v1/minio/buckets`

```python
@router.get("/minio/buckets", response_model=list[MinioBucketInfo])
async def list_minio_buckets(db: AsyncSession = Depends(get_db)):
    """
    SELECT * FROM minio_poll_state ORDER BY bucket
    Return list of MinioBucketInfo
    """
```

#### `POST /api/v1/minio/poll`

```python
@router.post("/minio/poll")
async def trigger_minio_poll():
    """
    Manually dispatch poll_minio Celery task immediately:
    task = poll_minio.delay()
    Return { "task_id": task.id, "message": "MinIO poll triggered" }
    """
```

---

## Constraints
- All DB queries use the async session (not sync) — these are FastAPI routes
- `list_jobs` total count must be a separate COUNT query (not `len(results)`) for correct pagination
- `retry_job` must run DELETE + INSERT + task dispatch in a single DB transaction — roll back everything if task dispatch fails
- Export endpoints use `StreamingResponse` — never load full file into memory
- SRT timecodes format: `HH:MM:SS,mmm` (comma not dot — SRT spec requires comma)
- Queue stats endpoint has a 3-second timeout on Celery inspect — if no workers respond, return zeros (not an error)
