# Prompt 06 — Audio Utilities (ffmpeg normalisation & chunking)

## Goal
Build the audio utility layer that normalises any input audio format to 16kHz mono WAV (required by Whisper and pyannote) and handles chunking of long audio files.

## File to create: `app/services/audio_utils.py`

### All functions must be synchronous (called inside Celery workers and FastAPI thread pool)

---

### `normalise_audio(input_path: Path, output_dir: Path | None = None) -> Path`

Convert any audio file to 16kHz mono WAV using ffmpeg.

- If `output_dir` is None, use `tempfile.gettempdir()`
- Output filename: `{stem}_{uuid4_short}.wav`
- ffmpeg command equivalent:
  ```
  ffmpeg -i input -ar 16000 -ac 1 -c:a pcm_s16le output.wav -y -loglevel error
  ```
- Use `ffmpeg-python` library (not subprocess directly)
- If ffmpeg fails (non-zero exit), raise `AudioProcessingError(message, input_path)`
- Detect and raise `UnsupportedAudioFormatError` if input extension not in allowed set
- Return `Path` to the normalised WAV file

**Allowed input formats:** `.mp3 .wav .flac .ogg .m4a .webm .mp4`

---

### `get_audio_duration(audio_path: Path) -> float`

Return duration in seconds using ffprobe.

```python
# Use ffmpeg.probe() — returns dict with stream info
# Look for stream where codec_type == 'audio'
# Return float(stream['duration'])
# Raise AudioProcessingError if no audio stream found
```

---

### `chunk_audio(audio_path: Path, chunk_duration_seconds: int = 600, overlap_seconds: int = 10) -> list[AudioChunk]`

Split long audio into overlapping chunks.

- Only chunks if duration > `chunk_duration_seconds` (default 10 minutes)
- Each chunk overlaps with previous by `overlap_seconds` (default 10 seconds) — this prevents word cut-off at boundaries
- Returns list of `AudioChunk` objects
- If audio is short enough, returns a single-element list containing the original file (no splitting)

```python
@dataclass
class AudioChunk:
    path: Path
    start_seconds: float    # position in original audio
    end_seconds: float
    chunk_index: int
    is_last: bool
```

ffmpeg trim command per chunk:
```
ffmpeg -i input -ss {start} -to {end} -c copy output_chunk_{i}.wav
```

---

### `stitch_transcriptions(chunks: list[ChunkTranscription]) -> StitchedTranscription`

Merge transcription results from multiple chunks back into a single coherent result.

```python
@dataclass
class ChunkTranscription:
    chunk: AudioChunk
    words: list[dict]     # [{word, start, end, probability}]
    text: str

@dataclass
class StitchedTranscription:
    full_text: str
    words: list[dict]     # timestamps adjusted to global position
```

Logic:
- Adjust each word's `start` and `end` by adding `chunk.start_seconds`
- In the overlap zone (last `overlap_seconds` of a chunk = first `overlap_seconds` of next): deduplicate words by keeping the version with higher probability
- Concatenate texts with a space

---

### `stitch_segments(chunks: list[ChunkSegments]) -> list[dict]`

Merge speaker segments from multiple chunks.

```python
@dataclass
class ChunkSegments:
    chunk: AudioChunk
    segments: list[dict]   # [{speaker, start, end}]
```

- Adjust all `start`/`end` timestamps by `chunk.start_seconds`
- Merge consecutive segments from the same speaker if gap < 0.5 seconds
- Re-index `segment_index` sequentially

---

### `cleanup_temp_files(*paths: Path) -> None`

Delete a list of temp files. Log any deletion errors at WARNING level but do not raise.

---

### `AudioProcessingError(Exception)`
### `UnsupportedAudioFormatError(AudioProcessingError)`

Define in `app/exceptions.py` (add to existing file from Prompt 05).

---

## Constraints
- Never mutate the original input file — always work on copies in temp dirs
- All temp files created by this module must use unique names (UUID prefix) to be safe for concurrent workers
- `chunk_audio` must not load the entire file into memory — use ffmpeg's `-ss`/`-to` flags (stream-based trim)
- Log ffmpeg stderr output at DEBUG level on success, ERROR level on failure
- All `Path` arguments must be validated to exist before processing; raise `FileNotFoundError` with a clear message if not
