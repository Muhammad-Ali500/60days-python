# Prompt 29 — Production Readiness Checklist & Hardening

## Goal
Implement all production hardening: security headers, rate limiting, graceful shutdown, connection pool tuning, Redis result backend TTL, and a complete production readiness checklist with automated verification.

## Files to create / edit

---

### `app/middleware/security.py`

```python
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        # Do NOT set HSTS here — handled by Nginx
        return response
```

---

### Rate limiting (`app/middleware/rate_limit.py`)

```python
import time
from collections import defaultdict
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Simple in-process rate limiter.
    For multi-worker setups, use Redis-based slowapi instead.
    Limits: 60 requests/minute per IP for all /api/v1/ routes.
    Inference endpoints: 10 requests/minute (more expensive).
    """
    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.rpm = requests_per_minute
        self._calls: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        if not request.url.path.startswith("/api/v1/"):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        limit = 10 if "/infer/" in request.url.path else self.rpm
        now = time.time()
        window = 60.0

        # Clean old entries
        self._calls[client_ip] = [t for t in self._calls[client_ip] if now - t < window]

        if len(self._calls[client_ip]) >= limit:
            return JSONResponse(
                status_code=429,
                content={"error": "rate_limited", "message": f"Too many requests. Limit: {limit}/minute"},
                headers={"Retry-After": "60"},
            )

        self._calls[client_ip].append(now)
        return await call_next(request)
```

> Note: This in-process rate limiter is per-worker. For multi-worker production, replace with `slowapi` using Redis backend: `pip install slowapi`.

---

### Graceful shutdown (`app/main.py` — update lifespan)

```python
import signal
import asyncio
from contextlib import asynccontextmanager

shutdown_event = asyncio.Event()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    configure_logging()
    log.info("starting AIP", env=settings.log_level)
    warmup_all_models(background=True)

    yield

    # Shutdown — wait for in-progress requests to complete
    log.info("shutting down AIP")
    # Give active requests 30 seconds to complete
    # Uvicorn handles this with --timeout-graceful-shutdown 30
```

In `docker-compose.yml`, add `stop_grace_period` to backend and worker:
```yaml
  backend:
    stop_grace_period: 30s

  worker:
    stop_grace_period: 60s    # longer for workers — tasks may be mid-inference
```

---

### Celery result backend TTL

In `app/workers/celery_app.py`, add result expiration:
```python
celery_app.conf.update(
    result_expires=86400,        # keep task results in Redis for 24 hours, then auto-expire
    result_backend_transport_options={
        "visibility_timeout": 3600,   # re-queue task if worker dies mid-task (1 hour)
    },
)
```

---

### Connection pool tuning

In `app/database.py`:
```python
engine = create_async_engine(
    settings.database_url,
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    pool_recycle=1800,      # recycle connections every 30 minutes
    pool_pre_ping=True,     # verify connections before using them
)
```

In `app/workers/db_session.py` (sync engine):
```python
sync_engine = create_engine(
    settings.sync_database_url,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=1800,
)
```

---

### `backend/scripts/readiness_check.py`

Automated pre-deploy readiness verification:

```python
"""
Run before deployment to verify the system is production-ready.
Checks: database connectivity, Redis, MinIO, models loaded, migrations current.
Exit 0 = ready. Exit 1 = not ready.
"""
import asyncio, sys
from app.config import settings

async def check_postgres() -> tuple[bool, str]:
    try:
        from sqlalchemy.ext.asyncio import create_async_engine
        engine = create_async_engine(settings.database_url)
        async with engine.connect() as conn:
            await conn.execute(sa.text("SELECT 1"))
        await engine.dispose()
        return True, "ok"
    except Exception as e:
        return False, str(e)

async def check_redis() -> tuple[bool, str]:
    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(settings.redis_url)
        await r.ping()
        await r.aclose()
        return True, "ok"
    except Exception as e:
        return False, str(e)

async def check_minio() -> tuple[bool, str]:
    try:
        from app.services.minio_client import minio_service
        minio_service.client.list_buckets()
        return True, "ok"
    except Exception as e:
        return False, str(e)

def check_models() -> tuple[bool, str]:
    from app.scripts.check_models import check_whisper, check_pyannote, check_sentiment
    missing = []
    if not check_whisper():  missing.append("whisper")
    if not check_pyannote(): missing.append("pyannote")
    if not check_sentiment(): missing.append("sentiment")
    if missing:
        return False, f"Missing models: {missing}"
    return True, "ok"

async def check_migrations() -> tuple[bool, str]:
    try:
        from alembic.runtime.migration import MigrationContext
        from alembic.script import ScriptDirectory
        from alembic.config import Config
        # Check head revision == current DB revision
        ...
        return True, "ok"
    except Exception as e:
        return False, str(e)

async def main():
    checks = {
        "postgres":   await check_postgres(),
        "redis":      await check_redis(),
        "minio":      await check_minio(),
        "models":     check_models(),
        "migrations": await check_migrations(),
    }
    all_ok = True
    for name, (ok, msg) in checks.items():
        status = "✓" if ok else "✗"
        print(f"  {status} {name:15} {msg}")
        if not ok:
            all_ok = False
    sys.exit(0 if all_ok else 1)

asyncio.run(main())
```

---

### Production checklist (document in `docs/production-checklist.md`)

```markdown
## Before deploying to production

### Security
- [ ] All secrets in environment variables (never in git)
- [ ] HF_TOKEN set for pyannote model
- [ ] SSL certificate installed in nginx/ssl/
- [ ] DOMAIN set to actual domain
- [ ] Flower NOT exposed on public port (docker-compose.prod.yml)
- [ ] MinIO console NOT exposed on public port
- [ ] Backend port NOT exposed on public port

### Infrastructure
- [ ] PostgreSQL data volume on persistent storage (not ephemeral)
- [ ] MinIO data volume on persistent storage
- [ ] Models volume pre-populated (run download_models.py)
- [ ] DB migration applied: `alembic upgrade head`
- [ ] Redis maxmemory policy set: `maxmemory-policy allkeys-lru`

### Performance
- [ ] WHISPER_DEVICE=cuda (if GPU available)
- [ ] WHISPER_COMPUTE_TYPE=float16 (GPU) or int8 (CPU)
- [ ] CELERY_CONCURRENCY set to CPU count (GPU: 1–2)
- [ ] Uvicorn workers=2 in production

### Monitoring
- [ ] /health endpoint returning ok
- [ ] Flower accessible from server at localhost:5555
- [ ] Log output going to docker log driver
- [ ] Readiness check passes: python -m app.scripts.readiness_check
```

---

## Constraints
- `stop_grace_period: 60s` on workers is critical — models take time to finish inference, don't SIGKILL mid-task
- Rate limit middleware must be added to `app/main.py` BEFORE the request routing middleware
- `pool_pre_ping=True` is essential — cloud databases drop idle connections after a few minutes
- `result_expires=86400` prevents Redis from filling up with stale Celery task metadata
- The `RateLimitMiddleware` in-process state is not shared across uvicorn workers — document this limitation and recommend `slowapi` + Redis for multi-worker production deployments
