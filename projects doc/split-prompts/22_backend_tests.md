# Prompt 22 — Backend Tests (pytest)

## Goal
Write a comprehensive pytest test suite for the FastAPI backend. Cover all routers, service functions, Celery tasks, and the MinIO poller. Use a real test database (PostgreSQL) — no mocking the database.

## Test structure

```
backend/
└── tests/
    ├── conftest.py
    ├── test_health.py
    ├── test_jobs_router.py
    ├── test_infer_router.py
    ├── test_realtime_router.py
    ├── test_queue_router.py
    ├── test_transcription_service.py
    ├── test_segmentation_service.py
    ├── test_sentiment_service.py
    ├── test_audio_utils.py
    ├── test_minio_client.py
    └── fixtures/
        ├── short_audio.wav        ← 5-second test WAV (silence or tone)
        └── short_audio.mp3        ← same, MP3 format
```

---

### `tests/conftest.py`

```python
import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.main import app
from app.database import get_db
from app.models import Base

# Test DB: separate database "aip_test"
TEST_DB_URL = "postgresql+asyncpg://aip_user:test@localhost:5432/aip_test"

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest.fixture
async def db_session(test_engine):
    async_session = async_sessionmaker(test_engine, expire_on_commit=False)
    async with async_session() as session:
        yield session
        await session.rollback()   # rollback after each test for isolation

@pytest.fixture
async def client(db_session):
    # Override get_db dependency
    async def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()

@pytest.fixture
def audio_wav():
    return Path(__file__).parent / "fixtures" / "short_audio.wav"

@pytest.fixture
def audio_mp3():
    return Path(__file__).parent / "fixtures" / "short_audio.mp3"
```

---

### `tests/test_health.py`

```python
async def test_health_returns_ok(client):
    r = await client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in ("ok", "degraded")  # either is valid in test env
    assert "postgres" in body
    assert "uptime_seconds" in body

async def test_models_health_returns_loaded_state(client):
    r = await client.get("/api/v1/health/models")
    assert r.status_code == 200
    body = r.json()
    assert "whisper" in body
    assert "loaded" in body["whisper"]
```

---

### `tests/test_jobs_router.py`

```python
# Fixtures: create_job() — helper that inserts a Job row directly via db_session

async def test_list_jobs_empty(client):
    r = await client.get("/api/v1/jobs")
    assert r.status_code == 200
    assert r.json()["items"] == []
    assert r.json()["total"] == 0

async def test_list_jobs_with_status_filter(client, db_session):
    # Insert 3 pending + 2 success jobs
    # GET /jobs?status=success → expect 2

async def test_get_job_not_found(client):
    r = await client.get(f"/api/v1/jobs/{uuid4()}")
    assert r.status_code == 404

async def test_get_job_returns_detail(client, db_session):
    # Insert job with transcription and segments
    # GET /jobs/{id} → check transcription and segments in response

async def test_delete_job(client, db_session):
    # Insert job with status='success'
    # DELETE /jobs/{id} → 204
    # GET /jobs/{id} → 404

async def test_delete_processing_job_returns_409(client, db_session):
    # Insert job with status='processing'
    # DELETE → 409

async def test_retry_failed_job(client, db_session, mocker):
    # Insert failed job
    # Mock celery run_pipeline.delay to return a mock task
    # POST /jobs/{id}/retry → 200, status='pending'

async def test_retry_non_failed_job_returns_409(client, db_session):
    # Insert success job
    # POST /jobs/{id}/retry → 409

async def test_export_job_json(client, db_session):
    # Insert success job with transcription
    # GET /jobs/{id}/export?format=json → 200, Content-Disposition with filename

async def test_export_job_srt(client, db_session):
    # Insert job with segments
    # GET /jobs/{id}/export?format=srt → 200, content starts with "1\n"

async def test_list_jobs_pagination(client, db_session):
    # Insert 25 jobs
    # GET /jobs?page=2&limit=10 → 10 items, page=2, total=25
```

---

### `tests/test_infer_router.py`

