# Prompt 16 — Dashboard Page (Jobs Overview)

## Goal
Build the main dashboard page at `/` that shows job statistics, a filterable/searchable jobs table with status badges, and quick action buttons. Data auto-refreshes every 5 seconds.

## File to create: `src/app/page.tsx` and supporting components

---

### `src/app/page.tsx`

Server component shell — renders the client dashboard component:

```tsx
import { DashboardClient } from "@/components/dashboard/DashboardClient";

export default function DashboardPage() {
  return <DashboardClient />;
}

export const metadata = { title: "Dashboard — Audio Intelligence Platform" };
```

---

### `src/components/dashboard/DashboardClient.tsx`

`"use client"` component. Root of the dashboard UI.

Layout:
```
┌─ Page Header ──────────────────────────────────────────────┐
│  "Dashboard"                          [Refresh] [Poll MinIO]│
└────────────────────────────────────────────────────────────┘
┌─ Stats Row ─────────────────────────────────────────────────┐
│  [Total Jobs] [Pending] [Processing] [Success] [Failed]      │
└────────────────────────────────────────────────────────────┘
┌─ Filter Bar ────────────────────────────────────────────────┐
│  [Status ▼] [Source ▼] [🔍 Search filename...] [Date range] │
└────────────────────────────────────────────────────────────┘
┌─ Jobs Table ────────────────────────────────────────────────┐
│  Filename | Source | Status | Duration | Created | Actions  │
│  ...                                                        │
└────────────────────────────────────────────────────────────┘
┌─ Pagination ────────────────────────────────────────────────┐
│  Showing 1–20 of 142              [< Prev] [1][2][3] [Next >]│
└────────────────────────────────────────────────────────────┘
```

State managed with `useState`:
- `page`, `limit` (20)
- `statusFilter`, `sourceFilter`, `search`, `dateFrom`, `dateTo`

Data from `useJobs({ status, source, search, date_from, date_to, page, limit })`.

---

### `src/components/dashboard/StatsRow.tsx`

Five cards in a responsive grid (2 cols mobile, 5 cols desktop):

```tsx
<StatsCard label="Total Jobs"   value={data.total}    icon={<Database />}  color="slate"  />
<StatsCard label="Pending"      value={pending}       icon={<Clock />}     color="yellow" />
<StatsCard label="Processing"   value={processing}    icon={<Loader2 />}   color="blue"   spin={processing > 0} />
<StatsCard label="Completed"    value={success}       icon={<CheckCircle />} color="green" />
<StatsCard label="Failed"       value={failed + dead} icon={<XCircle />}   color="red"    />
```

Each card shows the count in large bold text. "Processing" card has a spinning loader icon if count > 0.

---

### `src/components/dashboard/JobsTable.tsx`

Table using shadcn `Table` components.

**Columns:**

| Column | Content |
|--------|---------|
| Filename | Truncated to 40 chars with tooltip showing full name; link to `/jobs/{id}` |
| Source | Badge: `minio` (blue), `realtime` (purple), `direct` (orange) |
| Tasks | Small pills for each task type: T (transcription), S (segmentation), A (sentiment) |
| Status | `<StatusBadge status={job.status} />` |
| Duration | Audio duration in `mm:ss` format, or `—` if null |
| Processing | Time taken (`completed_at - started_at`) in human-readable form (e.g. "4.2s", "1m 32s") |
| Created | Relative time ("2 minutes ago") using a `useRelativeTime` hook |
| Actions | Three-dot menu: View, Retry (if failed/dead), Delete |

**Loading state:** Show 5 skeleton rows while data is loading.
**Empty state:** Centered illustration + "No jobs yet" text + link to Real-time page.
**Error state:** Alert with error message and retry button.

---

### `src/components/dashboard/FilterBar.tsx`

```tsx
// Status select: All | Pending | Processing | Success | Failed | Dead
// Source select: All | MinIO | Real-time | Direct
// Search input: debounced 300ms before triggering query
// Date range: two date inputs (from / to)
// Clear filters button (only visible when any filter is active)
```

Use controlled inputs — all state lifted to `DashboardClient`.

---

### `src/components/ui/StatusBadge.tsx`

```tsx
const statusConfig: Record<JobStatus, { label: string; variant: string; icon: ReactNode }> = {
  pending:    { label: "Pending",    variant: "outline",     icon: <Clock size={12} /> },
  processing: { label: "Processing", variant: "secondary",   icon: <Loader2 size={12} className="animate-spin" /> },
  success:    { label: "Success",    variant: "default",     icon: <CheckCircle size={12} /> },
  failed:     { label: "Failed",     variant: "destructive", icon: <XCircle size={12} /> },
  dead:       { label: "Dead",       variant: "destructive", icon: <Skull size={12} /> },
};
```

---

### `src/components/dashboard/JobActionsMenu.tsx`

Dropdown menu per row:

```tsx
<DropdownMenu>
  <DropdownMenuTrigger asChild>
    <Button variant="ghost" size="icon"><MoreHorizontal /></Button>
  </DropdownMenuTrigger>
  <DropdownMenuContent>
    <DropdownMenuItem onClick={() => router.push(`/jobs/${job.id}`)}>
      <Eye /> View Details
    </DropdownMenuItem>
    {canRetry && (
      <DropdownMenuItem onClick={() => retryJob(job.id)}>
        <RefreshCw /> Retry
      </DropdownMenuItem>
    )}
    <DropdownMenuSeparator />
    <DropdownMenuItem className="text-destructive" onClick={() => setDeleteTarget(job)}>
      <Trash2 /> Delete
    </DropdownMenuItem>
  </DropdownMenuContent>
</DropdownMenu>
```

---

### `src/components/dashboard/DeleteConfirmDialog.tsx`

```tsx
// shadcn Dialog
// Title: "Delete Job"
// Body: "Are you sure you want to delete {filename}? This action cannot be undone."
// Buttons: [Cancel] [Delete] (Delete is destructive red variant)
// On confirm: call deleteJob(id), close dialog, show toast "Job deleted"
```

---

### `src/hooks/useRelativeTime.ts`

```typescript
// Returns "just now", "2 minutes ago", "3 hours ago", etc.
// Updates every 60 seconds via setInterval
// Input: ISO timestamp string or Date
```

---

## Constraints
- Table must use `react-key` on `job.id`, never array index
- "Poll MinIO" button triggers `queueApi.minioTriggerPoll()` and shows a toast on success
- Search input debounce: 300ms (use `useDebounce` hook or `setTimeout` in effect)
- Pagination must reset to page 1 when any filter changes
- All dates displayed in local timezone (use `Intl.DateTimeFormat`)
- Skeleton rows must match the actual row height to prevent layout shift
