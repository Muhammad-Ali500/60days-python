# Prompt 11 — WebSocket Connection Manager & Real-time Router

## Goal
Build the WebSocket connection manager that handles streaming transcription tokens to the browser, and the real-time router that accepts direct file uploads and orchestrates in-process processing with live progress.

## Files to create

---

### `app/websocket/manager.py`

Manages active WebSocket connections, keyed by `job_id`.

```python
class ConnectionManager:
    def __init__(self):
        # active_connections: dict[str, WebSocket]  (job_id → websocket)
        self._connections: dict[str, WebSocket] = {}
        self._lock = asyncio.Lock()

    async def connect(self, job_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections[job_id] = websocket

    async def disconnect(self, job_id: str) -> None:
        async with self._lock:
            self._connections.pop(job_id, None)

    async def send(self, job_id: str, event: dict) -> bool:
        # Returns True if sent, False if no connection for this job_id
        ws = self._connections.get(job_id)
        if ws:
            try:
                await ws.send_json(event)
                return True
            except Exception:
                await self.disconnect(job_id)
        return False

    async def send_progress(self, job_id: str, step: str, percent: int) -> None:
        await self.send(job_id, {"event": "progress", "step": step, "percent": percent})

    async def send_token(self, job_id: str, word: str, start: float, end: float) -> None:
        await self.send(job_id, {"event": "token", "text": word, "start": start, "end": end})

    async def send_segment(self, job_id: str, segment: dict) -> None:
        await self.send(job_id, {"event": "segment", **segment})

    async def send_sentiment(self, job_id: str, data: dict) -> None:
        await self.send(job_id, {"event": "sentiment", **data})

    async def send_done(self, job_id: str) -> None:
        await self.send(job_id, {"event": "done", "job_id": job_id})

    async def send_error(self, job_id: str, message: str) -> None:
        await self.send(job_id, {"event": "error", "message": message})

    def is_connected(self, job_id: str) -> bool:
        return job_id in self._connections

# Singleton
manager = ConnectionManager()
```

---

### `app/routers/realtime.py`

Two endpoints:

#### `POST /api/v1/realtime/upload`

```python
@router.post("/upload", response_model=RealtimeUploadResponse)
async def upload_for_realtime(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    task_types: list[str] = Form(default=["transcription", "segmentation", "sentiment"]),
    db: AsyncSession = Depends(get_db),
):
    """
    1. Validate file:
       - Extension must be in allowed set
       - Size must be <= settings.realtime_max_file_mb * 1024 * 1024
       - Raise HTTP 400 for invalid extension
       - Raise HTTP 413 for oversized file

    2. Save uploaded file to temp path: /tmp/aip_rt_{uuid4}_{filename}
       - Use aiofiles to write asynchronously

    3. Create Job record in DB:
       - source = 'realtime'
       - status = 'pending'
       - original_filename = file.filename
       - file_size_bytes = file.size
       - task_types = task_types (validate: only 'transcription','segmentation','sentiment' allowed)

    4. Build WebSocket URL:
       ws_url = f"{settings.next_public_ws_url}/realtime/stream/{job.id}"

    5. Add background task: process_realtime_job(job_id=str(job.id), temp_path=str(temp_path), task_types=task_types)

    6. Return RealtimeUploadResponse(job_id=job.id, ws_url=ws_url)
    """
```

#### `WS /api/v1/realtime/stream/{job_id}`

```python
@router.websocket("/stream/{job_id}")
async def stream_realtime(websocket: WebSocket, job_id: str, db: AsyncSession = Depends(get_db)):
    """
    1. Validate job_id exists in DB, raise 404 if not
    2. Register websocket with manager.connect(job_id, websocket)
    3. Wait for messages from client (keep-alive pings) or disconnect
    4. On disconnect: manager.disconnect(job_id)
    5. Timeout: if job finishes and sends "done" event, close gracefully
    """
    await manager.connect(job_id, websocket)
    try:
        while True:
            # Keep connection alive; wait for client ping or disconnect
            data = await asyncio.wait_for(websocket.receive_text(), timeout=30)
            # Ignore client messages (they're just keep-alives)
    except (WebSocketDisconnect, asyncio.TimeoutError):
        pass
    finally:
        await manager.disconnect(job_id)
```

---

### `app/workers/realtime_processor.py`

The background task that runs the actual processing and pushes events to the WebSocket.

```python
async def process_realtime_job(job_id: str, temp_path: str, task_types: list[str]) -> None:
    """
    Runs in FastAPI's background tasks (async, same process).
    Bridges sync ML calls to async WebSocket sends via asyncio.get_event_loop().run_in_executor().

    Steps:
    1. Update job status → 'processing'
    2. await manager.send_progress(job_id, "normalising", 5)
    3. Run normalise_audio in executor (sync → async bridge)
    4. Get duration, update job

    If 'transcription' in task_types:
    5. await manager.send_progress(job_id, "transcription", 10)
    6. Run transcribe_streaming in executor:
       - on_word callback: puts word into asyncio.Queue
       - Separate coroutine drains the queue and calls manager.send_token()
    7. Save transcription to DB
    8. await manager.send_progress(job_id, "transcription", 60)

    If 'segmentation' in task_types:
    9. await manager.send_progress(job_id, "segmentation", 65)
    10. Run diarise in executor
    11. If transcription exists: align_segments_with_transcript()
    12. For each segment: await manager.send_segment(job_id, segment_dict)
    13. Save segments to DB
    14. await manager.send_progress(job_id, "segmentation", 85)

    If 'sentiment' in task_types:
    15. await manager.send_progress(job_id, "sentiment", 87)
    16. Run analyse_segments or analyse_chunks in executor
    17. For each result: await manager.send_sentiment(job_id, sentiment_dict)
    18. Save sentiment to DB
    19. await manager.send_progress(job_id, "sentiment", 98)

    20. Update job status → 'success', completed_at=now()
    21. await manager.send_progress(job_id, "done", 100)
    22. await manager.send_done(job_id)
    23. Cleanup temp files

    On any exception:
    - Update job status → 'failed', error_message=str(exc)
    - await manager.send_error(job_id, str(exc))
    - Cleanup temp files
    """
```

**Async bridge for streaming transcription:**
```python
async def _stream_transcription_tokens(audio_path: Path, job_id: str, loop: asyncio.AbstractEventLoop):
    token_queue: asyncio.Queue = asyncio.Queue()

    def on_word(word_result):
        # Called from thread (sync) — put into queue safely
        loop.call_soon_threadsafe(token_queue.put_nowait, word_result)

    # Run blocking transcription in thread
    future = loop.run_in_executor(
        None,
        lambda: transcribe_streaming(audio_path, on_word=on_word)
    )

    # Drain queue while transcription runs
    while not future.done() or not token_queue.empty():
        try:
            word = await asyncio.wait_for(token_queue.get(), timeout=0.1)
            await manager.send_token(job_id, word.word, word.start, word.end)
        except asyncio.TimeoutError:
            continue

    return await future
```

## Constraints
- `process_realtime_job` must always clean up temp files even on exception
- WebSocket timeout of 60 seconds (`settings.websocket_connect_timeout_seconds`) only applies to the waiting period before processing starts — if already processing, no timeout
- `send()` in the manager must silently ignore disconnected clients (never raise to the processing goroutine)
- File size check must happen before writing to disk (check `Content-Length` header first, reject early)
