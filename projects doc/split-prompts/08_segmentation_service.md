# Prompt 08 — Segmentation Service (pyannote.audio)

## Goal
Build the speaker diarisation service using `pyannote.audio`. Same singleton pattern as the transcription service. Supports stand-alone diarisation (no transcript needed) and a combined mode that aligns segments with an existing transcript.

## File to create: `app/services/segmentation.py`

---

### Model singleton

```python
_pipeline: Pipeline | None = None
_pipeline_lock = threading.Lock()

def get_pipeline() -> Pipeline:
    global _pipeline
    if _pipeline is None:
        with _pipeline_lock:
            if _pipeline is None:
                _pipeline = _load_pipeline()
    return _pipeline

def _load_pipeline() -> Pipeline:
    from pyannote.audio import Pipeline
    # Load from local cache first, fallback to HuggingFace Hub
    model_path = Path(settings.models_dir) / "pyannote"
    pipeline = Pipeline.from_pretrained(
        settings.pyannote_model,
        use_auth_token=settings.hf_token or None,
        cache_dir=str(model_path),
    )
    # Move to GPU if available
    if settings.whisper_device == "cuda":
        import torch
        pipeline = pipeline.to(torch.device("cuda"))
    return pipeline

def is_pipeline_loaded() -> bool:
    return _pipeline is not None

def get_pipeline_info() -> dict:
    return {
        "loaded": is_pipeline_loaded(),
        "model": settings.pyannote_model,
    }
```

---

### `diarise(audio_path: Path, num_speakers: int | None = None) -> DiarisationResult`

Run speaker diarisation on the normalised WAV file.

```python
@dataclass
class SpeakerSegment:
    index: int
    speaker: str        # e.g. "SPEAKER_00"
    start: float        # seconds
    end: float          # seconds
    is_overlap: bool    # True if multiple speakers at same time

@dataclass
class DiarisationResult:
    segments: list[SpeakerSegment]
    num_speakers: int
    model_used: str
    duration_seconds: float
```

Implementation:
```python
def diarise(audio_path: Path, num_speakers: int | None = None) -> DiarisationResult:
    pipeline = get_pipeline()
    params = {}
    if num_speakers:
        params["num_speakers"] = num_speakers

    diarization = pipeline(str(audio_path), **params)

    segments = []
    idx = 0
    for turn, _, speaker in diarization.itertracks(yield_label=True):
        segments.append(SpeakerSegment(
            index=idx,
            speaker=speaker,
            start=round(turn.start, 3),
            end=round(turn.end, 3),
            is_overlap=False,     # detect below
        ))
        idx += 1

    # Detect overlapping segments
    _mark_overlaps(segments)

    return DiarisationResult(
        segments=segments,
        num_speakers=len({s.speaker for s in segments}),
        model_used=settings.pyannote_model,
        duration_seconds=_get_duration(diarization),
    )
```

---

### `_mark_overlaps(segments: list[SpeakerSegment]) -> None`

Mutate segments in-place. A segment is an overlap if its time range intersects with any other segment.

```python
# For each pair (i, j) where i != j:
#   if segment[i].start < segment[j].end and segment[i].end > segment[j].start:
#       mark both as is_overlap = True
```

---

### `align_segments_with_transcript(segments: list[SpeakerSegment], words: list[WordResult]) -> list[AlignedSegment]`

Assign transcript words to each speaker segment based on time overlap. Returns enriched segments with text.

```python
@dataclass
class AlignedSegment:
    index: int
    speaker: str
    start: float
    end: float
    is_overlap: bool
    text: str        # words whose midpoint falls within [start, end]
    word_count: int
```

Logic:
- For each word, compute midpoint = `(word.start + word.end) / 2`
- Assign word to the segment whose `[start, end]` contains the midpoint
- If no segment contains the midpoint, assign to the nearest segment by midpoint distance
- Concatenate assigned words to form `text`

---

### `diarise_with_chunking(audio_path: Path, ...) -> DiarisationResult`

Wrapper that chunks long audio (same 30-minute threshold as transcription), diarises each chunk, stitches results using `audio_utils.stitch_segments()`.

---

### `preload_pipeline() -> None`

Eager load at startup. Same pattern as transcription service.

---

## Constraints
- pyannote pipeline is NOT thread-safe for concurrent GPU calls — use `_pipeline_lock` as a per-call lock around `pipeline(audio_path)` if running on GPU (CPU is safe for concurrent calls)
- If `settings.hf_token` is empty string, pass `None` to `use_auth_token` — pyannote will try local cache only. Log a WARNING that HF token is missing (model may not load on first run)
- `diarise` must handle audio with only one speaker — `num_speakers=1` is valid, return single segment covering full duration
- Round all timestamps to 3 decimal places (millisecond precision)
- Log diarisation duration at INFO level
