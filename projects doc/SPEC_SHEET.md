# SPEC SHEET — Audio Intelligence Platform
**Version:** 1.0.0  
**Date:** 2026-04-30  
**Status:** Ready for Build

---

## 1. Project Overview

| Field | Value |
|-------|-------|
| **Name** | Audio Intelligence Platform (AIP) |
| **Tagline** | Production-grade audio transcription, segmentation, and sentiment analysis at scale |
| **Problem** | Applications need reliable, private, offline-capable audio processing without paying per-call third-party API costs or sending sensitive audio data to external services |
| **Target Users** | Internal application services that upload audio to MinIO; end-users who interact via the GUI for real-time processing |
| **Value Proposition** | Fully self-hosted audio intelligence pipeline — no data leaves your infrastructure, costs are fixed (hardware), and processing is controllable via both a queue (async) and a real-time (direct) path |

---

## 2. Goals & Non-Goals

### WILL do (v1)
1. Transcribe audio files using a self-hosted Whisper model (faster-whisper)
2. Perform speaker diarisation / segmentation using pyannote.audio
3. Run sentiment analysis on transcript segments using a local HuggingFace model
4. Accept jobs via two paths: **Queue path** (files polled from MinIO) and **Real-time path** (direct GUI upload → immediate result)
5. Maintain a job queue with retry logic, exponential backoff, and dead-letter handling
6. Expose a monitoring dashboard for all queue jobs (status, retries, errors, throughput)
7. Store all completed job results (transcript, segments, sentiment) in PostgreSQL
8. Serve the frontend exclusively via Nginx (domain-bound); all other services are internal only
9. Stream real-time transcription progress back to the GUI via WebSockets

### WILL NOT do (v1)
- No third-party APIs (no OpenAI, AssemblyAI, AWS Transcribe, Google Speech)
- No user authentication system (auth handled by the parent application upstream)
- No billing or subscription management
- No video file support (audio only: mp3, wav, flac, ogg, m4a, webm)
- No translation (transcription output is in source language only)
- No mobile app

---

## 3. Tech Stack

### Backend
| Layer | Choice | Reason |
|-------|--------|--------|
| Runtime | Python 3.12 | Best ML/AI ecosystem |
| API Framework | FastAPI | Async-native, automatic OpenAPI docs, WebSocket support |
| Task Queue | Celery 5.x | Mature, retry logic built-in, Flower monitoring |
| Message Broker | Redis 7 | Fast, reliable Celery broker + result backend |
| Object Storage | MinIO | S3-compatible, fully self-hosted |
| Database | PostgreSQL 16 | Relational, JSONB for flexible result storage |
| ORM | SQLAlchemy 2.x (async) + Alembic | Async queries, schema migrations |
| WebSocket | FastAPI native WebSockets | Real-time streaming to GUI |

### ML Models (all self-hosted, no external calls)
| Task | Model | Library |
|------|-------|---------|
| Transcription | `faster-whisper large-v3` | `faster-whisper` (CTranslate2, 4-10x faster than original Whisper) |
| Speaker Segmentation / Diarisation | `pyannote/speaker-diarization-3.1` | `pyannote.audio` |
| Sentiment Analysis | `cardiffnlp/twitter-roberta-base-sentiment-latest` | `transformers` + `torch` |

> **Why faster-whisper over original Whisper?** Same accuracy as `large-v3`, 4–10x throughput improvement, lower VRAM usage. Runs on CPU too (slower but functional for dev).

### Frontend
| Layer | Choice |
|-------|--------|
| Framework | Next.js 15 (App Router, React 19) |
| Language | TypeScript 5 |
| Styling | Tailwind CSS 4 + shadcn/ui |
| State | Zustand (global) + TanStack Query v5 (server state) |
| WebSocket Client | Native browser WebSocket API wrapped in a custom React hook |
| File Upload | React Dropzone |
| Charts (dashboard) | Recharts |

### Infrastructure
| Layer | Choice |
|-------|--------|
| Reverse Proxy | Nginx (frontend only — all other services LAN/loopback) |
| Containerisation | Docker + Docker Compose |
| Process Manager | Supervisord inside worker containers (manages model loading) |
| Monitoring | Flower (Celery dashboard) — internal port only |
| Logging | structlog → stdout → Docker log driver |
| Metrics (optional P1) | Prometheus + Grafana |

---

## 4. Architecture Overview

