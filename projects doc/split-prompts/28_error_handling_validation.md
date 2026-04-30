# Prompt 28 — Error Handling, Validation & Edge Cases

## Goal
Implement comprehensive error handling across the entire stack — FastAPI exception handlers, custom exception hierarchy, frontend error boundaries, and handling for every edge case defined in Section 10 of the spec sheet.

## Files to create / edit

---

### `app/exceptions.py` (complete file)

```python
"""
Central exception hierarchy for AIP.
All custom exceptions inherit from AIPBaseError.
"""

class AIPBaseError(Exception):
    """Base class for all AIP domain errors."""
    pass


# ── Audio Processing ──────────────────────────────────────────

class AudioProcessingError(AIPBaseError):
    def __init__(self, message: str, path: str | None = None):
        self.path = path
        super().__init__(message)

class UnsupportedAudioFormatError(AudioProcessingError):
    pass

class AudioTooLargeError(AudioProcessingError):
    pass

class EmptyAudioError(AudioProcessingError):
    """Audio file contains no detectable speech."""
    pass


# ── MinIO ─────────────────────────────────────────────────────

class MinIOError(AIPBaseError):
    def __init__(self, message: str, bucket: str | None = None, key: str | None = None):
        self.bucket = bucket
        self.key = key
        super().__init__(message)

class MinIODownloadError(MinIOError):
    pass

class MinIOObjectNotFoundError(MinIODownloadError):
    pass

class MinIOUploadError(MinIOError):
    pass


# ── Model ─────────────────────────────────────────────────────

class ModelNotLoadedError(AIPBaseError):
    def __init__(self, model_name: str):
        self.model_name = model_name
        super().__init__(f"Model '{model_name}' is not loaded yet. Try again in a few seconds.")

class ModelInferenceError(AIPBaseError):
    def __init__(self, model_name: str, message: str):
        self.model_name = model_name
        super().__init__(f"{model_name}: {message}")


# ── Job ───────────────────────────────────────────────────────

class JobNotFoundError(AIPBaseError):
    def __init__(self, job_id: str):
        super().__init__(f"Job '{job_id}' not found")

class JobStateError(AIPBaseError):
    """Raised when a job operation is invalid for the current status."""
    pass

class JobAlreadyProcessingError(JobStateError):
    pass
```

---

### `app/exception_handlers.py`

```python
from fastapi import Request, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from app.exceptions import (
    ModelNotLoadedError, AudioProcessingError, UnsupportedAudioFormatError,
    AudioTooLargeError, MinIOObjectNotFoundError, MinIOError,
    JobNotFoundError, JobStateError,
)
import structlog, uuid

log = structlog.get_logger()


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "error": "validation_error",
            "message": "Request validation failed",
            "details": exc.errors(),
        },
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": "http_error", "message": exc.detail},
    )


async def model_not_loaded_handler(request: Request, exc: ModelNotLoadedError) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={"error": "model_not_ready", "message": str(exc), "model": exc.model_name},
        headers={"Retry-After": "30"},
    )


async def audio_error_handler(request: Request, exc: AudioProcessingError) -> JSONResponse:
    if isinstance(exc, UnsupportedAudioFormatError):
        return JSONResponse(status_code=400, content={"error": "unsupported_format", "message": str(exc)})
    if isinstance(exc, AudioTooLargeError):
        return JSONResponse(status_code=413, content={"error": "file_too_large", "message": str(exc)})
    return JSONResponse(status_code=422, content={"error": "audio_processing_error", "message": str(exc)})


async def minio_error_handler(request: Request, exc: MinIOError) -> JSONResponse:
    if isinstance(exc, MinIOObjectNotFoundError):
        return JSONResponse(status_code=404, content={"error": "minio_object_not_found", "message": str(exc)})
    return JSONResponse(status_code=502, content={"error": "storage_error", "message": str(exc)})


async def job_error_handler(request: Request, exc: JobNotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"error": "job_not_found", "message": str(exc)})


async def job_state_handler(request: Request, exc: JobStateError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"error": "job_state_error", "message": str(exc)})


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    error_id = str(uuid.uuid4())
    log.error("unhandled exception", error_id=error_id, exc_info=True)
    # Never expose traceback in production
    from app.config import settings
    body = {"error": "internal_error", "error_id": error_id, "message": "An unexpected error occurred"}
    if settings.log_level.upper() == "DEBUG":
        import traceback
        body["traceback"] = traceback.format_exc()
    return JSONResponse(status_code=500, content=body)
```

