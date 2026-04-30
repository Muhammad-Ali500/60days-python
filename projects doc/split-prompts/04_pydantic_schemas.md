# Prompt 04 — Pydantic Request & Response Schemas

## Goal
Write all Pydantic v2 schemas used for API request validation and response serialisation. These schemas are the contract between the frontend/callers and the FastAPI backend.

## Files to create

### `app/schemas/__init__.py`
Export everything.

### `app/schemas/job.py`

```python
# JobStatus enum
class JobStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    success = "success"
    failed = "failed"
    dead = "dead"

# JobSource enum
class JobSource(str, Enum):
    minio = "minio"
    realtime = "realtime"
    direct = "direct"

# Base job schema (shared fields)
class JobBase(BaseModel): ...

# Response schema — flat job summary (for list view)
class JobSummary(BaseModel):
    id: UUID
    source: JobSource
    status: JobStatus
    original_filename: str
    file_size_bytes: int | None
    audio_duration_seconds: float | None
    task_types: list[str]
    retry_count: int
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None

    @computed_field
    @property
    def duration_processing_seconds(self) -> float | None:
        # completed_at - started_at in seconds, or None
        ...

    model_config = ConfigDict(from_attributes=True)

# Paginated list response
class JobListResponse(BaseModel):
    items: list[JobSummary]
    total: int
    page: int
    limit: int
    pages: int

# Nested transcription in detail response
class TranscriptionDetail(BaseModel):
    id: UUID
    language: str | None
    full_text: str
    word_count: int | None
    model_used: str
    words: list[WordTimestamp] | None   # from words_json
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

# Word timestamp (for transcription words array)
class WordTimestamp(BaseModel):
    word: str
    start: float
    end: float
    probability: float

# Nested segment in detail response
class SegmentDetail(BaseModel):
    id: UUID
    speaker_label: str | None
    start_time: float
    end_time: float
    text: str | None
    segment_index: int
    is_overlap: bool
    sentiment: SentimentDetail | None = None   # joined if available
    model_config = ConfigDict(from_attributes=True)

# Nested sentiment result
class SentimentDetail(BaseModel):
    id: UUID
    label: str
    score: float
    model_used: str
    chunk_index: int | None
    chunk_text: str | None
    model_config = ConfigDict(from_attributes=True)

# Full job detail response (for /jobs/{id})
class JobDetail(JobSummary):
    transcription: TranscriptionDetail | None
    segments: list[SegmentDetail]
    sentiment_summary: SentimentSummary | None

# Sentiment summary (overall stats for a job)
class SentimentSummary(BaseModel):
    label: str        # dominant label
    score: float
    positive_pct: float
    negative_pct: float
    neutral_pct: float
```

### `app/schemas/infer.py`

```python
# Request for MinIO-reference input (used on all /infer/* endpoints as alternative to file upload)
class MinioReference(BaseModel):
    bucket: str
    object_key: str

# Transcription response
class TranscribeResponse(BaseModel):
    job_id: UUID | None          # present if ?save=true
    language: str | None
    duration_seconds: float | None
    model_used: str
    text: str
    words: list[WordTimestamp]
    processing_time_seconds: float

# Segment response
class SegmentResponse(BaseModel):
    job_id: UUID | None
    duration_seconds: float | None
    num_speakers: int
    model_used: str
    segments: list[SegmentItem]
    processing_time_seconds: float

class SegmentItem(BaseModel):
    index: int
    speaker: str
    start: float
    end: float
    is_overlap: bool

# Sentiment response
class SentimentChunk(BaseModel):
    index: int
    text: str
    label: str
    score: float

class SentimentResponse(BaseModel):
    job_id: UUID | None
    model_used: str
    overall: dict[str, Any]      # { label, score }
    chunks: list[SentimentChunk]
    processing_time_seconds: float

# Pipeline response (combined)
class PipelineResponse(BaseModel):
    job_id: UUID | None
    duration_seconds: float | None
    transcription: TranscribeResponse | None
    segments: list[PipelineSegment] | None
    sentiment_summary: dict[str, Any] | None
    processing_time_seconds: float

class PipelineSegment(BaseModel):
    index: int
    speaker: str
    start: float
    end: float
    text: str | None
    is_overlap: bool
    sentiment: SentimentChunk | None
```

### `app/schemas/queue.py`

```python
class QueueStats(BaseModel):
    active_workers: int
    active_tasks: int
    reserved_tasks: int
    scheduled_tasks: int
    failed_tasks: int
    total_processed: int

class MinioBucketInfo(BaseModel):
    bucket: str
    last_polled_at: datetime | None
    last_object_key: str | None
```

### `app/schemas/realtime.py`

```python
class RealtimeUploadResponse(BaseModel):
    job_id: UUID
    ws_url: str            # full WebSocket URL to connect to

class WSEventType(str, Enum):
    progress = "progress"
    token = "token"
    segment = "segment"
    sentiment = "sentiment"
    done = "done"
    error = "error"
```

## Constraints
- Use Pydantic v2 syntax throughout (`model_config = ConfigDict(...)`, not `class Config`)
- All `datetime` fields must be timezone-aware (`datetime` with `timezone=True` validator or `AwareDatetime`)
- `from_attributes=True` on all schemas that are built from ORM models
- No `Optional[X]` — use `X | None` (Python 3.10+ union syntax)
- All UUIDs as `uuid.UUID` type, not `str`
- Forward references resolved with `model_rebuild()` at bottom of file where needed (e.g., `SegmentDetail` references `SentimentDetail`)