```
 ┌─────────────────────────────────────────────────────────────┐
 │                        INTERNET                              │
 └──────────────────────────┬──────────────────────────────────┘
                            │ HTTPS (443)
                     ┌──────▼──────┐
                     │    Nginx    │  (only public entry point)
                     └──────┬──────┘
                            │
                     ┌──────▼──────┐
                     │  Next.js 15 │  (SSR + static, port 3000 internal)
                     └──────┬──────┘
                            │ HTTP/WS (internal only)
              ┌─────────────▼──────────────┐
              │        FastAPI             │  (port 8000 internal)
              │  - REST endpoints          │
              │  - WebSocket endpoint      │
              │  - Celery task dispatcher  │
              └────┬──────────┬────────────┘
                   │          │
         ┌─────────▼──┐  ┌────▼──────┐
         │   Redis 7  │  │ PostgreSQL│
         │  (broker + │  │  (results │
         │   results) │  │   + jobs) │
         └─────────┬──┘  └───────────┘
                   │
         ┌─────────▼──────────┐
         │   Celery Workers   │  (1–N workers, GPU/CPU)
         │  - Transcription   │
         │  - Segmentation    │
         │  - Sentiment       │
         └─────────┬──────────┘
                   │
              ┌────▼─────┐
              │  MinIO   │  (object storage, internal only)
              └──────────┘

  ┌─────────────────────┐
  │  Flower Dashboard   │  (port 5555, internal only)
  └─────────────────────┘
```

### Two Processing Paths

**Path A — Queue (Async, from MinIO)**
```
Parent App → uploads file to MinIO
→ MinIO webhook / Celery beat poller detects new object
→ Celery task created (PENDING)
→ Worker picks up task, downloads file from MinIO
→ Runs transcription → segmentation → sentiment
→ Result written to PostgreSQL, job marked SUCCESS
→ Original file optionally moved to processed/ prefix in MinIO
```

**Path B — Real-time (Direct GUI upload)**
```
User uploads file via GUI drag-and-drop
→ POST /api/realtime/upload (multipart)
→ FastAPI receives file in memory (no MinIO involved)
→ Spawns async task in-process
→ WebSocket streams progress tokens back to browser
→ Final result saved to PostgreSQL + returned via WS
```

**Path C — Direct Inference (synchronous API call)**
```
Caller sends audio file (multipart) OR MinIO object reference (JSON)
→ POST /api/v1/infer/transcribe  |  /infer/segment  |  /infer/sentiment  |  /infer/pipeline
→ FastAPI runs the model(s) inline on the request thread (no Celery, no queue)
→ Returns JSON result in the HTTP response body
→ Optional: ?save=true persists result to PostgreSQL and returns a job_id
→ No WebSocket, no polling — one request, one response
```

> **When to use which path:**
> - **Path A (Queue):** Bulk/background processing of files already in MinIO. Fire-and-forget.
> - **Path B (Real-time):** GUI-driven processing with streaming progress UX.
> - **Path C (Direct):** Programmatic callers (other services, scripts, tests) that want a simple synchronous call without managing WebSockets or job polling.

### Key Design Decisions
- **Three paths, one service layer**: All three processing paths (Queue, Real-time, Direct) call the same `services/transcription.py`, `services/segmentation.py`, and `services/sentiment.py` functions. No logic is duplicated — only the delivery mechanism differs.
- **Two paths, one model loader**: ML models are loaded once at worker startup and shared across tasks via a module-level singleton — avoids reloading 1–2 GB models per job.
- **MinIO polling vs. event notifications**: Celery Beat polls MinIO every N seconds (configurable). This is simpler than setting up MinIO webhooks and handles missed events gracefully.
- **Segment-level sentiment**: Sentiment is run per diarised speaker segment, not on the full transcript. This gives richer per-speaker emotional data.
- **WebSocket for real-time**: faster-whisper supports streaming word-level outputs. These are pushed token-by-token over WebSocket so the user sees transcription as it happens.

---

## 5. Data Models / Schema

### `jobs` table
```sql
CREATE TABLE jobs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source          VARCHAR(10) NOT NULL CHECK (source IN ('minio', 'realtime')),
    status          VARCHAR(20) NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending','processing','success','failed','dead')),
    minio_bucket    TEXT,
    minio_object_key TEXT,
    original_filename TEXT NOT NULL,
    file_size_bytes BIGINT,
    audio_duration_seconds FLOAT,
    task_types      TEXT[] NOT NULL,   -- e.g. ['transcription','segmentation','sentiment']
    celery_task_id  TEXT,
    retry_count     SMALLINT DEFAULT 0,
    error_message   TEXT,
    created_at      TIMESTAMPTZ DEFAULT now(),
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ
);
CREATE INDEX idx_jobs_status ON jobs(status);
CREATE INDEX idx_jobs_created_at ON jobs(created_at DESC);
```

