# Prompt 21 — Jobs List Page (`/jobs`)

## Goal
Build a dedicated `/jobs` page with advanced filtering, bulk actions, and direct links to exports. Distinct from the dashboard — this is the full data management view.

## Files to create

---

### `src/app/jobs/page.tsx`

```tsx
import { JobsListClient } from "@/components/jobs/JobsListClient";
export default function JobsPage() { return <JobsListClient />; }
export const metadata = { title: "All Jobs — AIP" };
```

---

### `src/components/jobs/JobsListClient.tsx`

`"use client"`. Similar to dashboard table but with:
- More columns
- Bulk selection and bulk actions
- Inline expandable row showing mini transcript preview
- Persistent filter state via URL search params (`useSearchParams` + `useRouter`)

#### URL-synced filters

```typescript
// Read from URL on mount, write to URL on change
// ?status=success&source=minio&search=recording&page=2
const searchParams = useSearchParams();
const router = useRouter();

function updateFilter(key: string, value: string | null) {
  const params = new URLSearchParams(searchParams.toString());
  if (value) params.set(key, value);
  else params.delete(key);
  params.set("page", "1");   // reset page on filter change
  router.replace(`/jobs?${params.toString()}`);
}
```

---

### Extended table columns (compared to dashboard)

| Column | Content |
|--------|---------|
| ☐ | Checkbox for bulk selection |
| Filename | Truncated, link to detail |
| Source | Badge |
| Tasks | Pills (T/S/A) |
| Status | StatusBadge |
| Audio | Duration (mm:ss) |
| Processing | Time taken |
| Retries | Count, red if > 0 |
| Created | Absolute timestamp |
| Actions | View, Export (JSON/TXT/SRT), Retry, Delete |

---

### `src/components/jobs/BulkActionsBar.tsx`

Appears when 1+ rows are selected:

```tsx
// Position: sticky bottom of the table area
// Shows: "{N} jobs selected" + action buttons
// Actions:
// - [Delete Selected] → confirm dialog → delete all selected
// - [Retry Selected]  → only enabled if all selected are failed/dead
// - [Deselect All]

<div className="fixed bottom-6 left-1/2 -translate-x-1/2 bg-background border rounded-lg shadow-lg px-4 py-3 flex items-center gap-4">
  <span>{selectedCount} selected</span>
  <Button variant="outline" onClick={deselectAll}>Deselect</Button>
  <Button variant="outline" onClick={retrySelected} disabled={!allRetryable}>Retry Selected</Button>
  <Button variant="destructive" onClick={() => setConfirmBulkDelete(true)}>Delete Selected</Button>
</div>
```

---

### `src/components/jobs/ExpandableRow.tsx`

Clicking anywhere on a row (except action buttons) expands it inline:

```tsx
// Expanded content:
// If transcription exists:
//   Show first 200 chars of full_text in a muted block
// If no transcription:
//   Show "No transcript available"
// Expanded row has a subtle background highlight
// Collapse on second click
```

---

### Inline Export Dropdown per row

Each row's action menu includes:

```tsx
<DropdownMenuSub>
  <DropdownMenuSubTrigger>
    <Download /> Export
  </DropdownMenuSubTrigger>
  <DropdownMenuPortal>
    <DropdownMenuSubContent>
      <DropdownMenuItem onClick={() => window.open(jobsApi.exportUrl(id, "json"))}>
        JSON (full data)
      </DropdownMenuItem>
      <DropdownMenuItem onClick={() => window.open(jobsApi.exportUrl(id, "txt"))}
        disabled={!job.transcription}>
        Plain Text
      </DropdownMenuItem>
      <DropdownMenuItem onClick={() => window.open(jobsApi.exportUrl(id, "srt"))}
        disabled={!job.segments?.length}>
        Subtitles (SRT)
      </DropdownMenuItem>
    </DropdownMenuSubContent>
  </DropdownMenuPortal>
</DropdownMenuSub>
```

---

### Bulk delete flow

```typescript
async function handleBulkDelete() {
  const ids = [...selectedIds];
  let deleted = 0, errors = 0;

  for (const id of ids) {
    try {
      await jobsApi.delete(id);
      deleted++;
    } catch {
      errors++;
    }
  }

  queryClient.invalidateQueries({ queryKey: ["jobs"] });
  setSelectedIds(new Set());

  if (errors === 0) {
    toastSuccess(`Deleted ${deleted} jobs`);
  } else {
    toastError(`Deleted ${deleted} jobs, ${errors} failed`);
  }
}
```

---

## Constraints
- URL filter sync: use `replace` not `push` to avoid browser history spam on filter changes
- Bulk selection state: use `Set<string>` — O(1) lookup on every checkbox render
- Select-all: selects only the current page (not all matching jobs across pages)
- Expandable rows: max one expanded row at a time — opening a second collapses the first
- Export items disabled correctly: "Plain Text" only if transcription exists, "SRT" only if segments exist
- Bulk retry: disabled if any selected job is NOT in failed/dead status (mixed selection edge case)
