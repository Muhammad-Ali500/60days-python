# Prompt 26 — Alembic Migration Workflow & Database Seed

## Goal
Establish the full Alembic workflow, write the initial migration (if not done in Prompt 02), add a second migration for the `minio_poll_state` insert_or_update logic, and write a seed script for local development data.

## Files to create / edit

---

### `alembic/env.py` (complete implementation)

```python
import asyncio
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context

# Import all models so autogenerate can detect them
from app.models import Base  # noqa: F401 — side-effect import registers all models
from app.config import settings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url() -> str:
    return settings.sync_database_url   # psycopg2 sync URL for Alembic


def run_migrations_offline() -> None:
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        {"sqlalchemy.url": settings.database_url},   # asyncpg URL
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

---

### `alembic/versions/0001_initial_schema.py` (verify completeness)

Ensure it includes:

```python
"""Initial schema

Revision ID: 0001
Revises:
Create Date: 2026-04-30
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable pgcrypto for gen_random_uuid()
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    # jobs
    op.create_table(
        "jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("source", sa.String(10), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("minio_bucket", sa.Text, nullable=True),
        sa.Column("minio_object_key", sa.Text, nullable=True),
        sa.Column("original_filename", sa.Text, nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger, nullable=True),
        sa.Column("audio_duration_seconds", sa.Float, nullable=True),
        sa.Column("task_types", postgresql.ARRAY(sa.Text), nullable=False),
        sa.Column("celery_task_id", sa.Text, nullable=True),
        sa.Column("retry_count", sa.SmallInteger, nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.CheckConstraint("source IN ('minio','realtime','direct')", name="jobs_source_check"),
        sa.CheckConstraint("status IN ('pending','processing','success','failed','dead')", name="jobs_status_check"),
    )
    op.create_index("idx_jobs_status", "jobs", ["status"])
    op.create_index("idx_jobs_created_at", "jobs", [sa.text("created_at DESC")])

    # transcriptions, segments, sentiment_results, minio_poll_state
    # ... (all as per Prompt 02 spec)


def downgrade() -> None:
    op.drop_table("sentiment_results")
    op.drop_table("segments")
    op.drop_table("transcriptions")
    op.drop_table("minio_poll_state")
    op.drop_table("jobs")
    op.execute("DROP EXTENSION IF EXISTS pgcrypto")
```

---

### `alembic/versions/0002_add_no_speech_flag.py`

Second migration — add `no_speech_detected` boolean to `transcriptions` table:

```python
"""Add no_speech_detected to transcriptions

