# Prompt 24 — Model Download & Warm-up Script

## Goal
Build a standalone script that downloads all three ML models to the local `models/` volume on first run, and a warm-up module that pre-loads them into memory when a worker or API server starts.

## Files to create

---

### `backend/scripts/download_models.py`

Standalone script — run once to pre-download all models before starting workers.

```bash
# Usage:
python -m app.scripts.download_models
# or inside Docker:
docker compose exec worker python -m app.scripts.download_models
```

```python
#!/usr/bin/env python3
"""
Downloads all ML models to the MODELS_DIR volume.
Run this once before starting workers to avoid download delays on first job.
"""

import sys
import time
from pathlib import Path
import structlog

log = structlog.get_logger()


def download_whisper():
    log.info("downloading faster-whisper model", size=settings.whisper_model_size)
    t = time.perf_counter()
    from faster_whisper import WhisperModel
    model = WhisperModel(
        settings.whisper_model_size,
        device="cpu",               # always download on CPU (device irrelevant for download)
        compute_type="int8",
        download_root=str(Path(settings.models_dir) / "whisper"),
    )
    del model  # free memory after download
    elapsed = time.perf_counter() - t
    log.info("whisper download complete", elapsed_seconds=round(elapsed, 1))


def download_pyannote():
    if not settings.hf_token:
        log.warning(
            "HF_TOKEN not set — pyannote model requires HuggingFace token for first download. "
            "Set HF_TOKEN env var and re-run. Skipping."
        )
        return
    log.info("downloading pyannote model", model=settings.pyannote_model)
    t = time.perf_counter()
    from pyannote.audio import Pipeline
    pipeline = Pipeline.from_pretrained(
        settings.pyannote_model,
        use_auth_token=settings.hf_token,
        cache_dir=str(Path(settings.models_dir) / "pyannote"),
    )
    del pipeline
    elapsed = time.perf_counter() - t
    log.info("pyannote download complete", elapsed_seconds=round(elapsed, 1))


def download_sentiment():
    log.info("downloading sentiment model", model=settings.sentiment_model)
    t = time.perf_counter()
    from transformers import AutoTokenizer, AutoModelForSequenceClassification
    cache_dir = str(Path(settings.models_dir) / "sentiment")
    AutoTokenizer.from_pretrained(settings.sentiment_model, cache_dir=cache_dir)
    AutoModelForSequenceClassification.from_pretrained(settings.sentiment_model, cache_dir=cache_dir)
    elapsed = time.perf_counter() - t
    log.info("sentiment model download complete", elapsed_seconds=round(elapsed, 1))


def main():
    log.info("starting model downloads", models_dir=settings.models_dir)
    Path(settings.models_dir).mkdir(parents=True, exist_ok=True)

    errors = []

    for name, fn in [("whisper", download_whisper), ("pyannote", download_pyannote), ("sentiment", download_sentiment)]:
        try:
            fn()
        except Exception as exc:
            log.error(f"{name} download failed", error=str(exc))
            errors.append(name)

    if errors:
        log.error("some models failed to download", failed=errors)
        sys.exit(1)
    else:
        log.info("all models downloaded successfully")
        sys.exit(0)


if __name__ == "__main__":
    main()
```

---

### `backend/scripts/check_models.py`

Verify all models are present without loading them into memory (just check the cache directories).

```python
"""
Checks if model files exist in MODELS_DIR.
Exits 0 if all present, exits 1 with list of missing models.
Used by Docker health checks and CI.
"""

def check_whisper() -> bool:
    # Check for model files in MODELS_DIR/whisper/
    # faster-whisper stores model as: models--Systran--faster-whisper-{size}/ in HF cache format
    # or directly as model.bin, config.json etc. depending on version
    whisper_dir = Path(settings.models_dir) / "whisper"
    return whisper_dir.exists() and any(whisper_dir.rglob("model.bin"))

def check_pyannote() -> bool:
    pyannote_dir = Path(settings.models_dir) / "pyannote"
    return pyannote_dir.exists() and any(pyannote_dir.rglob("config.yaml"))

def check_sentiment() -> bool:
    sentiment_dir = Path(settings.models_dir) / "sentiment"
    return sentiment_dir.exists() and any(sentiment_dir.rglob("config.json"))

def main():
    results = {
        "whisper":   check_whisper(),
        "pyannote":  check_pyannote(),
        "sentiment": check_sentiment(),
    }
    for model, ok in results.items():
        status = "✓" if ok else "✗ MISSING"
        print(f"  {model:12} {status}")

    if not all(results.values()):
        missing = [k for k, v in results.items() if not v]
        print(f"\nMissing: {missing}")
        print("Run: python -m app.scripts.download_models")
        sys.exit(1)
    sys.exit(0)
```

---

### `app/workers/warmup.py`

Module-level warm-up called from Celery worker `on_after_finalize` signal and from FastAPI lifespan.

```python
import threading
import structlog

log = structlog.get_logger()

def warmup_all_models(background: bool = False) -> None:
    """
    Pre-load all three models into memory.

    background=True: runs in a daemon thread (non-blocking startup).
    background=False: blocks until all models are loaded (used in tests).
    """
    def _load():
        from app.services.transcription import preload_model as preload_whisper
        from app.services.segmentation import preload_pipeline as preload_pyannote
        from app.services.sentiment import preload_model as preload_sentiment

        log.info("warming up models")
        try:
            preload_whisper()
            log.info("whisper ready")
        except Exception as exc:
            log.error("whisper warmup failed", error=str(exc))

        try:
            preload_pyannote()
            log.info("pyannote ready")
        except Exception as exc:
            log.error("pyannote warmup failed", error=str(exc))

        try:
            preload_sentiment()
            log.info("sentiment model ready")
        except Exception as exc:
            log.error("sentiment warmup failed", error=str(exc))

        log.info("all models warmed up")

    if background:
        t = threading.Thread(target=_load, daemon=True, name="model-warmup")
        t.start()
    else:
        _load()
```

Usage in `app/main.py` lifespan:
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    warmup_all_models(background=True)  # non-blocking; models ready within ~30s
    yield
    # shutdown: nothing to do (models unload with the process)
```

---

### Docker Compose init container (add to `docker-compose.yml`)

Add a one-shot service that downloads models before workers start:

```yaml
  model-downloader:
    build:
      context: ./backend
      dockerfile: Dockerfile
    command: python -m app.scripts.download_models
    environment:
      - MODELS_DIR=/models
      - WHISPER_MODEL_SIZE=${WHISPER_MODEL_SIZE:-large-v3}
      - HF_TOKEN=${HF_TOKEN}
      - SENTIMENT_MODEL=${SENTIMENT_MODEL}
      - PYANNOTE_MODEL=${PYANNOTE_MODEL}
    volumes:
      - models_data:/models
    networks: [aip_network]
    restart: "no"    # run once, don't restart
    # worker depends_on: model-downloader (condition: service_completed_successfully)
```

Update `worker` and `backend` services to depend on `model-downloader`:
```yaml
  worker:
    depends_on:
      model-downloader: { condition: service_completed_successfully }
      postgres: { condition: service_healthy }
      redis:    { condition: service_healthy }
```

---

## Constraints
- `download_models.py` must exit 0 on success, 1 on any failure — used by CI and Docker depends_on
- pyannote download failure must be logged but not fail the entire script if `HF_TOKEN` is not set — just skip and warn
- `warmup_all_models(background=True)` must not block the FastAPI startup — use daemon thread
- Model download script is idempotent — running it twice does nothing (HuggingFace caches check local files first)
- Add a `--force` flag to `download_models.py` that clears the model cache and re-downloads