### `transcriptions` table
```sql
CREATE TABLE transcriptions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id      UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    language    VARCHAR(10),             -- detected language code e.g. 'en'
    full_text   TEXT NOT NULL,
    word_count  INTEGER,
    model_used  TEXT NOT NULL,           -- e.g. 'faster-whisper-large-v3'
    created_at  TIMESTAMPTZ DEFAULT now()
);
```

### `segments` table
```sql
CREATE TABLE segments (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id          UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    transcription_id UUID REFERENCES transcriptions(id) ON DELETE CASCADE,
    speaker_label   TEXT,                -- e.g. 'SPEAKER_00'
    start_time      FLOAT NOT NULL,      -- seconds
    end_time        FLOAT NOT NULL,
    text            TEXT,
    segment_index   INTEGER NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_segments_job_id ON segments(job_id);
```

### `sentiment_results` table
```sql
CREATE TABLE sentiment_results (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id      UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    segment_id  UUID REFERENCES segments(id) ON DELETE CASCADE,
    label       VARCHAR(20) NOT NULL,   -- 'positive','negative','neutral'
    score       FLOAT NOT NULL,         -- confidence 0.0–1.0
    model_used  TEXT NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_sentiment_job_id ON sentiment_results(job_id);
```

### `minio_poll_state` table
```sql
CREATE TABLE minio_poll_state (
    id              SERIAL PRIMARY KEY,
    bucket          TEXT NOT NULL,
    last_polled_at  TIMESTAMPTZ,
    last_object_key TEXT,
    UNIQUE(bucket)
);
```

---

## 6. API Design

**Base URL:** `http://localhost:8000/api/v1` (internal)  
**Protocol:** REST + WebSocket  
**Auth:** None (internal service — parent app handles auth upstream)

### Jobs

| Method | Path | Description | Request | Response |
|--------|------|-------------|---------|----------|
| `GET` | `/jobs` | List all jobs (paginated) | `?status=&page=&limit=` | `{ items: Job[], total, page }` |
| `GET` | `/jobs/{id}` | Get single job with results | — | `Job + nested results` |
| `DELETE` | `/jobs/{id}` | Delete job and results | — | `204` |
| `POST` | `/jobs/{id}/retry` | Manually retry a failed job | — | `Job` |

### Real-time Processing

| Method | Path | Description | Request | Response |
|--------|------|-------------|---------|----------|
| `POST` | `/realtime/upload` | Upload file for immediate processing | `multipart/form-data: file, task_types[]` | `{ job_id, ws_token }` |
| `WS` | `/realtime/stream/{job_id}` | WebSocket stream for live progress | — | JSON events (see below) |

**WebSocket event shapes:**
```jsonc
// Progress event
{ "event": "progress", "step": "transcription", "percent": 42 }
// Token event (real-time words)
{ "event": "token", "text": "Hello", "start": 1.2, "end": 1.6 }
// Segment event
{ "event": "segment", "speaker": "SPEAKER_00", "start": 0.0, "end": 3.4, "text": "..." }
// Sentiment event
{ "event": "sentiment", "segment_id": "...", "label": "positive", "score": 0.94 }
// Done event
{ "event": "done", "job_id": "..." }
// Error event
{ "event": "error", "message": "..." }
```

### Direct Inference Endpoints

These endpoints are **synchronous** — they run the model and return the result in the HTTP response. No queue, no WebSocket, no polling required. Designed for programmatic callers and service-to-service use.

**Input — two accepted formats (both supported on all endpoints):**
- `multipart/form-data` with a `file` field (raw audio upload)
- `application/json` with a `{ "bucket": "...", "object_key": "..." }` body (MinIO reference — worker downloads the file)

**Query params available on all endpoints:**
- `?save=true` — persist result to PostgreSQL and include `job_id` in response (default: `false`)
- `?model=medium` — override the Whisper model size for this call only (default: env `WHISPER_MODEL_SIZE`)

---

#### `POST /infer/transcribe`

Transcribe audio to text. Returns the full transcript with word-level timestamps.

**Request (multipart):**
```
POST /api/v1/infer/transcribe?save=false
Content-Type: multipart/form-data

file: <audio binary>
```

**Request (MinIO reference):**
```json
POST /api/v1/infer/transcribe
Content-Type: application/json

{ "bucket": "audio-uploads", "object_key": "calls/2026-04/recording.wav" }
```

