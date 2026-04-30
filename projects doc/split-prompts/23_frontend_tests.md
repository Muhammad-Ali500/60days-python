# Prompt 23 — Frontend Tests (Vitest + React Testing Library)

## Goal
Write frontend unit and component tests using Vitest and React Testing Library. Cover API client, utility functions, hooks, and key UI components.

## Setup

### `package.json` — add dev dependencies
```json
{
  "devDependencies": {
    "vitest": "^2.0",
    "@vitejs/plugin-react": "^4.0",
    "@testing-library/react": "^16.0",
    "@testing-library/user-event": "^14.0",
    "@testing-library/jest-dom": "^6.0",
    "msw": "^2.0",
    "jsdom": "^25.0"
  }
}
```

### `vitest.config.ts`
```typescript
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { resolve } from "path";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
  },
  resolve: {
    alias: { "@": resolve(__dirname, "src") },
  },
});
```

### `src/test/setup.ts`
```typescript
import "@testing-library/jest-dom";
import { server } from "./mocks/server";

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
```

---

### `src/test/mocks/server.ts` — MSW handlers

```typescript
import { setupServer } from "msw/node";
import { http, HttpResponse } from "msw";

const API_BASE = "http://localhost:8000/api/v1";

export const handlers = [
  // Jobs list
  http.get(`${API_BASE}/jobs`, () =>
    HttpResponse.json({
      items: mockJobs,
      total: mockJobs.length,
      page: 1,
      limit: 20,
      pages: 1,
    })
  ),

  // Job detail
  http.get(`${API_BASE}/jobs/:id`, ({ params }) =>
    HttpResponse.json(mockJobDetail(params.id as string))
  ),

  // Delete job
  http.delete(`${API_BASE}/jobs/:id`, () => new HttpResponse(null, { status: 204 })),

  // Retry job
  http.post(`${API_BASE}/jobs/:id/retry`, ({ params }) =>
    HttpResponse.json({ ...mockJobSummary, id: params.id, status: "pending" })
  ),

  // Queue stats
  http.get(`${API_BASE}/queue/stats`, () =>
    HttpResponse.json(mockQueueStats)
  ),

  // Health
  http.get(`${API_BASE}/health`, () =>
    HttpResponse.json({ status: "ok", postgres: "ok", redis: "ok", minio: "ok", uptime_seconds: 300 })
  ),

  // Infer — transcribe
  http.post(`${API_BASE}/infer/transcribe`, () =>
    HttpResponse.json(mockTranscribeResponse)
  ),
];

export const server = setupServer(...handlers);
```

---

### `src/test/mocks/fixtures.ts`

Define all mock data:

```typescript
export const mockJobSummary = {
  id: "550e8400-e29b-41d4-a716-446655440000",
  source: "minio",
  status: "success",
  original_filename: "recording.mp3",
  file_size_bytes: 1024000,
  audio_duration_seconds: 142.3,
  task_types: ["transcription", "segmentation", "sentiment"],
  retry_count: 0,
  error_message: null,
  created_at: "2026-04-30T10:00:00Z",
  started_at: "2026-04-30T10:00:05Z",
  completed_at: "2026-04-30T10:00:17Z",
};

export const mockJobs = [mockJobSummary, ...];

export const mockJobDetail = (id: string) => ({
  ...mockJobSummary,
  id,
  transcription: {
    id: "...",
    language: "en",
    full_text: "Hello this is a test transcription.",
    word_count: 7,
    model_used: "faster-whisper-large-v3",
    words: [...],
    created_at: "...",
  },
  segments: [
    { id: "...", speaker_label: "SPEAKER_00", start_time: 0.0, end_time: 3.5, text: "Hello this is", segment_index: 0, is_overlap: false, sentiment: { label: "positive", score: 0.92, ... } },
  ],
  sentiment_summary: { label: "positive", score: 0.92, positive_pct: 75, negative_pct: 10, neutral_pct: 15 },
});
```

---

### `src/test/lib/utils.test.ts`

```typescript
import { formatDuration, formatProcessingTime, formatSpeakerLabel, speakerColour } from "@/lib/utils";

describe("formatDuration", () => {
  it("formats seconds as mm:ss", () => expect(formatDuration(90)).toBe("1:30"));
  it("formats over an hour", () => expect(formatDuration(3661)).toBe("1:01:01"));
  it("returns — for null", () => expect(formatDuration(null)).toBe("—"));
  it("returns 0:00 for zero", () => expect(formatDuration(0)).toBe("0:00"));
});

describe("formatProcessingTime", () => {
  it("formats short time as seconds", () => expect(formatProcessingTime(4.2)).toBe("4.2s"));
  it("formats over a minute", () => expect(formatProcessingTime(92)).toBe("1m 32s"));
});

describe("formatSpeakerLabel", () => {
  it("converts SPEAKER_00 to Speaker 1", () => expect(formatSpeakerLabel("SPEAKER_00")).toBe("Speaker 1"));
  it("converts SPEAKER_02 to Speaker 3", () => expect(formatSpeakerLabel("SPEAKER_02")).toBe("Speaker 3"));
  it("passes through unknown labels", () => expect(formatSpeakerLabel("Alice")).toBe("Alice"));
});
```

