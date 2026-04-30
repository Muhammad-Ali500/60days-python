# Prompt 19 — Queue Monitor Page

## Goal
Build the `/queue` page that shows live Celery worker stats, MinIO bucket status, and queue management controls. Embeds or links to Flower dashboard.

## Files to create

---

### `src/app/queue/page.tsx`

```tsx
import { QueueClient } from "@/components/queue/QueueClient";
export default function QueuePage() { return <QueueClient />; }
export const metadata = { title: "Queue Monitor — AIP" };
```

---

### `src/components/queue/QueueClient.tsx`

`"use client"`. Uses `useQueueStats()` (polls every 5s) and `useMinioStatus()`.

Layout:
```
┌─ Page Header ───────────────────────────────────────────────┐
│  Queue Monitor                    [Poll MinIO Now] [Purge ▼]│
└────────────────────────────────────────────────────────────┘
┌─ Workers & Tasks ──────────────────────────────────────────┐
│  [Active Workers: 3]  [Active Tasks: 2]                     │
│  [Reserved: 5]        [Scheduled: 0]   [Failed: 1]         │
└────────────────────────────────────────────────────────────┘
┌─ Queue Throughput Chart ────────────────────────────────────┐
│  (Recharts line chart: jobs processed per minute, last 30m) │
└────────────────────────────────────────────────────────────┘
┌─ MinIO Buckets ─────────────────────────────────────────────┐
│  Bucket Name       | Last Polled     | Last Object          │
│  audio-uploads     | 2 minutes ago   | calls/rec_001.mp3   │
└────────────────────────────────────────────────────────────┘
┌─ Flower Link ───────────────────────────────────────────────┐
│  ℹ Flower is running at http://localhost:5555 (internal)    │
└────────────────────────────────────────────────────────────┘
```

---

### `src/components/queue/WorkerStatsGrid.tsx`

Six stat cards in a 3×2 grid:

```tsx
const stats = [
  { label: "Active Workers",  value: data.active_workers,  icon: <Server />,   color: data.active_workers > 0 ? "green" : "red" },
  { label: "Active Tasks",    value: data.active_tasks,    icon: <Play />,     color: "blue" },
  { label: "Reserved Tasks",  value: data.reserved_tasks,  icon: <Layers />,   color: "yellow" },
  { label: "Scheduled Tasks", value: data.scheduled_tasks, icon: <CalendarClock />, color: "slate" },
  { label: "Failed Tasks",    value: data.failed_tasks,    icon: <XCircle />,  color: data.failed_tasks > 0 ? "red" : "slate" },
  { label: "Total Processed", value: data.total_processed, icon: <CheckCircle2 />, color: "green" },
];
```

Each card has:
- Large number (animated count-up on load using a simple `useCountUp` hook)
- Label
- Icon
- Coloured left border

---

### `src/components/queue/ThroughputChart.tsx`

Recharts `<LineChart>` showing job completion rate.

Data source: poll `GET /jobs?status=success&date_from={30_minutes_ago}` and bucket results by minute.

```tsx
// Build data points: last 30 minutes, 1-minute buckets
// x-axis: time labels ("14:30", "14:31", ...)
// y-axis: jobs completed in that minute
// Tooltip: "3 jobs at 14:32"
// Smooth line, no dots, fill under line

const data = buildMinuteBuckets(successfulJobs, 30);  // helper: groups jobs by minute
```

Chart dimensions: full width, 180px height.

---

### `src/components/queue/MinioStatus.tsx`

Table of monitored MinIO buckets from `GET /minio/buckets`.

Columns:
- Bucket Name (monospace, with copy button)
- Last Polled (relative time)
- Last Object Key (truncated, monospace)
- Status dot: green if polled within last 2× poll interval, yellow if stale, red if never polled

"Poll MinIO Now" button in the table header:
- Calls `queueApi.minioTriggerPoll()`
- Shows loading spinner while pending
- Shows success toast "MinIO poll triggered (task: {task_id})"
- Disables for 5 seconds after click (prevent spam)

---

### `src/components/queue/PurgeQueueButton.tsx`

```tsx
// Dropdown button: [Purge ▼] with two items:
// - "Purge Pending Tasks" — clears Celery queue
// - (future: "Retry All Failed")

// On click "Purge Pending Tasks":
// Open confirmation dialog:
//   Title: "Purge Queue"
//   Body: "This will cancel all {N} pending tasks and mark their jobs as failed. This cannot be undone."
//   Buttons: [Cancel] [Purge Queue] (destructive)
//
// On confirm:
//   Call queueApi.purge()
//   Show toast: "Queue purged. {purged_tasks} tasks cancelled, {updated_jobs} jobs updated."
//   Invalidate ["jobs"] and ["queue-stats"] queries
```

---

### `src/components/queue/FlowerInfo.tsx`

Informational card:

```tsx
<Card>
  <CardHeader>
    <CardTitle className="flex items-center gap-2">
      <Flower /> Flower Dashboard
    </CardTitle>
  </CardHeader>
  <CardContent>
    <p className="text-muted-foreground text-sm">
      Flower provides a detailed real-time view of your Celery workers and tasks.
      It is accessible only from the server — not exposed to the public internet.
    </p>
    <code className="block mt-2 text-sm bg-muted p-2 rounded">
      http://localhost:5555
    </code>
    <p className="text-xs text-muted-foreground mt-1">
      Access via SSH tunnel or from the server directly.
    </p>
  </CardContent>
</Card>
```

---

### `src/hooks/useMinioStatus.ts`

```typescript
export function useMinioStatus() {
  return useQuery({
    queryKey: ["minio-buckets"],
    queryFn: () => queueApi.minioBuckets(),
    refetchInterval: 30_000,   // every 30s (matches poll interval)
  });
}
```

---

## Constraints
- Throughput chart data must be derived from the existing `/jobs` endpoint — no new backend endpoint needed
- `WorkerStatsGrid` must show "0 workers" with a red indicator when no workers respond — not an error state
- Purge dialog must show the current pending task count in its body text (fetch from stats before showing)
- All mutation buttons (Poll, Purge) must be disabled while their requests are in-flight
- `useCountUp` hook: animate from 0 to target value over 600ms on first render only — not on every poll update