**Response `200`:**
```jsonc
{
  "job_id": null,           // UUID string if ?save=true, else null
  "language": "en",
  "duration_seconds": 142.3,
  "model_used": "faster-whisper-large-v3",
  "text": "Hello, this is a full transcript of the audio...",
  "words": [
    { "word": "Hello",  "start": 0.00, "end": 0.42, "probability": 0.99 },
    { "word": "this",   "start": 0.50, "end": 0.71, "probability": 0.98 }
  ],
  "processing_time_seconds": 4.2
}
```

---

#### `POST /infer/segment`

Diarise audio into speaker segments. Returns labelled time-range segments. Does **not** require transcription — runs pyannote.audio directly on the audio signal.

**Response `200`:**
```jsonc
{
  "job_id": null,
  "duration_seconds": 142.3,
  "num_speakers": 2,
  "model_used": "pyannote/speaker-diarization-3.1",
  "segments": [
    { "index": 0, "speaker": "SPEAKER_00", "start": 0.00,  "end": 5.40,  "is_overlap": false },
    { "index": 1, "speaker": "SPEAKER_01", "start": 5.41,  "end": 12.80, "is_overlap": false },
    { "index": 2, "speaker": "SPEAKER_00", "start": 12.50, "end": 14.10, "is_overlap": true  }
  ],
  "processing_time_seconds": 8.1
}
```

---

#### `POST /infer/sentiment`

Analyse sentiment. Accepts **either** audio (will auto-transcribe first, then run sentiment per sentence) **or** plain text via JSON. Text input skips the transcription step entirely.

**Request (text only — skip audio processing):**
```json
POST /api/v1/infer/sentiment
Content-Type: application/json

{
  "text": "I am really happy with the service today.",
  "chunk_by": "sentence"   // "sentence" | "paragraph" | "full" — how to split for analysis
}
```

**Request (audio — will transcribe then analyse):**
```
POST /api/v1/infer/sentiment
Content-Type: multipart/form-data

file: <audio binary>
chunk_by: sentence
```

**Response `200`:**
```jsonc
{
  "job_id": null,
  "model_used": "cardiffnlp/twitter-roberta-base-sentiment-latest",
  "overall": { "label": "positive", "score": 0.87 },
  "chunks": [
    { "index": 0, "text": "I am really happy with the service today.", "label": "positive", "score": 0.94 },
    { "index": 1, "text": "However, the wait time was too long.",       "label": "negative", "score": 0.81 }
  ],
  "processing_time_seconds": 0.4
}
```

---

#### `POST /infer/pipeline`

Run any combination of transcription → segmentation → sentiment in a single call. This is the "do everything" endpoint. Tasks are executed in dependency order automatically.

**Request (multipart):**
```
POST /api/v1/infer/pipeline?save=true
Content-Type: multipart/form-data

file:        <audio binary>
task_types:  transcription,segmentation,sentiment   ← comma-separated or repeated fields
```

**Dependency rules enforced server-side:**
- `sentiment` alone → text chunks only (no audio segmentation)
- `segmentation` + `sentiment` → segments get sentiment scores
- `transcription` + `segmentation` → segments include transcript text
- `transcription` + `segmentation` + `sentiment` → full pipeline

**Response `200`:**
```jsonc
{
  "job_id": "a3f1c2d4-...",     // present because ?save=true
  "duration_seconds": 142.3,
  "transcription": {
    "language": "en",
    "text": "Full transcript here...",
    "words": [ ... ]
  },
  "segments": [
    {
      "index": 0,
      "speaker": "SPEAKER_00",
      "start": 0.0,
      "end": 5.4,
      "text": "Hello, how are you today?",
      "sentiment": { "label": "positive", "score": 0.91 }
    }
  ],
  "sentiment_summary": { "label": "positive", "score": 0.87 },
  "processing_time_seconds": 14.6
}
```

---

#### Error responses (all `/infer/*` endpoints)

| Status | When |
|--------|------|
| `400` | Unsupported file format, missing required field, invalid `task_types` combination |
| `413` | File exceeds `REALTIME_MAX_FILE_MB` limit |
| `422` | Request body validation error |
| `503` | Model not yet loaded (worker still warming up) |
| `500` | Inference error with `{ "detail": "...", "traceback": "..." }` (dev mode only) |

---

#### Router file: `app/routers/infer.py`

