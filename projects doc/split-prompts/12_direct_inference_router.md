# Prompt 12 — Direct Inference Router (`/infer/*`)

## Goal
Implement all four direct inference endpoints: `/infer/transcribe`, `/infer/segment`, `/infer/sentiment`, `/infer/pipeline`. These are synchronous HTTP endpoints — one request, one response, no queue, no WebSocket.

## File to create: `app/routers/infer.py`

---

### Shared dependency: `resolve_audio_input`

Both multipart file uploads and MinIO references are valid inputs. Build a FastAPI dependency that resolves either into a local temp `Path`.

```python
async def resolve_audio_input(
    file: UploadFile | None = File(default=None),
    minio_ref: str | None = Form(default=None),  # JSON string of MinioReference
    db: AsyncSession = Depends(get_db),
) -> tuple[Path, str]:
    """
    Returns (temp_audio_path, original_filename).

    If `file` is provided:
        - Validate extension
        - Validate size <= settings.realtime_max_file_mb MB
        - Write to temp file using aiofiles
        - Return (temp_path, file.filename)

    If `minio_ref` is provided (JSON: {"bucket": "...", "object_key": "..."}):
        - Parse MinioReference from JSON string
        - Validate object exists in MinIO
        - Download to temp file via run_in_executor(minio_service.download_to_temp)
        - Return (temp_path, object_key.split("/")[-1])

    If neither: raise HTTP 422 with clear message.
    Raise HTTP 400 for unsupported file extension.
    Raise HTTP 413 for oversized file.
    """
```

The dependency does NOT normalise audio — normalisation is done inside each endpoint handler.

---

### Shared helper: `optionally_save_job`

```python
async def optionally_save_job(
    save: bool,
    source: str,
    filename: str,
    file_size: int | None,
    task_types: list[str],
    result_saver: Callable,   # async callable that saves results given job_id
    db: AsyncSession,
) -> UUID | None:
    """
    If save=True:
        1. Create Job record (status='success', source='direct', completed_at=now())
        2. Call result_saver(job_id) to persist the specific results
        3. Return job.id
    If save=False:
        Return None
    """
```

---

### `POST /api/v1/infer/transcribe`

```python
@router.post("/transcribe", response_model=TranscribeResponse)
async def direct_transcribe(
    save: bool = Query(default=False),
    model: str = Query(default=None),   # override WHISPER_MODEL_SIZE for this call
    audio: tuple[Path, str] = Depends(resolve_audio_input),
    db: AsyncSession = Depends(get_db),
):
    """
    1. Unpack audio → (temp_path, filename)
    2. t_start = time.perf_counter()
    3. Normalise: norm_path = await run_in_executor(normalise_audio, temp_path)
    4. Get duration: duration = await run_in_executor(get_audio_duration, norm_path)
    5. Transcribe: result = await run_in_executor(transcribe_with_chunking, norm_path)
       - If `model` query param provided and differs from settings: temporarily use that model size
         (note: changing model size requires reloading — only allow if model is already loaded for
         requested size, otherwise HTTP 400 "model not loaded, use default")
    6. Cleanup temp files (both original and normalised)
    7. processing_time = time.perf_counter() - t_start
    8. job_id = await optionally_save_job(...) if save else None
    9. Return TranscribeResponse(
           job_id=job_id,
           language=result.language,
           duration_seconds=duration,
           model_used=result.model_used,
           text=result.text,
           words=[WordTimestamp(**w.__dict__) for w in result.words],
           processing_time_seconds=round(processing_time, 3),
       )
    """
```

---

### `POST /api/v1/infer/segment`

```python
@router.post("/segment", response_model=SegmentResponse)
async def direct_segment(
    save: bool = Query(default=False),
    num_speakers: int | None = Query(default=None, ge=1, le=20),
    audio: tuple[Path, str] = Depends(resolve_audio_input),
    db: AsyncSession = Depends(get_db),
):
    """
    1. Normalise audio
    2. Get duration
    3. Diarise: result = await run_in_executor(diarise_with_chunking, norm_path, num_speakers)
    4. Cleanup
    5. Save if requested
    6. Return SegmentResponse(
           job_id=job_id,
           duration_seconds=duration,
           num_speakers=result.num_speakers,
           model_used=result.model_used,
           segments=[SegmentItem(index=s.index, speaker=s.speaker, start=s.start, end=s.end, is_overlap=s.is_overlap)
                     for s in result.segments],
           processing_time_seconds=...,
       )
    """
```