Register all in `app/main.py`:
```python
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(ModelNotLoadedError, model_not_loaded_handler)
app.add_exception_handler(AudioProcessingError, audio_error_handler)
app.add_exception_handler(MinIOError, minio_error_handler)
app.add_exception_handler(JobNotFoundError, job_error_handler)
app.add_exception_handler(JobStateError, job_state_handler)
app.add_exception_handler(Exception, generic_exception_handler)
```

---

### Edge case implementations (add to relevant service files)

#### Empty speech detection (in `transcription.py`)

```python
# After collecting segments:
if not full_text_parts or not "".join(full_text_parts).strip():
    log.info("no speech detected in audio", path=str(audio_path))
    return TranscriptionResult(
        text="",
        language=info.language,
        language_probability=info.language_probability,
        duration_seconds=info.duration,
        words=[],
        model_used=f"faster-whisper-{settings.whisper_model_size}",
        no_speech_detected=True,
    )
```

In Celery task — handle empty speech as success, not error:
```python
if result.no_speech_detected:
    log.info("no speech in audio, marking success with empty transcript", job_id=job_id)
    transcript = Transcription(
        job_id=job.id, full_text="", word_count=0,
        model_used=result.model_used, language=result.language,
        no_speech_detected=True,
    )
    # Continue to mark job as success
```

#### Job deduplication (in `minio_poller.py`)

```python
async def _job_exists_for_object(db, bucket: str, key: str) -> bool:
    result = await db.execute(
        select(Job).where(
            Job.minio_bucket == bucket,
            Job.minio_object_key == key,
            Job.status.in_(["pending", "processing", "success"]),
        ).limit(1)
    )
    return result.scalar_one_or_none() is not None
```

#### Segment overlap deduplication (in `segmentation.py`)

Already defined in Prompt 08. Ensure `is_overlap=True` is stored in DB and surfaced in API responses.

---

### Frontend: Error Boundary (`src/components/ErrorBoundary.tsx`)

```tsx
"use client";
import { Component, ReactNode } from "react";

interface Props { children: ReactNode; fallback?: ReactNode }
interface State { hasError: boolean; error: Error | null }

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error("ErrorBoundary caught:", error, info);
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback ?? (
        <div className="flex flex-col items-center justify-center p-8 gap-4">
          <p className="text-destructive font-semibold">Something went wrong</p>
          <p className="text-muted-foreground text-sm">{this.state.error?.message}</p>
          <button onClick={() => this.setState({ hasError: false, error: null })}>
            Try again
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
```

Wrap each page in `app/layout.tsx`:
```tsx
<ErrorBoundary>
  <main>{children}</main>
</ErrorBoundary>
```

---

### Frontend: API error display (`src/lib/api.ts` addition)

```typescript
export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    public body: unknown,
    message: string,
  ) { super(message); this.name = "ApiError"; }

  get isNotFound() { return this.status === 404; }
  get isValidation() { return this.status === 422; }
  get isModelNotReady() { return this.status === 503; }
  get isServerError() { return this.status >= 500; }

  // User-friendly message
  get displayMessage(): string {
    if (this.isModelNotReady) return "The AI model is still loading. Please try again in a moment.";
    if (this.isNotFound) return "The requested resource was not found.";
    if (this.isValidation) return "The request was invalid. Please check your input.";
    if (this.isServerError) return "A server error occurred. Please try again.";
    return this.message;
  }
}
```

---

## Constraints
- Exception handlers must be registered in ORDER from specific → generic (FastAPI matches first handler that applies)
- `generic_exception_handler` must ALWAYS be last
- `Retry-After: 30` header on 503 model responses tells clients when to retry
- Frontend `ErrorBoundary` must be a class component — hooks cannot catch render errors
- `no_speech_detected` flag must be stored in DB and returned in `TranscriptionDetail` API response (add field to Pydantic schema in Prompt 04)
- Never log sensitive data (file contents, audio bytes) — only log filenames, sizes, job IDs