All four endpoints live in this single router, mounted at `/api/v1/infer`. Each handler:
1. Resolves the audio source (multipart file → temp file, or MinIO reference → download to temp file)
2. Normalises audio via ffmpeg (16kHz mono WAV) into a temp path
3. Calls the relevant service functions directly (same functions used by Celery workers)
4. If `?save=true`, writes result to DB and returns `job_id`
5. Cleans up temp files in a `finally` block

---

### Queue Management

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/queue/stats` | Active, reserved, scheduled, failed counts |
| `POST` | `/queue/purge` | Purge all pending tasks (admin) |
| `GET` | `/minio/buckets` | List monitored MinIO buckets |
| `POST` | `/minio/poll` | Manually trigger a MinIO poll |

### Health

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Returns service health + model load status |
| `GET` | `/health/models` | Detailed model status (loaded, VRAM usage) |

---

## 7. Feature List (Prioritised)

### P0 — Must have for launch
- [ ] Audio file ingestion from MinIO (polling with configurable interval)
- [ ] Transcription via faster-whisper (all audio formats via ffmpeg)
- [ ] Speaker diarisation via pyannote.audio
- [ ] Sentiment analysis per segment via HuggingFace model
- [ ] Celery queue with retry logic + exponential backoff (max 3 retries)
- [ ] Dead-letter handling (status = 'dead' after max retries)
- [ ] Job results persisted to PostgreSQL
- [ ] Real-time upload + WebSocket streaming on GUI
- [ ] Direct inference endpoints: `POST /infer/transcribe`, `/infer/segment`, `/infer/sentiment`, `/infer/pipeline`
- [ ] `?save=true` query param on all direct inference endpoints to optionally persist results
- [ ] Direct inference accepts both multipart file upload and MinIO object reference
- [ ] Jobs list page (status, timestamps, duration)
- [ ] Job detail page (full transcript, segments, sentiment badges)
- [ ] Flower dashboard accessible at internal URL
- [ ] Nginx serving frontend on domain with HTTPS
- [ ] Docker Compose for full-stack local + production deployment
- [ ] Health check endpoints

### P1 — Important, not blocking
- [ ] Job filtering and search on dashboard
- [ ] Export job results as JSON / SRT / plain text
- [ ] Real-time job count badges in nav (pending / processing / failed)
- [ ] Configurable MinIO bucket watchlist (via env or admin API)
- [ ] Model warm-up on worker start (pre-load all models)
- [ ] Prometheus metrics endpoint (`/metrics`)
- [ ] Grafana dashboard for system metrics
- [ ] Audio waveform visualisation with segment highlighting in GUI
- [ ] Per-job log viewer in dashboard

### P2 — Nice to have / post-launch
- [ ] Webhook callback to parent app on job completion
- [ ] Batch retry (retry all failed jobs at once)
- [ ] Configurable model selection per job (e.g., `whisper-medium` for speed)
- [ ] Speaker name editing (rename SPEAKER_00 → "Alice")
- [ ] Full-text search across stored transcriptions
- [ ] Dark mode toggle

---

## 8. Pages / Screens

### `/` — Dashboard / Jobs Overview
- Job stats cards: Total, Pending, Processing, Success, Failed
- Jobs table: filename, source (minio/realtime), status badge, created, duration, actions
- Refresh every 5 seconds (TanStack Query polling)
- Filter bar: status, source, date range

### `/jobs/[id]` — Job Detail
- Job metadata header (filename, duration, status, timing)
- Full transcript text block
- Segment timeline: speaker label, time range, text, sentiment badge (colour-coded)
- Sentiment summary chart (% positive / neutral / negative)
- Download buttons: JSON, plain text, SRT
- Retry button (if status = failed/dead)

### `/realtime` — Real-time Processor
- Drag-and-drop file upload zone (accepts mp3, wav, flac, ogg, m4a, webm)
- Task selector: checkboxes for Transcription / Segmentation / Sentiment
- "Process Now" button
- Live progress bar with step labels
- Streaming transcript panel (words appear as they're transcribed)
- Segment panel populates as segments are detected
- Sentiment badges appear per segment in real-time
- On completion: links to saved job detail page

### `/queue` — Queue Monitor
- Celery stats: active workers, active tasks, reserved, scheduled
- Embed or link to Flower dashboard
- Manual poll MinIO button
- Purge queue button (with confirmation modal)

### `/settings` (P1)
- MinIO bucket watchlist management
- Poll interval config
- Worker concurrency config

---

## 9. Authentication & Authorisation

**Not handled by this service.** The frontend is behind Nginx which is expected to be accessed only by authenticated users of the parent application. No login, session, or JWT system inside this service.

Internal API (FastAPI) is only reachable from `localhost` / Docker internal network — not exposed to the internet.

**Nginx access control:**
- Frontend served at `https://yourdomain.com`
- Optional: Nginx `allow/deny` directives to restrict by IP if needed
- Flower and FastAPI ports are NOT exposed in `docker-compose.yml` port mappings to host