---

### `POST /api/v1/infer/sentiment`

This endpoint has two modes: audio input OR plain text input (no audio). Handle both.

```python
@router.post("/sentiment", response_model=SentimentResponse)
async def direct_sentiment(
    save: bool = Query(default=False),
    chunk_by: str = Query(default="sentence", pattern="^(sentence|paragraph|full)$"),
    # For text-only mode (no file upload needed):
    text: str | None = Form(default=None),
    # For audio mode (handled by resolve_audio_input):
    file: UploadFile | None = File(default=None),
    minio_ref: str | None = Form(default=None),
    db: AsyncSession = Depends(get_db),
):
    """
    Mode A — text provided directly:
        - Skip audio processing entirely
        - chunks = await run_in_executor(analyse_chunks, text, chunk_by)
        - overall = compute_overall_sentiment([c for c in chunks])

    Mode B — audio provided (file or minio_ref):
        - Resolve audio input manually (call resolve_audio_input logic inline since we have custom Form fields)
        - Normalise audio
        - Transcribe to get text
        - Run analyse_chunks on transcript

    Either mode:
        - Save if requested
        - Return SentimentResponse(
              job_id=job_id,
              model_used=settings.sentiment_model,
              overall={"label": overall.label, "score": overall.score},
              chunks=[SentimentChunk(index=i, text=c.text, label=c.label, score=c.score)
                      for i, c in enumerate(chunks)],
              processing_time_seconds=...,
          )

    If neither text nor audio provided: raise HTTP 422.
    """
```

---

### `POST /api/v1/infer/pipeline`

```python
@router.post("/pipeline", response_model=PipelineResponse)
async def direct_pipeline(
    save: bool = Query(default=False),
    task_types: str = Query(default="transcription,segmentation,sentiment"),
    # task_types is comma-separated string for simplicity with multipart forms
    audio: tuple[Path, str] = Depends(resolve_audio_input),
    db: AsyncSession = Depends(get_db),
):
    """
    1. Parse task_types: tasks = [t.strip() for t in task_types.split(",")]
    2. Validate: only 'transcription','segmentation','sentiment' allowed; raise 400 on invalid
    3. Enforce dependency: 'sentiment' requires 'transcription' if audio input (not text)
    4. Normalise audio, get duration

    Execute in dependency order:
    5. If 'transcription' in tasks:
       transcription_result = await run_in_executor(transcribe_with_chunking, norm_path)
    6. If 'segmentation' in tasks:
       seg_result = await run_in_executor(diarise_with_chunking, norm_path)
       If transcription_result exists:
           aligned = align_segments_with_transcript(seg_result.segments, transcription_result.words)
       Else:
           aligned = seg_result.segments  (no text, just time+speaker)
    7. If 'sentiment' in tasks:
       If aligned segments with text exist:
           sentiment_results = await run_in_executor(analyse_segments, aligned)
       Elif transcription_result exists:
           sentiment_results = await run_in_executor(analyse_chunks, transcription_result.text)
       overall = compute_overall_sentiment(sentiment_results)

    8. Build PipelineSegment list: merge seg + sentiment per segment
    9. Cleanup temp files
    10. Save if requested (save all: transcription + segments + sentiment in one DB transaction)
    11. Return PipelineResponse(...)
    """
```

---

## Constraints
- All ML calls must use `asyncio.get_event_loop().run_in_executor(None, ...)` — never call sync ML functions directly in async route handlers (blocks the event loop)
- Temp file cleanup must be in `try/finally` blocks — always clean up regardless of success or failure
- `resolve_audio_input` is a generator dependency — use `try/finally` or `contextlib.asynccontextmanager` to ensure cleanup even on HTTP errors
- HTTP 503 must be returned if a required model is not loaded: check `is_model_loaded()` at start of each handler before doing any work
- Processing time must be measured with `time.perf_counter()`, not `datetime.now()`
- Log each inference call at INFO level: endpoint, filename, duration_seconds, processing_time_seconds
