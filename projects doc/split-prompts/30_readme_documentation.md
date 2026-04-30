# Prompt 30 — README, Developer Documentation & Final Wiring

## Goal
Write the complete README.md, ensure all components are correctly wired together (imports, router registration, middleware order), and do a final integration pass to close any gaps between prompts.

## Files to create / edit

---

### `README.md` (root level)

````markdown
# Audio Intelligence Platform (AIP)

Self-hosted audio transcription, speaker segmentation, and sentiment analysis.  
No external API calls. All processing on your own hardware.

## What it does

- **Transcription** — Convert audio to text using [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (Whisper large-v3)
- **Segmentation** — Identify and label speakers using [pyannote.audio](https://github.com/pyannote/pyannote-audio)
- **Sentiment Analysis** — Per-segment emotional tone using [cardiffnlp/twitter-roberta-base-sentiment](https://huggingface.co/cardiffnlp/twitter-roberta-base-sentiment-latest)

## Three processing modes

| Mode | How | When to use |
|------|-----|-------------|
| **Queue** | Files in MinIO → polled by Celery workers | Bulk async processing |
| **Real-time** | Upload via GUI → immediate WebSocket streaming | Interactive use |
| **Direct API** | POST to `/infer/*` endpoints | Programmatic callers |

## Quick start (local dev)

```bash
# 1. Clone and configure
git clone https://github.com/your-org/audio-intelligence-platform
cp .env.example .env
# Edit .env: set HF_TOKEN (required for pyannote on first run)

# 2. Start all services
docker compose up --build -d

# 3. Run migrations
docker compose exec backend alembic upgrade head

# 4. Download ML models (first run — takes 5–15 minutes)
docker compose exec worker python -m app.scripts.download_models

# 5. Seed dev data (optional)
docker compose exec backend python -m app.scripts.seed_dev_data
```

After startup:
| Service | URL |
|---------|-----|
| Frontend | http://localhost (Nginx) or http://localhost:3000 |
| API docs | http://localhost:8000/docs |
| Flower | http://localhost:5555 |
| MinIO console | http://localhost:9001 |

## API quick reference

### Direct inference

```bash
# Transcribe a file
curl -X POST http://localhost:8000/api/v1/infer/transcribe \
  -F "file=@recording.mp3"

# Segment speakers
curl -X POST http://localhost:8000/api/v1/infer/segment \
  -F "file=@recording.mp3"

# Sentiment on text
curl -X POST http://localhost:8000/api/v1/infer/sentiment \
  -F "text=I love this product" \
  -F "chunk_by=sentence"

# Full pipeline and save to DB
curl -X POST "http://localhost:8000/api/v1/infer/pipeline?save=true&task_types=transcription,segmentation,sentiment" \
  -F "file=@recording.mp3"

# From MinIO reference
curl -X POST http://localhost:8000/api/v1/infer/transcribe \
  -F 'minio_ref={"bucket":"audio-uploads","object_key":"calls/recording.wav"}'
```

### Jobs API

```bash
# List jobs
curl http://localhost:8000/api/v1/jobs?status=success&page=1&limit=10

# Get job detail
curl http://localhost:8000/api/v1/jobs/{job_id}

# Retry failed job
curl -X POST http://localhost:8000/api/v1/jobs/{job_id}/retry

# Export as SRT
curl http://localhost:8000/api/v1/jobs/{job_id}/export?format=srt -o output.srt
```

## Scaling workers

```bash
# Scale to 4 GPU workers
docker compose up --scale worker=4 -d

# CPU-only mode (no GPU)
WHISPER_DEVICE=cpu WHISPER_COMPUTE_TYPE=int8 docker compose up -d
```

## Production deployment

```bash
# On your server:
cp .env.example .env
# Set: all secrets, DOMAIN, SSL cert paths, WHISPER_DEVICE=cuda

docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
docker compose exec backend alembic upgrade head
```

See [docs/production-checklist.md](docs/production-checklist.md) before going live.

## Models used

| Task | Model | Licence | Download size |
|------|-------|---------|--------------|
| Transcription | faster-whisper large-v3 | MIT | ~3 GB |
| Segmentation | pyannote/speaker-diarization-3.1 | CC BY 4.0 | ~400 MB |
| Sentiment | cardiffnlp/twitter-roberta-base-sentiment-latest | MIT | ~500 MB |

> pyannote requires accepting the model licence on HuggingFace and setting `HF_TOKEN`.

## Architecture

See [SPEC_SHEET.md](SPEC_SHEET.md) for full architecture documentation.
````

---

### Final wiring checklist — `app/main.py` (complete version)

Ensure this order in the final `main.py`:

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.logging_config import configure_logging
from app.config import settings
from app.middleware.request_id import RequestIDMiddleware
from app.middleware.access_log import AccessLogMiddleware
from app.middleware.security import SecurityHeadersMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.exception_handlers import (
    validation_exception_handler, http_exception_handler,
    model_not_loaded_handler, audio_error_handler, minio_error_handler,
    job_error_handler, job_state_handler, generic_exception_handler,
)
from app.routers import health, jobs, realtime, infer, queue
from app.metrics import metrics_router
from app.workers.warmup import warmup_all_models
from app.exceptions import (
    ModelNotLoadedError, AudioProcessingError, MinIOError,
    JobNotFoundError, JobStateError,
)

import structlog
log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    log.info("AIP starting", version="1.0.0", env=settings.log_level)
    warmup_all_models(background=True)
    yield
    log.info("AIP shutting down")


app = FastAPI(
    title="Audio Intelligence Platform",
    version="1.0.0",
    docs_url="/docs" if settings.log_level == "DEBUG" else None,
    redoc_url=None,
    lifespan=lifespan,
)

# Middleware — ORDER MATTERS (outermost first)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware, requests_per_minute=60)
app.add_middleware(AccessLogMiddleware)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],   # frontend only
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handlers — specific before generic
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(ModelNotLoadedError, model_not_loaded_handler)
app.add_exception_handler(AudioProcessingError, audio_error_handler)
app.add_exception_handler(MinIOError, minio_error_handler)
app.add_exception_handler(JobNotFoundError, job_error_handler)
app.add_exception_handler(JobStateError, job_state_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# Routers
app.include_router(metrics_router)              # /metrics (no prefix)
app.include_router(health.router,   prefix="/api/v1")
app.include_router(jobs.router,     prefix="/api/v1/jobs",    tags=["jobs"])
app.include_router(realtime.router, prefix="/api/v1/realtime", tags=["realtime"])
app.include_router(infer.router,    prefix="/api/v1/infer",   tags=["inference"])
app.include_router(queue.router,    prefix="/api/v1",         tags=["queue"])
```

---

### `frontend/next.config.ts` (complete)

```typescript
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  experimental: {
    serverActions: { allowedOrigins: ["localhost:3000"] },
  },
  async rewrites() {
    // Proxy /api/* from frontend server → backend (server-side only)
    // This keeps the backend truly internal — browser never knows backend URL
    return [
      {
        source: "/api/v1/:path*",
        destination: `${process.env.NEXT_PUBLIC_API_URL}/:path*`,
      },
    ];
  },
};

export default nextConfig;
```

With this rewrite, the browser calls `/api/v1/jobs` → Next.js server proxies to `http://backend:8000/api/v1/jobs`. The backend is never reachable from the internet.

Update `src/lib/api.ts` to use relative URL:
```typescript
// Use relative URL — Next.js proxy handles routing to backend
const API_BASE = "/api/v1";
const WS_BASE  = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000/api/v1";
// Note: WebSocket cannot be proxied by Next.js rewrites; WS connects directly to backend
// In production, expose WS port through Nginx with upgrade headers or use a WS-specific path
```

---

### Final environment variables to add to `.env.example`

```bash
# Node (frontend)
NODE_ENV=development
NEXT_PUBLIC_API_URL=http://backend:8000/api/v1
NEXT_PUBLIC_WS_URL=ws://localhost:8000/api/v1

# Nginx
DOMAIN=localhost
```

---

### `docs/` directory

Create these docs (stubs — content from spec sheet):

```
docs/
├── production-checklist.md    ← from Prompt 29
├── architecture.md            ← system diagram + data flow description
├── api-reference.md           ← link to /docs or summarise endpoints
└── model-setup.md             ← HF token setup, pyannote licence acceptance steps
```

---

## Final integration notes

1. **WebSocket in production via Nginx:** Add this to `nginx.conf` if direct WS access is needed:
   ```nginx
   location /api/v1/realtime/stream/ {
       proxy_pass http://backend:8000;
       proxy_http_version 1.1;
       proxy_set_header Upgrade $http_upgrade;
       proxy_set_header Connection "upgrade";
   }
   ```

2. **Model loading race:** The API starts before models are loaded (background warm-up). All inference endpoints check `is_model_loaded()` and return 503 if not ready. Clients should retry on 503 with the `Retry-After` header.

3. **MinIO bucket creation:** The worker auto-creates buckets on startup via `minio_service.ensure_buckets_exist()`. No manual bucket creation needed.

4. **First-time setup summary:**
   - Set `HF_TOKEN` in `.env` (one-time)
   - Run `download_models.py` (one-time, ~10 min)
   - Run `alembic upgrade head` (every deploy)
   - Run `seed_dev_data.py` (dev only)

---

## Constraints
- `docs_url=None` in production (`log_level != DEBUG`) — never expose Swagger UI publicly
- Next.js rewrite proxies API but NOT WebSocket — WS must either be exposed via Nginx upgrade or handled via a Next.js API route that upgrades the connection (document the tradeoff)
- README must include the `HF_TOKEN` requirement prominently — pyannote will silently fail without it
- CORS origins must be locked to the frontend origin only — not `allow_origins=["*"]` in production
