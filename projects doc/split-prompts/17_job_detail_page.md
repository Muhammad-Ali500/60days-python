# Prompt 17 — Job Detail Page

## Goal
Build the job detail page at `/jobs/[id]` showing full transcript, speaker segments with sentiment badges, a sentiment summary chart, and export/retry actions.

## Files to create

---

### `src/app/jobs/[id]/page.tsx`

```tsx
import { JobDetailClient } from "@/components/jobs/JobDetailClient";

interface Props { params: Promise<{ id: string }> }

export default async function JobDetailPage({ params }: Props) {
  const { id } = await params;
  return <JobDetailClient jobId={id} />;
}
```

---

### `src/components/jobs/JobDetailClient.tsx`

`"use client"` component. Uses `useJob(jobId)` which polls every 2s while processing.

Layout:
```
┌─ Job Header ────────────────────────────────────────────────┐
│  ← Back    filename.mp3           [StatusBadge]  [Actions ▼]│
│  Source: MinIO  |  Duration: 4:32  |  Created: 2h ago       │
│  Processing time: 12.4s  |  Model: faster-whisper-large-v3  │
└────────────────────────────────────────────────────────────┘
┌─ Tabs ──────────────────────────────────────────────────────┐
│  [Transcript]  [Segments]  [Sentiment]                       │
└────────────────────────────────────────────────────────────┘
  (tab content below)
```

**Loading state:** Full-page skeleton.
**Not found:** 404 card with "Job not found" and back button.
**Processing state:** Show progress indicator and "Processing…" message, auto-refreshes.

---

### Actions dropdown (top-right)

```
Export → JSON
Export → Plain Text (.txt)
Export → Subtitles (.srt)
──────────────
Retry (only if failed/dead)
──────────────
Delete
```

Export actions: `window.open(jobsApi.exportUrl(id, format))` — browser handles file download.

---

### Tab: Transcript (`src/components/jobs/TranscriptTab.tsx`)

```tsx
// If job.transcription is null: show "No transcription available" empty state

// Header row: language detected, word count, model used

// Full transcript block:
// <div className="prose max-w-none bg-muted rounded-lg p-4 font-mono text-sm leading-relaxed whitespace-pre-wrap">
//   {job.transcription.full_text}
// </div>

// Copy to clipboard button (top-right of transcript block)

// If job.transcription.words exists: show word count + duration stats
// Words per minute = word_count / (audio_duration / 60)
```

---

### Tab: Segments (`src/components/jobs/SegmentsTab.tsx`)

```tsx
// If no segments: empty state

// Summary line: "{N} speakers detected, {M} segments total"

// Speaker legend: colour-coded dots mapping SPEAKER_00 → Speaker 1, etc.
// Colours: [blue, green, orange, purple, pink, teal, ...] cycling

// Segments list:
// For each segment:
<SegmentCard
  segment={segment}
  speakerColor={colorMap[segment.speaker_label]}
  speakerName={`Speaker ${index + 1}`}
/>

// SegmentCard layout:
// ┌──────────────────────────────────────────────────────┐
// │ ● Speaker 1        0:00 → 0:05    [positive 94%]    │
// │ "Hello, how are you doing today?"                    │
// └──────────────────────────────────────────────────────┘
// - Timestamp formatted as m:ss.mmm → m:ss.mmm
// - Sentiment badge: colour-coded (green=positive, red=negative, grey=neutral)
// - is_overlap: show "⟨overlap⟩" indicator
```

---

### Tab: Sentiment (`src/components/jobs/SentimentTab.tsx`)

```tsx
// If no sentiment results: empty state

// Summary card:
// Overall label (large) + confidence score
// e.g. "POSITIVE  87% confidence"

// Three-bar breakdown:
<SentimentBar label="Positive" percent={summary.positive_pct} color="green" />
<SentimentBar label="Neutral"  percent={summary.neutral_pct}  color="gray"  />
<SentimentBar label="Negative" percent={summary.negative_pct} color="red"   />

// Per-speaker breakdown (if segments with speaker labels exist):
// Group sentiment results by speaker_label
// For each speaker: show mini bar chart of their positive/neutral/negative distribution

// Recharts pie chart: donut chart showing positive/neutral/negative proportions
// Legend below the chart
```

---

### `src/components/jobs/SentimentBar.tsx`

```tsx
// Animated progress bar:
// [Label]  [████████████░░░░░░░░░░░░]  87%
// Use CSS transition on width for animation on mount
```

---

### `src/components/jobs/JobMetaHeader.tsx`

Displays the metadata row under the filename:
- Source badge
- Audio duration formatted as `mm:ss`
- Created timestamp (absolute + relative)
- Processing time (if completed)
- Model used (from transcription.model_used if available)
- Retry count (if > 0): "Retried 2 times"

---

### Error state: Failed Job

When `job.status === 'failed' | 'dead'`:
```tsx
<Alert variant="destructive">
  <AlertTitle>Job Failed</AlertTitle>
  <AlertDescription>
    {job.error_message}
    <br />
    <Button onClick={() => retryJob(job.id)}>Retry Now</Button>
  </AlertDescription>
</Alert>
```

---

## Constraints
- `useJob` must auto-poll when status is `processing` — see Prompt 15 for polling logic
- Segment speaker colour mapping must be stable across re-renders — derive from `SPEAKER_NN` index, not array index
- Sentiment bars must animate on initial render (CSS transition, not JS animation)
- Copy to clipboard must use `navigator.clipboard.writeText` with fallback for non-HTTPS
- Timestamps in segments tab: format `start_time` and `end_time` as `m:ss` (e.g. `1:04`) not decimal seconds
- All tabs preserve scroll position independently (use tab key in URL or per-tab `ref` scroll restoration)