```python
# These tests require models to be loaded OR mock the service calls

async def test_transcribe_returns_503_if_model_not_loaded(client, mocker):
    mocker.patch("app.routers.infer.is_model_loaded", return_value=False)
    with open("tests/fixtures/short_audio.wav", "rb") as f:
        r = await client.post("/api/v1/infer/transcribe", files={"file": f})
    assert r.status_code == 503

async def test_transcribe_rejects_unsupported_format(client):
    fake_file = ("test.exe", b"fake", "application/octet-stream")
    r = await client.post("/api/v1/infer/transcribe", files={"file": fake_file})
    assert r.status_code == 400

async def test_transcribe_rejects_oversized_file(client, mocker):
    mocker.patch("app.routers.infer.settings.realtime_max_file_mb", 0)
    with open("tests/fixtures/short_audio.wav", "rb") as f:
        r = await client.post("/api/v1/infer/transcribe", files={"file": f})
    assert r.status_code == 413

async def test_pipeline_invalid_task_types(client):
    fake_file = ("test.wav", b"fake", "audio/wav")
    r = await client.post(
        "/api/v1/infer/pipeline?task_types=invalid_task",
        files={"file": fake_file}
    )
    assert r.status_code == 400

async def test_sentiment_text_only(client, mocker):
    # Mock analyse_chunks to return fake results
    mocker.patch("app.routers.infer.analyse_chunks", return_value=[...])
    mocker.patch("app.routers.infer.is_model_loaded", return_value=True)
    r = await client.post(
        "/api/v1/infer/sentiment",
        data={"text": "I love this product!", "chunk_by": "sentence"}
    )
    assert r.status_code == 200
    assert r.json()["overall"]["label"] in ("positive", "negative", "neutral")
```

---

### `tests/test_audio_utils.py`

```python
# These test actual ffmpeg calls — require ffmpeg installed

async def test_normalise_audio_wav(audio_wav):
    result = normalise_audio(audio_wav)
    assert result.exists()
    assert result.suffix == ".wav"
    result.unlink()

async def test_normalise_audio_mp3(audio_mp3):
    result = normalise_audio(audio_mp3)
    assert result.exists()
    result.unlink()

async def test_get_audio_duration(audio_wav):
    norm = normalise_audio(audio_wav)
    duration = get_audio_duration(norm)
    assert 4.0 <= duration <= 6.0   # 5-second test file ±1s tolerance
    norm.unlink()

async def test_normalise_rejects_unsupported_format(tmp_path):
    fake = tmp_path / "test.exe"
    fake.write_bytes(b"fake")
    with pytest.raises(UnsupportedAudioFormatError):
        normalise_audio(fake)

async def test_chunk_audio_short_file_no_split(audio_wav):
    norm = normalise_audio(audio_wav)
    chunks = chunk_audio(norm, chunk_duration_seconds=600)
    assert len(chunks) == 1
    assert chunks[0].path == norm
    norm.unlink()
```

---

### `tests/test_sentiment_service.py`

```python
# Unit tests for sentiment functions (mocked model)

def test_analyse_empty_text():
    result = analyse_text("")
    assert result.label == "neutral"
    assert result.score == 1.0

def test_analyse_chunks_sentence(mocker):
    mocker.patch("app.services.sentiment.get_model", return_value=(mock_tokenizer, mock_model))
    chunks = analyse_chunks("I love it. I hate it.", chunk_by="sentence")
    assert len(chunks) == 2

def test_compute_overall_sentiment():
    scores = [
        SentimentScore(label="positive", score=0.9, all_scores={}),
        SentimentScore(label="positive", score=0.8, all_scores={}),
        SentimentScore(label="negative", score=0.7, all_scores={}),
    ]
    overall = compute_overall_sentiment(scores)
    assert overall.label == "positive"
```

---

## pytest configuration (`pyproject.toml` additions)

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
markers = [
    "integration: marks tests that require external services (postgres, redis, minio)",
    "unit: marks pure unit tests with no external dependencies",
]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.mypy]
python_version = "3.12"
strict = true
ignore_missing_imports = true
```

---

## Constraints
- Test database must be `aip_test` — never run tests against `aip` (production) database
- Each test function rolls back its DB changes (fixture-level rollback in `conftest.py`)
- Tests that call real ML models are marked `@pytest.mark.integration` and skipped in CI by default
- `mocker` fixture from `pytest-mock` — add `pytest-mock` to dev dependencies
- Fixture `short_audio.wav`: generate programmatically in conftest if not present using `scipy.io.wavfile` or a simple sine wave — do not require a pre-existing binary file in git
