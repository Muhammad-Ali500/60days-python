# Prompt 25 — Structured Logging, Prometheus Metrics & Monitoring

## Goal
Implement production-grade structured logging with structlog, add a Prometheus `/metrics` endpoint, and configure all log contexts. Every log line must carry request ID, job ID (when applicable), and component name.

## Files to create / edit

---

### `app/logging_config.py`

```python
import structlog
import logging
import sys
from app.config import settings


def configure_logging() -> None:
    """
    Configure structlog for JSON output in production, coloured ConsoleRenderer in dev.
    Call this once at app startup (in main.py lifespan, before anything else).
    """
    shared_processors = [
        structlog.contextvars.merge_contextvars,        # merge bound vars (request_id, job_id)
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if settings.log_level.upper() == "DEBUG":
        # Dev: coloured, human-readable
        renderer = structlog.dev.ConsoleRenderer(colors=True)
    else:
        # Production: JSON
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(settings.log_level.upper())

    # Silence noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("faster_whisper").setLevel(logging.INFO)
```

---

### Request ID middleware (`app/middleware/request_id.py`)

```python
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
import structlog

class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        # Bind to structlog context for this request's coroutine
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
```

Add to `app/main.py`:
```python
app.add_middleware(RequestIDMiddleware)
```

---

### Request logging middleware (`app/middleware/access_log.py`)

```python
import time
from starlette.middleware.base import BaseHTTPMiddleware

log = structlog.get_logger("access")

class AccessLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        t_start = time.perf_counter()
        response = await call_next(request)
        elapsed = round((time.perf_counter() - t_start) * 1000, 1)
        log.info(
            "request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=elapsed,
            client=request.client.host if request.client else None,
        )
        return response
```

---

### `app/metrics.py` — Prometheus metrics

```python
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi import APIRouter
from fastapi.responses import Response

# Define metrics
jobs_total = Counter(
    "aip_jobs_total",
    "Total jobs processed",
    ["source", "status"],   # labels: source=minio|realtime|direct, status=success|failed
)

job_duration_seconds = Histogram(
    "aip_job_duration_seconds",
    "Time to process a job end-to-end",
    ["task_types"],          # label: comma-separated task types
    buckets=[1, 5, 15, 30, 60, 120, 300, 600],
)

inference_duration_seconds = Histogram(
    "aip_inference_duration_seconds",
    "Time for a single model inference call",
    ["model", "endpoint"],   # model=whisper|pyannote|sentiment, endpoint=/infer/transcribe etc.
    buckets=[0.1, 0.5, 1, 2, 5, 10, 30, 60],
)

queue_depth = Gauge(
    "aip_queue_depth",
    "Current number of tasks in each Celery queue",
    ["queue_name"],
)

active_workers = Gauge(
    "aip_active_workers",
    "Number of active Celery workers",
)

models_loaded = Gauge(
    "aip_models_loaded",
    "Whether each ML model is loaded (1=yes, 0=no)",
    ["model_name"],
)

# Router
metrics_router = APIRouter()

@metrics_router.get("/metrics", include_in_schema=False)
async def prometheus_metrics():
    if not settings.enable_metrics:
        return Response("Metrics disabled", status_code=404)
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
```

**Update model services to record metrics:**

In `app/services/transcription.py` — wrap `transcribe()`:
```python
with inference_duration_seconds.labels(model="whisper", endpoint="transcribe").time():
    result = _run_transcription(audio_path, language)
```

In `app/workers/tasks.py` — after job completion:
```python
jobs_total.labels(source=job.source, status="success").inc()
job_duration_seconds.labels(task_types=",".join(sorted(job.task_types))).observe(
    (job.completed_at - job.started_at).total_seconds()
)
```

---

### Log binding for job context

In `run_pipeline` Celery task, bind job context at the start:
```python
structlog.contextvars.bind_contextvars(job_id=job_id, source=job.source)
log.info("job started", task_types=job.task_types)
```

In real-time processor:
```python
structlog.contextvars.bind_contextvars(job_id=job_id, path="realtime")
```

---

### `app/middleware/__init__.py`

Export all middleware.

---

### Celery task logging

In `app/workers/celery_app.py`, add Celery signals to log task events:

```python
from celery.signals import task_prerun, task_postrun, task_failure, task_retry

@task_prerun.connect
def on_task_start(task_id, task, args, kwargs, **kw):
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(celery_task_id=task_id, task_name=task.name)
    log.info("task started")

@task_postrun.connect
def on_task_end(task_id, task, args, kwargs, retval, state, **kw):
    log.info("task completed", state=state)

@task_failure.connect
def on_task_failure(task_id, exception, traceback, **kw):
    log.error("task failed", error=str(exception), exc_info=True)

@task_retry.connect
def on_task_retry(request, reason, einfo, **kw):
    log.warning("task retrying", reason=str(reason), retries=request.retries)
```

---

## Constraints
- `configure_logging()` must be called FIRST in `lifespan`, before any other setup
- `structlog.contextvars` is coroutine-safe in asyncio — correct choice for FastAPI
- But Celery tasks are sync — `structlog.contextvars.clear_contextvars()` must be called at start of each task (context leaks between tasks in the same worker process otherwise)
- Prometheus metrics router must be mounted WITHOUT the `/api/v1` prefix: `app.include_router(metrics_router)` at root
- `CONTENT_TYPE_LATEST` from `prometheus_client` must be used as media_type — not `text/plain`
- Log level `DEBUG` should not be used in production — log sampling or level guard for hot paths
