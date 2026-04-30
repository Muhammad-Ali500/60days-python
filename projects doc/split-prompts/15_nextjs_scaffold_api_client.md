# Prompt 15 — Next.js 15 Scaffold, API Client & TanStack Query Setup

## Goal
Set up the Next.js 15 App Router project structure, configure Tailwind CSS 4 with shadcn/ui, build the typed API client, configure TanStack Query, and create the root layout with navigation.

## Files to create / edit

---

### `src/lib/api.ts`

Typed API client. All backend communication goes through this file.

```typescript
// Base config
const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";
const WS_BASE  = process.env.NEXT_PUBLIC_WS_URL  ?? "ws://localhost:8000/api/v1";

// Generic fetch wrapper
async function apiFetch<T>(
  path: string,
  options?: RequestInit & { params?: Record<string, string | number | boolean | undefined> }
): Promise<T> {
  // Build URL with query params
  // Add default headers: Content-Type: application/json (skip for multipart)
  // Throw ApiError on non-2xx responses (include status + parsed body)
  // Return parsed JSON
}

export class ApiError extends Error {
  constructor(public status: number, public body: unknown, message: string) { super(message); }
}

// ── Jobs ──────────────────────────────────────────────────────

export const jobsApi = {
  list: (params?: JobListParams) =>
    apiFetch<JobListResponse>("/jobs", { params }),

  get: (id: string) =>
    apiFetch<JobDetail>(`/jobs/${id}`),

  delete: (id: string) =>
    apiFetch<void>(`/jobs/${id}`, { method: "DELETE" }),

  retry: (id: string) =>
    apiFetch<JobSummary>(`/jobs/${id}/retry`, { method: "POST" }),

  exportUrl: (id: string, format: "json" | "txt" | "srt") =>
    `${API_BASE}/jobs/${id}/export?format=${format}`,
  // Returns URL string — browser navigates to it for file download
};

// ── Real-time ─────────────────────────────────────────────────

export const realtimeApi = {
  upload: (file: File, taskTypes: string[]) => {
    const form = new FormData();
    form.append("file", file);
    taskTypes.forEach(t => form.append("task_types", t));
    return apiFetch<RealtimeUploadResponse>("/realtime/upload", {
      method: "POST",
      body: form,
      // No Content-Type header — browser sets multipart boundary automatically
    });
  },
  wsUrl: (jobId: string) => `${WS_BASE}/realtime/stream/${jobId}`,
};

// ── Direct Inference ──────────────────────────────────────────

export const inferApi = {
  transcribe: (file: File, opts?: { save?: boolean; model?: string }) => {
    const form = new FormData();
    form.append("file", file);
    const params = { save: opts?.save, model: opts?.model };
    return apiFetch<TranscribeResponse>("/infer/transcribe", { method: "POST", body: form, params });
  },

  transcribeFromMinio: (bucket: string, objectKey: string, opts?: { save?: boolean }) => {
    const form = new FormData();
    form.append("minio_ref", JSON.stringify({ bucket, object_key: objectKey }));
    return apiFetch<TranscribeResponse>("/infer/transcribe", { method: "POST", body: form, params: opts });
  },

  segment: (file: File, opts?: { save?: boolean; numSpeakers?: number }) => {
    const form = new FormData();
    form.append("file", file);
    return apiFetch<SegmentResponse>("/infer/segment", {
      method: "POST", body: form,
      params: { save: opts?.save, num_speakers: opts?.numSpeakers },
    });
  },

  sentiment: (input: File | string, opts?: { save?: boolean; chunkBy?: "sentence" | "paragraph" | "full" }) => {
    const form = new FormData();
    if (typeof input === "string") {
      form.append("text", input);
    } else {
      form.append("file", input);
    }
    return apiFetch<SentimentResponse>("/infer/sentiment", {
      method: "POST", body: form,
      params: { save: opts?.save, chunk_by: opts?.chunkBy ?? "sentence" },
    });
  },

  pipeline: (file: File, taskTypes: string[], opts?: { save?: boolean }) => {
    const form = new FormData();
    form.append("file", file);
    return apiFetch<PipelineResponse>("/infer/pipeline", {
      method: "POST", body: form,
      params: { save: opts?.save, task_types: taskTypes.join(",") },
    });
  },
};

// ── Queue ─────────────────────────────────────────────────────

export const queueApi = {
  stats: () => apiFetch<QueueStats>("/queue/stats"),
  purge: () => apiFetch<{ purged_tasks: number; updated_jobs: number }>("/queue/purge", { method: "POST" }),
  minioTriggerPoll: () => apiFetch<{ task_id: string }>("/minio/poll", { method: "POST" }),
  minioBuckets: () => apiFetch<MinioBucketInfo[]>("/minio/buckets"),
};

// ── Health ────────────────────────────────────────────────────

export const healthApi = {
  check: () => apiFetch<HealthStatus>("/health"),
  models: () => apiFetch<ModelStatus>("/health/models"),
};

// Export WS_BASE for hooks
export { WS_BASE };
```