---

## 10. Business Logic & Rules

1. **Job deduplication:** If a MinIO object key already has a `success` job in the DB, skip it on the next poll. Configurable override via env `REPROCESS_DUPLICATES=true`.
2. **Retry backoff:** Retry delays = `[60s, 300s, 900s]` (1 min, 5 min, 15 min). After 3 failures, status → `dead`.
3. **Task type independence:** A job can request any subset of `[transcription, segmentation, sentiment]`. Sentiment requires transcription (cannot run standalone). Segmentation can run independently.
4. **Audio format normalisation:** All audio piped through `ffmpeg` before model inference → normalised to 16kHz mono WAV. Raw upload stored as-is; normalised version is ephemeral (temp file, deleted after job).
5. **File size limit (real-time path):** Max 200 MB for direct uploads. Larger files must go through MinIO queue path.
6. **MinIO processed prefix:** After successful processing, the object is copied to `{bucket}/processed/{original_key}` and the original deleted. On failure it stays in place for manual inspection.
7. **Segment overlap handling:** If pyannote produces overlapping segments (two speakers at once), both are stored separately with a flag `is_overlap = true`.
8. **Empty transcript handling:** If faster-whisper returns empty text (silence, music-only), job is marked `success` with a note `"no_speech_detected"`, not as failed.
9. **Long audio chunking:** Audio > 30 minutes is chunked into 10-minute overlapping segments internally, processed in parallel, then stitched. User sees one unified result.
10. **WebSocket timeout:** If no client connects to the WebSocket within 60 seconds of `POST /realtime/upload`, the job continues processing and result is saved to DB normally without streaming.

---

## 11. Third-Party Integrations

**None.** All processing is on-premises. All models are downloaded once at container build time or first run and stored in a Docker volume.

| Model | Source | Licence |
|-------|--------|---------|
| faster-whisper large-v3 | HuggingFace Hub (downloaded at build) | MIT |
| pyannote/speaker-diarization-3.1 | HuggingFace Hub (requires free account token, one-time) | CC BY 4.0 |
| cardiffnlp/twitter-roberta-base-sentiment-latest | HuggingFace Hub | MIT |

> **Note on pyannote:** Requires accepting the model licence on HuggingFace and providing a `HF_TOKEN` env var. This is a one-time manual step; no ongoing external calls are made.

---

## 12. Non-Functional Requirements

| Category | Requirement |
|----------|-------------|
| **Transcription speed** | `large-v3` on GPU: ≤ 0.3× real-time (i.e., 10 min audio ≤ 3 min to transcribe) |
| **Transcription speed (CPU fallback)** | `large-v3` on CPU: ≤ 5× real-time |
| **Queue throughput** | Support ≥ 10 concurrent Celery workers |
| **Real-time latency** | First WebSocket token delivered within 2 seconds of file receipt |
| **API response time** | All REST endpoints < 200ms (excluding file upload/download) |
| **DB storage** | Transcript text + results ≈ 10–50 KB per job; plan for 100k+ jobs |
| **Security** | No services except Nginx are exposed to the public internet |
| **Security** | No audio data ever leaves the server |
| **Security** | All secrets in env vars, never in code or images |
| **Availability** | Workers auto-restart on crash (Docker `restart: unless-stopped`) |
| **Browser support** | Latest Chrome, Firefox, Safari, Edge |
| **Accessibility** | WCAG 2.1 AA for the frontend dashboard |

---

## 13. File & Folder Structure

