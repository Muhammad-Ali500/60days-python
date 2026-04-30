# Prompt 05 — MinIO Client Service

## Goal
Build the MinIO client service that handles all object storage operations: listing objects, downloading files, moving processed files, and polling for new unprocessed objects.

## File to create: `app/services/minio_client.py`

### Class: `MinIOService`

Initialise with `minio.Minio` client using settings from `app.config.settings`.

```python
class MinIOService:
    def __init__(self): ...   # builds Minio client from settings, no async needed (Minio SDK is sync)
```

#### Methods to implement

**`ensure_buckets_exist(buckets: list[str]) -> None`**
- For each bucket in the list, call `client.make_bucket()` only if it doesn't already exist
- Log bucket creation vs. already-exists at INFO level
- Called at worker startup

**`list_unprocessed_objects(bucket: str, prefix: str = "") -> list[ObjectInfo]`**
- List all objects in `bucket` that do NOT start with `settings.minio_processed_prefix`
- Filter out directory markers (objects ending with `/`)
- Return list of `ObjectInfo(bucket, key, size, last_modified, etag)`
- Supported audio extensions only: `.mp3 .wav .flac .ogg .m4a .webm .mp4`

**`download_to_temp(bucket: str, object_key: str) -> Path`**
- Download the object to a system temp directory
- Filename: `{uuid4}_{original_filename}` (prefix with UUID to avoid collisions)
- Return the `Path` to the temp file
- Raise `MinIODownloadError` if object does not exist or download fails

**`mark_processed(bucket: str, object_key: str) -> None`**
- Copy object to `{bucket}/{settings.minio_processed_prefix}{object_key}`
- Delete the original object
- Log the operation
- If either step fails, log error and do NOT raise (best-effort — don't fail the job over this)

**`get_object_metadata(bucket: str, object_key: str) -> ObjectMetadata`**
- Call `client.stat_object()`
- Return `ObjectMetadata(size_bytes, content_type, last_modified, etag)`

**`object_exists(bucket: str, object_key: str) -> bool`**
- Return True if the object exists, False if `NoSuchKey` exception raised

### Dataclasses to define in the same file

```python
@dataclass
class ObjectInfo:
    bucket: str
    key: str
    size: int
    last_modified: datetime
    etag: str

    @property
    def filename(self) -> str:
        return self.key.split("/")[-1]

@dataclass
class ObjectMetadata:
    size_bytes: int
    content_type: str | None
    last_modified: datetime
    etag: str
```

### Custom exceptions (define in `app/exceptions.py` and import here)

```python
class MinIODownloadError(Exception): ...
class MinIOObjectNotFoundError(MinIODownloadError): ...
```

### Singleton instance

At module bottom:
```python
minio_service = MinIOService()
```

Import as: `from app.services.minio_client import minio_service`

## File to create: `app/services/minio_poller.py`

This is the Celery Beat task that polls MinIO for new audio files.

### Function: `poll_minio_for_new_files()`

This is called by Celery Beat on a schedule (every `settings.minio_poll_interval_seconds`).

Logic:
1. For each bucket in `settings.minio_watch_buckets_list`:
   a. Call `minio_service.list_unprocessed_objects(bucket)`
   b. For each object:
      - Check DB: does a job with `minio_bucket=bucket, minio_object_key=key, status IN ('pending','processing','success')` already exist?
      - If yes AND `settings.reprocess_duplicates=False` → skip
      - If no (or reprocess enabled) → create a new `Job` record with `status='pending'`, `source='minio'`, then dispatch a Celery task
   c. Update `minio_poll_state` table: set `last_polled_at=now()`, `last_object_key` = last key seen
2. Log count of new jobs dispatched per bucket

Use a sync DB session (not async) since this runs inside a Celery task, not FastAPI. Use `sqlalchemy` with `psycopg2` driver for the sync session.

## Constraints
- MinIO SDK (`minio` package) is synchronous — do not wrap in `asyncio.run_in_executor` for the service class
- FastAPI endpoints that call `minio_service` methods should use `run_in_executor` since the methods are blocking
- Always clean up temp files — document that callers are responsible for deletion (use `try/finally` or context manager)
- Log all MinIO errors with `structlog` at ERROR level, include bucket and object_key in log context