---

### `src/lib/types.ts`

TypeScript type definitions mirroring the backend Pydantic schemas. Define all types used by `api.ts`.

```typescript
export type JobStatus = "pending" | "processing" | "success" | "failed" | "dead";
export type JobSource = "minio" | "realtime" | "direct";

export interface JobSummary { /* ... all fields from spec schema */ }
export interface JobDetail extends JobSummary { /* ... */ }
export interface TranscribeResponse { /* ... */ }
export interface SegmentResponse { /* ... */ }
export interface SentimentResponse { /* ... */ }
export interface PipelineResponse { /* ... */ }
export interface QueueStats { /* ... */ }
export interface HealthStatus { /* ... */ }
// etc. — mirror every Pydantic schema from Prompt 04
```

---

### `src/lib/query-client.ts`

```typescript
import { QueryClient } from "@tanstack/react-query";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 10_000,        // 10 seconds
      retry: 2,
      refetchOnWindowFocus: false,
    },
  },
});
```

---

### `src/app/providers.tsx`

```tsx
"use client";
import { QueryClientProvider } from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import { queryClient } from "@/lib/query-client";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>
      {children}
      {process.env.NODE_ENV === "development" && <ReactQueryDevtools />}
    </QueryClientProvider>
  );
}
```

---

### `src/app/layout.tsx`

Root layout with:
- `<html lang="en">`
- Inter font via `next/font`
- `<Providers>` wrapping children
- `<Sidebar>` component (see below)
- Main content area with `<main>` tag

---

### `src/components/layout/Sidebar.tsx`

Left sidebar with navigation links:

| Icon | Label | Path |
|------|-------|------|
| LayoutDashboard | Dashboard | `/` |
| Zap | Real-time | `/realtime` |
| List | Jobs | `/jobs` |
| Activity | Queue | `/queue` |

- Highlight active link using `usePathname()`
- Show system health indicator dot (green/red) — fetched from `/health`
- Refresh health every 30 seconds

---

### `src/hooks/useJobs.ts`

```typescript
// useJobs — paginated job list with auto-refresh
export function useJobs(params?: JobListParams) {
  return useQuery({
    queryKey: ["jobs", params],
    queryFn: () => jobsApi.list(params),
    refetchInterval: 5000,    // poll every 5 seconds
  });
}

// useJob — single job detail
export function useJob(id: string) {
  return useQuery({
    queryKey: ["job", id],
    queryFn: () => jobsApi.get(id),
    refetchInterval: (data) => data?.status === "processing" ? 2000 : false,
  });
}

// useRetryJob — mutation
export function useRetryJob() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => jobsApi.retry(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["jobs"] }),
  });
}

// useDeleteJob — mutation
export function useDeleteJob() { ... }

// useQueueStats
export function useQueueStats() {
  return useQuery({
    queryKey: ["queue-stats"],
    queryFn: () => queueApi.stats(),
    refetchInterval: 5000,
  });
}
```

---

## shadcn/ui setup

Run this command to initialise shadcn (put instructions in a README note — don't actually run it during build):
```bash
npx shadcn@latest init
```
Then add components:
```bash
npx shadcn@latest add button badge card table tabs dialog alert separator skeleton
```

Create `src/components/ui/` — shadcn generates these files automatically.

---

## Constraints
- `apiFetch` must NOT include `Content-Type: application/json` when body is `FormData` — let the browser set multipart headers
- All API functions must be typed — no `any` in `api.ts` or `types.ts`
- `useJobs` refetch interval must be 5 seconds (matches spec)
- `useJob` refetch interval must be 2 seconds when status is `processing`, disabled otherwise (no unnecessary polling)
- The Providers component must be `"use client"` — TanStack Query requires client context
- Sidebar health dot should use the `/health` endpoint, NOT ping the DB directly
