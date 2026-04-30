# Prompt 02 — PostgreSQL Schema & Alembic Migrations

## Goal
Write all SQLAlchemy ORM models and generate the initial Alembic migration that creates the complete database schema defined in Section 5 of the spec sheet.

## Files to create / edit

### `app/models/__init__.py`
Export all models so Alembic can discover them:
```python
from app.models.job import Job
from app.models.transcription import Transcription
from app.models.segment import Segment
from app.models.sentiment import SentimentResult
from app.models.minio_state import MinioPollState
```

### `app/models/base.py`
Define the declarative base:
```python
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass
```

### `app/models/job.py`
Map the `jobs` table exactly as defined in the spec sheet Section 5.

Fields:
- `id`: UUID primary key, default `gen_random_uuid()` (server default) + Python default `uuid4`
- `source`: String(10), NOT NULL, CHECK IN ('minio', 'realtime', 'direct') ← add 'direct' for Path C calls
- `status`: String(20), NOT NULL, default 'pending', CHECK IN ('pending','processing','success','failed','dead')
- `minio_bucket`: Text, nullable
- `minio_object_key`: Text, nullable
- `original_filename`: Text, NOT NULL
- `file_size_bytes`: BigInteger, nullable
- `audio_duration_seconds`: Float, nullable
- `task_types`: ARRAY(Text), NOT NULL — use `postgresql.ARRAY(String)`
- `celery_task_id`: Text, nullable
- `retry_count`: SmallInteger, default 0
- `error_message`: Text, nullable
- `created_at`: TIMESTAMPTZ, server_default `now()`, not nullable
- `started_at`: TIMESTAMPTZ, nullable
- `completed_at`: TIMESTAMPTZ, nullable

Relationships:
- `transcription`: one-to-one back to `Transcription`
- `segments`: one-to-many back to `Segment`
- `sentiment_results`: one-to-many back to `SentimentResult`

Indexes:
- `idx_jobs_status` on `status`
- `idx_jobs_created_at` on `created_at DESC`

### `app/models/transcription.py`
Fields:
- `id`: UUID PK
- `job_id`: UUID FK → `jobs.id` ON DELETE CASCADE, NOT NULL, unique (one per job)
- `language`: String(10), nullable
- `full_text`: Text, NOT NULL
- `word_count`: Integer, nullable
- `model_used`: Text, NOT NULL
- `words_json`: JSONB, nullable — stores the word-level timestamp array `[{word, start, end, probability}]`
- `created_at`: TIMESTAMPTZ

### `app/models/segment.py`
Fields:
- `id`: UUID PK
- `job_id`: UUID FK → `jobs.id` ON DELETE CASCADE, NOT NULL
- `transcription_id`: UUID FK → `transcriptions.id` ON DELETE CASCADE, nullable
- `speaker_label`: Text, nullable
- `start_time`: Float, NOT NULL
- `end_time`: Float, NOT NULL
- `text`: Text, nullable
- `segment_index`: Integer, NOT NULL
- `is_overlap`: Boolean, default False
- `created_at`: TIMESTAMPTZ

Index: `idx_segments_job_id` on `job_id`

### `app/models/sentiment.py`
Fields:
- `id`: UUID PK
- `job_id`: UUID FK → `jobs.id` ON DELETE CASCADE, NOT NULL
- `segment_id`: UUID FK → `segments.id` ON DELETE CASCADE, nullable (null = document-level sentiment)
- `chunk_index`: Integer, nullable — position in the chunk list for direct text sentiment
- `chunk_text`: Text, nullable — the text chunk that was analysed
- `label`: String(20), NOT NULL — 'positive' | 'negative' | 'neutral'
- `score`: Float, NOT NULL — confidence 0.0–1.0
- `model_used`: Text, NOT NULL
- `created_at`: TIMESTAMPTZ

Index: `idx_sentiment_job_id` on `job_id`

### `app/models/minio_state.py`
Fields:
- `id`: Integer PK autoincrement
- `bucket`: Text, NOT NULL, unique
- `last_polled_at`: TIMESTAMPTZ, nullable
- `last_object_key`: Text, nullable

### `alembic/versions/0001_initial_schema.py`
Generate (do not use `alembic revision --autogenerate` — write it by hand) a migration that:
1. Enables `pgcrypto` extension (`CREATE EXTENSION IF NOT EXISTS pgcrypto`)
2. Creates all 5 tables in dependency order: `jobs` → `transcriptions` → `segments` → `sentiment_results` → `minio_poll_state`
3. Creates all indexes listed in the spec
4. The `downgrade()` function drops all tables and indexes in reverse order

### `app/database.py`
```python
# Async SQLAlchemy engine + session factory
# - Read DATABASE_URL from config
# - engine: create_async_engine with pool_size=10, max_overflow=20
# - AsyncSessionLocal: async_sessionmaker
# - get_db(): async generator yielding a session, used as FastAPI dependency
```

## Constraints
- Use `sqlalchemy.dialects.postgresql` for ARRAY, JSONB, UUID types — do not use generic types for these
- All UUID columns use `postgresql.UUID(as_uuid=True)`
- All timestamp columns use `TIMESTAMP(timezone=True)`
- No `__tablename__` typos — match exactly the names in the spec SQL
- The migration must be reversible (downgrade works)
