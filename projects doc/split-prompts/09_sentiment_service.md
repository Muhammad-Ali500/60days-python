# Prompt 09 — Sentiment Analysis Service (HuggingFace)

## Goal
Build the sentiment analysis service using a local HuggingFace transformer model. Supports three input modes: per speaker segment, per text chunk (sentence/paragraph), and full document.

## File to create: `app/services/sentiment.py`

---

### Model singleton

```python
_tokenizer = None
_model = None
_model_lock = threading.Lock()

def get_model():
    global _tokenizer, _model
    if _model is None:
        with _model_lock:
            if _model is None:
                _tokenizer, _model = _load_model()
    return _tokenizer, _model

def _load_model():
    from transformers import AutoTokenizer, AutoModelForSequenceClassification
    import torch

    model_path = Path(settings.models_dir) / "sentiment"
    tokenizer = AutoTokenizer.from_pretrained(
        settings.sentiment_model,
        cache_dir=str(model_path),
    )
    model = AutoModelForSequenceClassification.from_pretrained(
        settings.sentiment_model,
        cache_dir=str(model_path),
    )
    device = "cuda" if settings.whisper_device == "cuda" else "cpu"
    model = model.to(device)
    model.eval()
    return tokenizer, model

def is_model_loaded() -> bool:
    return _model is not None

def get_model_info() -> dict:
    return {
        "loaded": is_model_loaded(),
        "model": settings.sentiment_model,
    }
```

---

### `analyse_text(text: str) -> SentimentScore`

Analyse a single text string.

```python
@dataclass
class SentimentScore:
    label: str     # "positive" | "negative" | "neutral"
    score: float   # confidence 0.0–1.0
    all_scores: dict[str, float]   # all label scores, e.g. {"positive": 0.9, "negative": 0.05, "neutral": 0.05}
```

Implementation:
```python
def analyse_text(text: str) -> SentimentScore:
    if not text or not text.strip():
        return SentimentScore(label="neutral", score=1.0, all_scores={"neutral": 1.0})

    tokenizer, model = get_model()
    import torch, torch.nn.functional as F

    device = next(model.parameters()).device
    inputs = tokenizer(
        text,
        return_tensors="pt",
        truncation=True,
        max_length=512,
        padding=True,
    ).to(device)

    with torch.no_grad():
        outputs = model(**inputs)
        scores = F.softmax(outputs.logits, dim=-1)[0]

    id2label = model.config.id2label
    label_scores = {id2label[i]: round(float(s), 4) for i, s in enumerate(scores)}
    best_label = max(label_scores, key=label_scores.get)

    return SentimentScore(
        label=best_label.lower(),
        score=label_scores[best_label],
        all_scores={k.lower(): v for k, v in label_scores.items()},
    )
```

---

### `analyse_segments(segments: list[AlignedSegment | SpeakerSegment]) -> list[SegmentSentiment]`

Run sentiment on each speaker segment's text. Used after segmentation + alignment.

```python
@dataclass
class SegmentSentiment:
    segment_index: int
    speaker: str
    text: str
    label: str
    score: float
    all_scores: dict[str, float]
```

- Skip segments where `text` is empty or whitespace → assign `label="neutral", score=1.0`
- Run in a loop (batch if text count > 8 for efficiency — see `analyse_batch` below)

---

### `analyse_chunks(text: str, chunk_by: str = "sentence") -> list[ChunkSentiment]`

Split text into chunks and analyse each.

```python
@dataclass
class ChunkSentiment:
    index: int
    text: str
    label: str
    score: float
    all_scores: dict[str, float]
```

`chunk_by` options:
- `"sentence"` → split on `.!?` followed by whitespace. Use `re.split(r'(?<=[.!?])\s+', text)`
- `"paragraph"` → split on `\n\n`
- `"full"` → single chunk (entire text)

Filter out empty chunks after splitting.

---

### `analyse_batch(texts: list[str]) -> list[SentimentScore]`

Batch inference for efficiency when analysing many short texts.

```python
def analyse_batch(texts: list[str]) -> list[SentimentScore]:
    # Tokenize all at once with padding
    # Run model.forward() once
    # Return list of SentimentScore in same order as input
    # Max batch size: 16 (split into batches if len(texts) > 16)
    ...
```

---

### `compute_overall_sentiment(scores: list[SentimentScore]) -> SentimentScore`

Compute aggregate sentiment from a list of scores.

- Weighted average of scores by label
- The label with the highest average weighted score is the overall label
- Return `SentimentScore` with `score` = confidence of the winning label

---

### `preload_model() -> None`

Eager load at startup.

---

## Constraints
- Truncate inputs to 512 tokens (model limit) — log at DEBUG when truncation occurs
- `analyse_text("")` must return neutral safely, never raise
- Model runs in `torch.no_grad()` always — never gradient tracking in inference
- Label normalisation: the cardiffnlp model may return labels like `LABEL_0`, `LABEL_1`, `LABEL_2` or `positive`/`negative`/`neutral` depending on version — normalise all labels to lowercase `positive`/`negative`/`neutral` using `model.config.id2label` mapping
- All GPU tensors must be `.to(device)` before forward pass