```
audio-intelligence-platform/
│
├── docker-compose.yml
├── docker-compose.prod.yml
├── .env.example
├── nginx/
│   ├── nginx.conf
│   └── ssl/                         # certs mounted here
│
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml               # Poetry or uv
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   └── app/
│       ├── main.py                  # FastAPI app factory
│       ├── config.py                # Pydantic settings (reads .env)
│       ├── database.py              # Async SQLAlchemy engine + session
│       ├── models/                  # SQLAlchemy ORM models
│       │   ├── job.py
│       │   ├── transcription.py
│       │   ├── segment.py
│       │   └── sentiment.py
│       ├── schemas/                 # Pydantic request/response schemas
│       ├── routers/
│       │   ├── jobs.py
│       │   ├── realtime.py
│       │   ├── infer.py             # Direct inference: /infer/transcribe|segment|sentiment|pipeline
│       │   └── queue.py
│       ├── services/
│       │   ├── transcription.py     # faster-whisper wrapper
│       │   ├── segmentation.py      # pyannote wrapper
│       │   ├── sentiment.py         # HuggingFace wrapper
│       │   ├── minio_client.py      # MinIO S3 client
│       │   └── audio_utils.py       # ffmpeg normalisation
│       ├── workers/
│       │   ├── celery_app.py        # Celery app + config
│       │   ├── tasks.py             # Celery task definitions
│       │   └── beat.py              # Celery Beat schedule (MinIO poller)
│       └── websocket/
│           └── manager.py           # WebSocket connection manager
│
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── next.config.ts
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   └── src/
│       ├── app/                     # Next.js App Router
│       │   ├── layout.tsx
│       │   ├── page.tsx             # Dashboard
│       │   ├── jobs/[id]/page.tsx   # Job detail
│       │   ├── realtime/page.tsx    # Real-time processor
│       │   └── queue/page.tsx       # Queue monitor
│       ├── components/
│       │   ├── ui/                  # shadcn/ui components
│       │   ├── jobs/
│       │   ├── realtime/
│       │   └── dashboard/
│       ├── hooks/
│       │   ├── useWebSocket.ts
│       │   └── useJobs.ts
│       ├── lib/
│       │   ├── api.ts               # API client (fetch wrapper)
│       │   └── utils.ts
│       └── stores/
│           └── realtimeStore.ts     # Zustand store
│
└── models/                          # Docker volume mount — downloaded models live here
    ├── whisper/
    ├── pyannote/
    └── sentiment/
```

---

## 14. Environment Variables

```bash
# ── PostgreSQL ──────────────────────────────────────────
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=aip
POSTGRES_USER=aip_user
POSTGRES_PASSWORD=change_me_in_prod

# ── Redis ───────────────────────────────────────────────
REDIS_URL=redis://redis:6379/0

# ── MinIO ───────────────────────────────────────────────
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=change_me_in_prod
MINIO_USE_SSL=false
MINIO_WATCH_BUCKETS=audio-uploads        # comma-separated
MINIO_PROCESSED_PREFIX=processed/
MINIO_POLL_INTERVAL_SECONDS=30

# ── Models ──────────────────────────────────────────────
WHISPER_MODEL_SIZE=large-v3              # tiny|base|small|medium|large-v3
WHISPER_DEVICE=cuda                      # cuda|cpu
WHISPER_COMPUTE_TYPE=float16             # float16|int8 (int8 for CPU)
PYANNOTE_MODEL=pyannote/speaker-diarization-3.1
SENTIMENT_MODEL=cardiffnlp/twitter-roberta-base-sentiment-latest
HF_TOKEN=hf_xxxxxxxxxxxxxxxxxxxx         # HuggingFace token for pyannote licence
MODELS_DIR=/models                       # Docker volume path

# ── Celery ──────────────────────────────────────────────
CELERY_CONCURRENCY=4                     # workers per container
CELERY_MAX_RETRIES=3
CELERY_RETRY_BACKOFF=60                  # seconds, multiplied exponentially

# ── FastAPI ─────────────────────────────────────────────
API_HOST=0.0.0.0
API_PORT=8000
REALTIME_MAX_FILE_MB=200
WEBSOCKET_CONNECT_TIMEOUT_SECONDS=60
LOG_LEVEL=INFO

# ── Frontend ────────────────────────────────────────────
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1    # internal (SSR calls)
NEXT_PUBLIC_WS_URL=ws://localhost:8000/api/v1       # internal

# ── Nginx ───────────────────────────────────────────────
DOMAIN=yourdomain.com
SSL_CERT_PATH=/etc/nginx/ssl/cert.pem
SSL_KEY_PATH=/etc/nginx/ssl/key.pem

# ── Feature flags ───────────────────────────────────────
REPROCESS_DUPLICATES=false
ENABLE_METRICS=true
```

---

## 15. Deployment & DevOps

### Local Development
```bash
# 1. Copy env
cp .env.example .env
# edit .env: set HF_TOKEN, keep rest as defaults

# 2. Start all services
docker compose up --build

# 3. Run DB migrations
docker compose exec backend alembic upgrade head

# 4. Download models (first run only — takes ~5 min)
docker compose exec worker python -m app.services.download_models

# Services running:
# Frontend:  http://localhost:3000
# FastAPI:   http://localhost:8000/docs
# Flower:    http://localhost:5555
# MinIO UI:  http://localhost:9001
```