Revision ID: 0002
Revises: 0001
"""

def upgrade():
    op.add_column(
        "transcriptions",
        sa.Column("no_speech_detected", sa.Boolean, nullable=False, server_default="false")
    )

def downgrade():
    op.drop_column("transcriptions", "no_speech_detected")
```

---

### `backend/scripts/seed_dev_data.py`

Creates realistic local development data for testing the UI without running real ML.

```python
"""
Seed script for local development.
Creates sample jobs with fake transcription, segment, and sentiment data.
Usage: python -m app.scripts.seed_dev_data
"""

import asyncio
import uuid
from datetime import datetime, timezone, timedelta
import random
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.config import settings
from app.models import Job, Transcription, Segment, SentimentResult

SAMPLE_TRANSCRIPTS = [
    "Hello everyone and welcome to today's meeting. We'll be discussing the quarterly results.",
    "I think the product launch went really well. The customer feedback has been overwhelmingly positive.",
    "Unfortunately we ran into some issues with the deployment last week. The team has been working hard to resolve them.",
    "Let's talk about our plans for next quarter. We have some exciting new features lined up.",
]

SPEAKERS = ["SPEAKER_00", "SPEAKER_01", "SPEAKER_02"]
SENTIMENTS = ["positive", "negative", "neutral"]


async def create_sample_job(
    session: AsyncSession,
    source: str,
    status: str,
    task_types: list[str],
    days_ago: int = 0,
) -> Job:
    created = datetime.now(timezone.utc) - timedelta(days=days_ago, hours=random.randint(0, 23))
    job = Job(
        id=uuid.uuid4(),
        source=source,
        status=status,
        original_filename=f"recording_{random.randint(1000, 9999)}.mp3",
        file_size_bytes=random.randint(500_000, 50_000_000),
        audio_duration_seconds=random.uniform(30, 900),
        task_types=task_types,
        retry_count=0 if status != "failed" else random.randint(1, 3),
        error_message="Connection timeout" if status in ("failed", "dead") else None,
        created_at=created,
        started_at=created + timedelta(seconds=2) if status != "pending" else None,
        completed_at=created + timedelta(seconds=random.uniform(5, 60)) if status == "success" else None,
    )
    session.add(job)
    await session.flush()

    if status == "success" and "transcription" in task_types:
        text = random.choice(SAMPLE_TRANSCRIPTS)
        words = _generate_fake_words(text, job.audio_duration_seconds)
        transcript = Transcription(
            job_id=job.id,
            language="en",
            full_text=text,
            word_count=len(text.split()),
            model_used="faster-whisper-large-v3",
            words_json=words,
        )
        session.add(transcript)
        await session.flush()

        if "segmentation" in task_types:
            segments = _generate_fake_segments(job.id, transcript.id, text, job.audio_duration_seconds)
            for seg in segments:
                session.add(seg)
            await session.flush()

            if "sentiment" in task_types:
                for seg in segments:
                    sentiment = SentimentResult(
                        job_id=job.id,
                        segment_id=seg.id,
                        label=random.choice(SENTIMENTS),
                        score=random.uniform(0.65, 0.99),
                        model_used="cardiffnlp/twitter-roberta-base-sentiment-latest",
                    )
                    session.add(sentiment)

    return job


def _generate_fake_words(text: str, duration: float) -> list[dict]:
    words = text.split()
    interval = duration / len(words) if words else 1.0
    result = []
    for i, word in enumerate(words):
        start = i * interval
        result.append({"word": word, "start": round(start, 3), "end": round(start + interval * 0.8, 3), "probability": round(random.uniform(0.85, 0.99), 3)})
    return result


def _generate_fake_segments(job_id, transcript_id, text: str, duration: float) -> list[Segment]:
    sentences = text.split(". ")
    segments = []
    t = 0.0
    for i, sentence in enumerate(sentences):
        end = t + duration / len(sentences)
        segments.append(Segment(
            job_id=job_id,
            transcription_id=transcript_id,
            speaker_label=random.choice(SPEAKERS),
            start_time=round(t, 3),
            end_time=round(end, 3),
            text=sentence,
            segment_index=i,
            is_overlap=False,
        ))
        t = end
    return segments


async def main():
    engine = create_async_engine(settings.database_url)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as session:
        # Create variety of jobs
        configs = [
            ("minio",    "success", ["transcription", "segmentation", "sentiment"], 0),
            ("minio",    "success", ["transcription", "segmentation", "sentiment"], 1),
            ("realtime", "success", ["transcription"], 0),
            ("realtime", "processing", ["transcription", "segmentation"], 0),
            ("minio",    "pending",  ["transcription", "segmentation", "sentiment"], 0),
            ("minio",    "failed",   ["transcription"], 1),
            ("direct",   "success",  ["sentiment"], 0),
            ("minio",    "dead",     ["transcription", "segmentation"], 3),
        ] * 3  # multiply for more variety

        for source, status, tasks, days in configs:
            await create_sample_job(session, source, status, tasks, days)

        await session.commit()

    print(f"Seeded {len(configs)} sample jobs.")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
```

---

### `Makefile` (convenience commands)

```makefile
.PHONY: migrate seed reset-db

migrate:
	docker compose exec backend alembic upgrade head

migrate-down:
	docker compose exec backend alembic downgrade -1

seed:
	docker compose exec backend python -m app.scripts.seed_dev_data

reset-db:
	docker compose exec backend alembic downgrade base
	docker compose exec backend alembic upgrade head
	docker compose exec backend python -m app.scripts.seed_dev_data

download-models:
	docker compose exec worker python -m app.scripts.download_models

check-models:
	docker compose exec worker python -m app.scripts.check_models
```

---

## Constraints
- Alembic migrations must be reversible — every `upgrade()` has a working `downgrade()`
- `env.py` uses the async engine for online mode — this is correct for `asyncpg`
- Seed script must be idempotent (running twice creates duplicate data but doesn't crash — acceptable for dev)
- Never run seed script in production — add a guard: `if settings.log_level == "DEBUG" or "dev" in settings.postgres_db`
- `compare_type=True` in `env.py` ensures Alembic detects column type changes in autogenerate
