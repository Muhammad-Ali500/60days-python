# Prompt 07 — Transcription Service (faster-whisper)

## Goal
Build the transcription service using `faster-whisper`. The model must be loaded once as a module-level singleton and reused across all calls. Support streaming word-level output for the WebSocket real-time path.

## File to create: `app/services/transcription.py`

---

### Model singleton

```python
# Module-level state
_model: WhisperModel | None = None
_model_lock = threading.Lock()

def get_model() -> WhisperModel:
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:   # double-checked locking
                _model = _load_model()
    return _model

def _load_model() -> WhisperModel:
    # Load faster-whisper WhisperModel
    # model_size = settings.whisper_model_size
    # device = settings.whisper_device
    # compute_type = settings.whisper_compute_type
    # download_root = settings.models_dir + "/whisper"
    # Log load start and end with timing
    # Return loaded model
    ...

def is_model_loaded() -> bool:
    return _model is not None

def get_model_info() -> dict:
    return {
        "loaded": is_model_loaded(),
        "model_size": settings.whisper_model_size,
        "device": settings.whisper_device,
        "compute_type": settings.whisper_compute_type,
    }
```

---

### `transcribe(audio_path: Path, language: str | None = None) -> TranscriptionResult`

Full blocking transcription. Returns only after complete.

```python
@dataclass
class TranscriptionResult:
    text: str
    language: str
    language_probability: float
    duration_seconds: float
    words: list[WordResult]
    model_used: str

@dataclass
class WordResult:
    word: str
    start: float
    end: float
    probability: float
```

Implementation:
```python
def transcribe(audio_path: Path, language: str | None = None) -> TranscriptionResult:
    model = get_model()
    segments, info = model.transcribe(
        str(audio_path),
        language=language,
        word_timestamps=True,
        vad_filter=True,           # filter silence
        vad_parameters={"min_silence_duration_ms": 500},
        beam_size=5,
    )
    # Collect all segments and words
    all_words = []
    full_text_parts = []
    for segment in segments:
        full_text_parts.append(segment.text)
        if segment.words:
            for w in segment.words:
                all_words.append(WordResult(word=w.word, start=w.start, end=w.end, probability=w.probability))

    return TranscriptionResult(
        text=" ".join(full_text_parts).strip(),
        language=info.language,
        language_probability=info.language_probability,
        duration_seconds=info.duration,
        words=all_words,
        model_used=f"faster-whisper-{settings.whisper_model_size}",
    )
```

**Handle empty speech:**
- If `full_text_parts` is empty or all whitespace → return `TranscriptionResult` with `text=""` and a flag attribute `no_speech_detected=True`
- Do not raise — empty audio is a valid result

---

### `transcribe_streaming(audio_path: Path, on_word: Callable[[WordResult], None], language: str | None = None) -> TranscriptionResult`

Same as `transcribe` but calls `on_word(word)` callback for each word as it's produced (before full completion). Used by the WebSocket real-time path.

```python
def transcribe_streaming(
    audio_path: Path,
    on_word: Callable[[WordResult], None],
    language: str | None = None,
) -> TranscriptionResult:
    model = get_model()
    segments, info = model.transcribe(...)   # same params as above
    all_words = []
    full_text_parts = []
    for segment in segments:
        full_text_parts.append(segment.text)
        if segment.words:
            for w in segment.words:
                wr = WordResult(...)
                all_words.append(wr)
                on_word(wr)    # ← fires callback immediately for each word
    return TranscriptionResult(...)
```

The `on_word` callback is called in the same thread. The WebSocket handler wraps this in an executor and bridges to async via a queue.

---

### `preload_model() -> None`

Called at worker/server startup to eagerly load the model before the first request.

```python
def preload_model() -> None:
    log.info("preloading whisper model", size=settings.whisper_model_size)
    get_model()
    log.info("whisper model loaded")
```

---

### `transcribe_with_chunking(audio_path: Path, ...) -> TranscriptionResult`

Wrapper that:
1. Calls `audio_utils.get_audio_duration()`
2. If duration > 30 minutes: calls `audio_utils.chunk_audio()`, transcribes each chunk, then `audio_utils.stitch_transcriptions()`
3. Otherwise: calls `transcribe()` directly
4. Always cleans up chunk temp files

---

## Constraints
- `get_model()` is thread-safe (multiple Celery workers in same process share one model instance)
- If the model files are not present in `models_dir`, `faster-whisper` will auto-download them on first call — this is acceptable and expected on first run
- Log transcription duration and audio duration at INFO level for every call (throughput tracking)
- Do not catch `Exception` broadly — let real errors propagate to Celery retry logic
- `transcribe_streaming` must work even if `on_word` raises — catch callback exceptions, log at WARNING, continue transcription
