# Prompt 20 — Zustand Stores, Global Hooks & Toast System

## Goal
Build all remaining shared state management, global utility hooks, and the toast notification system used across all pages.

## Files to create

---

### `src/stores/uiStore.ts`

Global UI state — sidebar, toasts, modals.

```typescript
import { create } from "zustand";

interface Toast {
  id: string;
  type: "success" | "error" | "info" | "warning";
  title: string;
  description?: string;
  duration?: number;    // ms, default 4000
}

interface UIState {
  sidebarCollapsed: boolean;
  toasts: Toast[];

  toggleSidebar: () => void;
  setSidebarCollapsed: (v: boolean) => void;

  toast: (opts: Omit<Toast, "id">) => void;
  dismissToast: (id: string) => void;

  // Convenience methods
  toastSuccess: (title: string, description?: string) => void;
  toastError:   (title: string, description?: string) => void;
  toastInfo:    (title: string, description?: string) => void;
}

export const useUIStore = create<UIState>((set, get) => ({
  sidebarCollapsed: false,
  toasts: [],

  toggleSidebar: () => set(s => ({ sidebarCollapsed: !s.sidebarCollapsed })),
  setSidebarCollapsed: (v) => set({ sidebarCollapsed: v }),

  toast: (opts) => {
    const id = crypto.randomUUID();
    set(s => ({ toasts: [...s.toasts, { ...opts, id }] }));
    setTimeout(() => get().dismissToast(id), opts.duration ?? 4000);
  },
  dismissToast: (id) => set(s => ({ toasts: s.toasts.filter(t => t.id !== id) })),

  toastSuccess: (title, description) => get().toast({ type: "success", title, description }),
  toastError:   (title, description) => get().toast({ type: "error",   title, description }),
  toastInfo:    (title, description) => get().toast({ type: "info",    title, description }),
}));
```

---

### `src/components/ui/ToastContainer.tsx`

Renders toasts from `useUIStore`. Lives in `app/layout.tsx` outside `<main>`.

```tsx
// Position: bottom-right, fixed
// Each toast slides in from the right, slides out when dismissed
// Stack up to 5 toasts; oldest dismissed first if limit exceeded
// Toast card:
// ┌──────────────────────────────────┐
// │ ✓  Job deleted successfully   ✕ │
// │    The job has been removed.     │
// └──────────────────────────────────┘
// Auto-dismiss timer shown as shrinking bottom border line
```

---

### `src/hooks/useCountUp.ts`

```typescript
// Animates a number from 0 to target over `duration` ms (default 600ms)
// Only fires once on mount (not on every value change)
// Uses requestAnimationFrame for smooth animation
export function useCountUp(target: number, duration = 600): number {
  const [current, setCurrent] = useState(0);
  // useEffect: requestAnimationFrame loop from 0 → target over `duration`
  return current;
}
```

---

### `src/hooks/useDebounce.ts`

```typescript
export function useDebounce<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}
```

---

### `src/hooks/useRelativeTime.ts`

```typescript
// Format a date as "just now", "2 minutes ago", "3 hours ago", "2 days ago"
// Refreshes every 60 seconds via setInterval
// Input: Date | string | null
// Output: string
export function useRelativeTime(date: Date | string | null): string {
  const [text, setText] = useState(() => formatRelative(date));
  useEffect(() => {
    const interval = setInterval(() => setText(formatRelative(date)), 60_000);
    return () => clearInterval(interval);
  }, [date]);
  return text;
}

function formatRelative(date: Date | string | null): string {
  if (!date) return "—";
  const seconds = Math.floor((Date.now() - new Date(date).getTime()) / 1000);
  if (seconds < 60)   return "just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)} minutes ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)} hours ago`;
  return `${Math.floor(seconds / 86400)} days ago`;
}
```

---

### `src/hooks/useHealthCheck.ts`

```typescript
// Polls /health every 30 seconds
// Returns { status: 'ok' | 'degraded' | 'error', services: HealthStatus }
export function useHealthCheck() {
  return useQuery({
    queryKey: ["health"],
    queryFn: () => healthApi.check(),
    refetchInterval: 30_000,
    retry: false,    // don't retry health checks
    select: (data) => ({
      ...data,
      // Compute overall: 'ok' if all services ok, 'degraded' if any error, 'error' if request failed
      overall: Object.values(data).every(v => v === "ok") ? "ok" : "degraded",
    }),
  });
}
```

---

### `src/hooks/useFileValidation.ts`

```typescript
const ALLOWED_EXTENSIONS = [".mp3", ".wav", ".flac", ".ogg", ".m4a", ".webm"];
const MAX_SIZE_BYTES = 200 * 1024 * 1024;

export function useFileValidation() {
  const validate = useCallback((file: File): string | null => {
    const ext = "." + file.name.split(".").pop()?.toLowerCase();
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      return `Unsupported format. Allowed: ${ALLOWED_EXTENSIONS.join(", ")}`;
    }
    if (file.size > MAX_SIZE_BYTES) {
      return `File too large. Maximum: 200 MB (file is ${formatBytes(file.size)})`;
    }
    return null;   // valid
  }, []);

  return { validate };
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
}
```

---

### `src/lib/utils.ts`

```typescript
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

// shadcn utility
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// Format seconds to mm:ss or hh:mm:ss
export function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null) return "—";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  return `${m}:${String(s).padStart(2, "0")}`;
}

// Format processing time: "4.2s", "1m 32s"
export function formatProcessingTime(seconds: number | null | undefined): string {
  if (seconds == null) return "—";
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}m ${s}s`;
}

// Speaker label to display name: "SPEAKER_00" → "Speaker 1"
export function formatSpeakerLabel(label: string): string {
  const match = label.match(/SPEAKER_(\d+)/);
  if (match) return `Speaker ${parseInt(match[1], 10) + 1}`;
  return label;
}

// Speaker index to Tailwind colour class
const SPEAKER_COLOURS = ["blue", "green", "orange", "purple", "pink", "teal", "indigo", "rose"];
export function speakerColour(speakerLabel: string): string {
  const match = speakerLabel.match(/\d+/);
  const idx = match ? parseInt(match[0], 10) % SPEAKER_COLOURS.length : 0;
  return SPEAKER_COLOURS[idx];
}
```

---

## Constraints
- Toast IDs must use `crypto.randomUUID()` — never Math.random()
- `useCountUp` must use `requestAnimationFrame`, not `setInterval` — smoother animation
- `formatDuration` must handle `null`, `undefined`, and `0` gracefully
- Zustand stores must be importable without React context — no Provider needed
- `useHealthCheck` `retry: false` is intentional — failed health checks should show error immediately, not retry silently