---

### `src/test/hooks/useDebounce.test.ts`

```typescript
import { renderHook, act } from "@testing-library/react";
import { useDebounce } from "@/hooks/useDebounce";

it("returns initial value immediately", () => {
  const { result } = renderHook(() => useDebounce("hello", 300));
  expect(result.current).toBe("hello");
});

it("debounces value change", async () => {
  vi.useFakeTimers();
  const { result, rerender } = renderHook(({ value }) => useDebounce(value, 300), {
    initialProps: { value: "hello" },
  });
  rerender({ value: "world" });
  expect(result.current).toBe("hello");   // not updated yet
  act(() => vi.advanceTimersByTime(300));
  expect(result.current).toBe("world");   // updated after delay
  vi.useRealTimers();
});
```

---

### `src/test/components/StatusBadge.test.tsx`

```typescript
import { render, screen } from "@testing-library/react";
import { StatusBadge } from "@/components/ui/StatusBadge";

it("renders correct label for each status", () => {
  const statuses = ["pending", "processing", "success", "failed", "dead"] as const;
  statuses.forEach(status => {
    const { unmount } = render(<StatusBadge status={status} />);
    expect(screen.getByText(/.+/)).toBeTruthy();
    unmount();
  });
});

it("renders spinning icon for processing", () => {
  render(<StatusBadge status="processing" />);
  expect(document.querySelector(".animate-spin")).toBeTruthy();
});
```

---

### `src/test/components/JobsTable.test.tsx`

```typescript
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClientProvider } from "@tanstack/react-query";
import { JobsTable } from "@/components/dashboard/JobsTable";

const wrapper = ({ children }) => (
  <QueryClientProvider client={new QueryClient()}>{children}</QueryClientProvider>
);

it("renders job rows", () => {
  render(<JobsTable jobs={mockJobs} />, { wrapper });
  expect(screen.getByText("recording.mp3")).toBeInTheDocument();
});

it("shows empty state when no jobs", () => {
  render(<JobsTable jobs={[]} />, { wrapper });
  expect(screen.getByText(/no jobs yet/i)).toBeInTheDocument();
});

it("calls onDelete when delete menu item clicked", async () => {
  const onDelete = vi.fn();
  render(<JobsTable jobs={mockJobs} onDelete={onDelete} />, { wrapper });
  await userEvent.click(screen.getAllByRole("button", { name: /more/i })[0]);
  await userEvent.click(screen.getByText(/delete/i));
  // Confirm dialog appears
  await userEvent.click(screen.getByRole("button", { name: /delete/i }));
  expect(onDelete).toHaveBeenCalledWith(mockJobSummary.id);
});
```

---

### `src/test/hooks/useJobs.test.ts`

```typescript
// Uses MSW to mock /jobs endpoint
it("fetches and returns job list", async () => {
  const { result } = renderHook(() => useJobs(), { wrapper: queryWrapper });
  await waitFor(() => expect(result.current.isSuccess).toBe(true));
  expect(result.current.data?.items).toHaveLength(mockJobs.length);
});

it("auto-refetches every 5 seconds", async () => {
  vi.useFakeTimers();
  const fetchSpy = vi.spyOn(global, "fetch");
  renderHook(() => useJobs(), { wrapper: queryWrapper });
  await act(() => vi.advanceTimersByTime(5000));
  expect(fetchSpy).toHaveBeenCalledTimes(2);  // initial + 1 refetch
  vi.useRealTimers();
});
```

---

## `package.json` test scripts

```json
{
  "scripts": {
    "test":         "vitest run",
    "test:watch":   "vitest",
    "test:coverage": "vitest run --coverage"
  }
}
```

---

## Constraints
- MSW intercepts all fetch calls — `apiFetch` in `api.ts` uses native `fetch`, which MSW patches
- All component tests must use `{ wrapper }` with `QueryClientProvider` when testing components that use TanStack Query hooks
- `vi.useFakeTimers()` must always be paired with `vi.useRealTimers()` in cleanup
- Do not snapshot test — write assertion-based tests
- Coverage target: 80% for `src/lib/` and `src/hooks/` — not required for UI components
