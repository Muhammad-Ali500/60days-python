# Prompt 03 — FastAPI App Factory & Configuration

## Goal
Build the FastAPI application entry point, Pydantic settings, structured logging, and wire up all routers. The app should start cleanly with `uvicorn app.main:app`.

## Files to create / edit

### `app/config.py`
Use `pydantic-settings` `BaseSettings`. Read all values from environment / `.env` file.

```python
class Settings(BaseSettings):
    # PostgreSQL
    postgres_host: str
    postgres_port: int = 5432
    postgres_db: str
    postgres_user: str
    postgres_password: str

    @property
    def database_url(self) -> str:
        return f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

    @property
    def sync_database_url(self) -> str:
        # Used by Alembic (sync driver)
        return f"postgresql+psycopg2://..."

    # Redis
    redis_url: str

    # MinIO
    minio_endpoint: str
    minio_access_key: str
    minio_secret_key: str
    minio_use_ssl: bool = False
    minio_watch_buckets: str = "audio-uploads"
    minio_processed_prefix: str = "processed/"
    minio_poll_interval_seconds: int = 30

    @property
    def minio_watch_buckets_list(self) -> list[str]:
        return [b.strip() for b in self.minio_watch_buckets.split(",")]

    # Models
    whisper_model_size: str = "large-v3"
    whisper_device: str = "cuda"
    whisper_compute_type: str = "float16"
    pyannote_model: str = "pyannote/speaker-diarization-3.1"
    sentiment_model: str = "cardiffnlp/twitter-roberta-base-sentiment-latest"
    hf_token: str = ""
    models_dir: str = "/models"

    # Celery
    celery_concurrency: int = 4
    celery_max_retries: int = 3
    celery_retry_backoff: int = 60

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    realtime_max_file_mb: int = 200
    websocket_connect_timeout_seconds: int = 60
    log_level: str = "INFO"

    # Feature flags
    reprocess_duplicates: bool = False
    enable_metrics: bool = True

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

settings = Settings()
```

### `app/main.py`
```python
# FastAPI app factory with:
# - lifespan context manager (startup: log config, run DB health check; shutdown: close connections)
# - CORS middleware: allow origins from env, or localhost for dev
# - Include all routers with prefix /api/v1:
#     /api/v1/jobs        ← from routers.jobs
#     /api/v1/realtime    ← from routers.realtime
#     /api/v1/infer       ← from routers.infer
#     /api/v1/queue       ← from routers.queue
#     /api/v1/health      ← from routers.health (create a stub)
#     /api/v1/minio       ← from routers.queue (minio sub-routes)
# - Custom exception handlers:
#     RequestValidationError → 422 with structured body
#     HTTPException → pass-through
#     Exception → 500 with error id (never expose traceback in production)
# - structlog configured for JSON output in production, pretty-print in dev
# - OpenAPI docs at /docs (disable in production via env flag)
```

### `app/routers/health.py`
Two endpoints:

**`GET /api/v1/health`**
Response:
```json
{
  "status": "ok",
  "postgres": "ok" | "error",
  "redis": "ok" | "error",
  "minio": "ok" | "error",
  "uptime_seconds": 142
}
```
- Each check has a 2-second timeout; if it fails, field = "error" but HTTP status still 200 (degraded, not down)
- Track startup time at module level to compute uptime

**`GET /api/v1/health/models`**
Response:
```json
{
  "whisper": { "loaded": true, "model_size": "large-v3", "device": "cuda" },
  "pyannote": { "loaded": true, "model": "pyannote/speaker-diarization-3.1" },
  "sentiment": { "loaded": false, "model": "cardiffnlp/twitter-roberta-base-sentiment-latest" }
}
```
- Read loaded state from the model singleton (see Prompt 08–10). If models not yet loaded, `loaded: false`.

### `app/logging_config.py`
Configure `structlog`:
- JSON renderer in production (`LOG_LEVEL != DEBUG`)
- ConsoleRenderer (coloured) in development
- Bind `request_id` to every log line via middleware
- Add a FastAPI middleware that generates a UUID request ID, binds it to structlog context, and adds `X-Request-ID` response header

## Constraints
- `settings` must be importable as a singleton: `from app.config import settings`
- App must start with zero routers implemented yet (stubs are fine — each router file just returns `[]` or `{}`)
- No hardcoded strings anywhere — everything from `settings`
- The lifespan must not crash if DB is unreachable at startup — log a warning and continue
