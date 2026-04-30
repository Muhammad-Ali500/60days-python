# Prompt 18 — Real-time Processor Page

## Goal
Build the `/realtime` page where users upload an audio file, select processing tasks, and watch transcription/segmentation/sentiment appear live via WebSocket streaming.

## Files to create

---

### `src/app/realtime/page.tsx`

```tsx
import { RealtimeClient } from "@/components/realtime/RealtimeClient";
export default function RealtimePage() { return <RealtimeClient />; }
export const metadata = { title: "Real-time Processing — AIP" };
```

---

### `src/components/realtime/RealtimeClient.tsx`

`"use client"` root component. Three phases: **Idle → Processing → Done**.

```
Phase 1 — IDLE:
┌─────────────────────────────────────────────────────────┐
│  [Drag & drop audio file here, or click to browse]      │
│  Supported: mp3, wav, flac, ogg, m4a, webm  Max: 200MB  │
└─────────────────────────────────────────────────────────┘
┌─ Task selection ────────────────────────────────────────┐
│  ☑ Transcription    ☑ Segmentation    ☑ Sentiment        │
└─────────────────────────────────────────────────────────┘
[Process Now] (disabled until file selected)

Phase 2 — PROCESSING:
┌─ Progress ──────────────────────────────────────────────┐
│  Normalising audio...  ████░░░░░░░░░░  10%              │
└─────────────────────────────────────────────────────────┘
┌─ Live Transcript ───────────────────────────────────────┐
│  Hello this is a live transcription as words arrive...  │
└─────────────────────────────────────────────────────────┘
┌─ Segments ──────────────────────────────────────────────┐
│  (populates as segments are detected)                    │
└─────────────────────────────────────────────────────────┘

Phase 3 — DONE:
"Processing complete!"
[View Full Results →] (links to /jobs/{job_id})
```

---

### `src/components/realtime/DropZone.tsx`

File upload drop zone using `react-dropzone`.

```tsx
const { getRootProps, getInputProps, isDragActive, fileRejections } = useDropzone({
  accept: {
    "audio/mpeg": [".mp3"],
    "audio/wav":  [".wav"],
    "audio/flac": [".flac"],
    "audio/ogg":  [".ogg"],
    "audio/mp4":  [".m4a"],
    "audio/webm": [".webm"],
  },
  maxFiles: 1,
  maxSize: 200 * 1024 * 1024,  // 200 MB
  onDropAccepted: onFileSelected,
  onDropRejected: (rejections) => setError(rejections[0].errors[0].message),
});
```

Visual states:
- Default: dashed border, upload icon, instruction text
- Drag over: solid blue border, highlighted background, "Drop it!"
- File selected: show file name, size, duration estimate, green checkmark, X button to clear
- Error: red border, error message below

---

### `src/components/realtime/TaskSelector.tsx`

```tsx
const tasks = [
  { id: "transcription", label: "Transcription",  icon: <FileText />,    description: "Convert speech to text" },
  { id: "segmentation",  label: "Segmentation",   icon: <Users />,       description: "Identify speakers" },
  { id: "sentiment",     label: "Sentiment",      icon: <BarChart2 />,   description: "Analyse emotional tone" },
];

// Three toggle cards — clicking toggles selection
// Visual: selected = filled background with checkmark; unselected = outline
// Constraint: if segmentation or sentiment selected, transcription must also be selected
// → If user deselects transcription: also deselect segmentation and sentiment, show tooltip "Required"
```

---

### `src/components/realtime/ProgressBar.tsx`

```tsx
// Shows current step name and percentage
// <div className="w-full bg-muted rounded-full h-2">
//   <div className="bg-primary h-2 rounded-full transition-all duration-500" style={{ width: `${percent}%` }} />
// </div>
// Step label below: "Transcription — 42%"
// Animated: CSS transition-all duration-500ms on width
```

---

### `src/components/realtime/LiveTranscript.tsx`

```tsx
// Append words as they arrive from WebSocket
// Each word is a <span> that fades in with a brief animation
// Auto-scroll to bottom as words arrive
// Word-level: show individual words animating in
// After completion: show clean full text

// Implementation:
// - Maintain `words: WordToken[]` in state
// - Each WS "token" event appends to words
// - Render: words.map(w => <span key={w.index} className="animate-fade-in">{w.text} </span>)
// - useEffect: scroll container to bottom on every words update

interface WordToken {
  index: number;
  text: string;
  start: number;
  end: number;
}
```

---

### `src/components/realtime/LiveSegments.tsx`

```tsx
// Renders segments as they arrive from WebSocket
// Each "segment" event adds a card

// SegmentLiveCard:
// ┌──────────────────────────────────────────────────────┐
// │ ● Speaker 1   0:00 → 0:05                           │
// │ "Hello how are you?"           [positive 94%]        │
// └──────────────────────────────────────────────────────┘
// Sentiment badge appended when "sentiment" WS event for this segment arrives
// Animate in with slide-up + fade
```

---

### `src/hooks/useWebSocket.ts`

```typescript
interface UseWebSocketOptions {
  onToken:     (data: WSToken) => void;
  onSegment:   (data: WSSegment) => void;
  onSentiment: (data: WSSentiment) => void;
  onProgress:  (step: string, percent: number) => void;
  onDone:      (jobId: string) => void;
  onError:     (message: string) => void;
}

export function useWebSocket(jobId: string | null, options: UseWebSocketOptions) {
  // Connect to WS_BASE + /realtime/stream/{jobId}
  // Parse incoming JSON messages, dispatch to correct handler based on event type
  // Auto-reconnect on disconnect (max 3 attempts, 1s delay)
  // Cleanup: close WS on component unmount or jobId change
  // Return: { isConnected, disconnect }
}
```

---

### `src/stores/realtimeStore.ts`

Zustand store for real-time processing state:

```typescript
interface RealtimeState {
  phase: "idle" | "uploading" | "processing" | "done" | "error";
  file: File | null;
  taskTypes: string[];
  jobId: string | null;
  progress: { step: string; percent: number };
  words: WordToken[];
  segments: LiveSegment[];
  error: string | null;

  // Actions
  setFile: (file: File | null) => void;
  toggleTask: (task: string) => void;
  startProcessing: () => Promise<void>;  // calls realtimeApi.upload()
  appendWord: (word: WordToken) => void;
  appendSegment: (segment: LiveSegment) => void;
  updateSegmentSentiment: (segmentIndex: number, sentiment: SentimentData) => void;
  setProgress: (step: string, percent: number) => void;
  setDone: (jobId: string) => void;
  setError: (message: string) => void;
  reset: () => void;
}
```

---

## Constraints
- WebSocket connection must only be opened AFTER the upload response is received (not before)
- `LiveTranscript` must auto-scroll to bottom without jumping when user has scrolled up manually — use intersection observer to detect if user is at bottom
- File selection persists across task changes — only reset on explicit "X" button or after processing completes
- "Process Now" button must be disabled during upload AND processing phases
- If WebSocket fails to connect within 5 seconds: show error state with option to view results via polling (`/jobs/{id}`)
- `updateSegmentSentiment` matches by `segment.index`, not by array position