### Production
```bash
# 1. On server: copy .env, set real secrets and domain
# 2. Place SSL certs in ./nginx/ssl/

docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Exposed to internet: port 443 (Nginx → Next.js frontend)
# All other ports: bound to 127.0.0.1 only
```

### Docker Compose Services
| Service | Image | Replicas |
|---------|-------|----------|
| `postgres` | postgres:16-alpine | 1 |
| `redis` | redis:7-alpine | 1 |
| `minio` | minio/minio | 1 |
| `backend` | ./backend (FastAPI) | 1 |
| `worker` | ./backend (Celery worker) | 1–N (scale with `--scale worker=N`) |
| `beat` | ./backend (Celery Beat) | 1 |
| `flower` | mher/flower | 1 |
| `frontend` | ./frontend (Next.js) | 1 |
| `nginx` | nginx:alpine | 1 |

### CI/CD (P1)
- GitHub Actions on `main` push:
  1. Lint (ruff, eslint)
  2. Type check (mypy, tsc)
  3. Unit tests (pytest, vitest)
  4. Build Docker images
  5. Push to registry
  6. SSH deploy: `docker compose pull && docker compose up -d`

### Monitoring
- **Flower:** `http://internal:5555` — Celery task monitor
- **FastAPI docs:** `http://internal:8000/docs` — live API explorer
- **`/health` endpoint:** Used by Docker health checks + uptime monitor
- **P1:** Prometheus scrapes `/metrics`; Grafana shows job throughput, queue depth, model latency

---

## 16. Open Questions

| # | Question | Impact |
|---|----------|--------|
| 1 | Does the GPU have enough VRAM to run all three models simultaneously? (`large-v3` needs ~10 GB, pyannote ~1 GB, sentiment ~500 MB) → If not, models need to be loaded/unloaded per task or run on separate workers. | High |
| 2 | Should MinIO buckets be pre-created by this service or assumed to exist already? | Medium |
| 3 | How should the parent app be notified when a queued job completes? (webhook callback, polling the jobs API, Redis pub/sub?) | Medium |
| 4 | Is there a need to retain audio files in MinIO after processing, or always move to `processed/`? | Low |
| 5 | What is the expected average audio file length? This determines chunking strategy and expected queue SLA. | Medium |
| 6 | Should Flower be password-protected even on internal network? | Low |
| 7 | Is GPU available on the deployment server, or is CPU-only mode required for launch? | High |

---

## Architect's Notes & Suggestions

> These are recommendations based on the requirements above.

1. **Use `faster-whisper` not `openai-whisper`** — same models, 4–10× faster, lower memory footprint. Non-negotiable for production throughput.

2. **Load models once, reuse** — Load all three models into memory when the worker starts. Do not reload per task. This cuts per-job overhead from ~30 seconds to ~0.

3. **Two worker types** — Consider two Celery queues: `gpu_queue` (transcription + segmentation, GPU-bound) and `cpu_queue` (sentiment, CPU-bound). This lets you scale them independently and avoids GPU contention.

4. **MinIO polling is safer than webhooks for first version** — Webhooks require MinIO to reach your FastAPI service. Polling from the worker side is simpler, has no network topology dependencies, and handles MinIO restarts gracefully.

5. **WebSocket streaming is the key UX differentiator** — The real-time path with streaming tokens is what makes this feel like a premium product vs. "upload and wait." Prioritise this experience.

6. **Plan for audio chunking from day one** — Don't hardcode single-pass processing. Users will upload hour-long recordings. Build the chunking logic as a first-class concern in `audio_utils.py`.

7. **pyannote requires a HuggingFace token** — This is a one-time licence acceptance. Document this clearly in the README. Consider pre-downloading the model into the Docker image in CI so production workers start instantly.

8. **Use `int8` compute type on CPU** — If GPU is not available, set `WHISPER_COMPUTE_TYPE=int8`. This cuts memory by 4× with minimal accuracy loss on `large-v3`.

9. **Don't expose MinIO to the frontend directly** — All file operations go through FastAPI. The frontend never gets MinIO credentials.

10. **Nginx should handle SSL termination** — All HTTPS → Nginx → HTTP internally. Do not configure SSL in FastAPI or Next.js.

---

*Spec sheet complete.*

Say **"write prompts"** when you want 15+ ordered build prompts from this spec, or **"build"** to start scaffolding the project.
