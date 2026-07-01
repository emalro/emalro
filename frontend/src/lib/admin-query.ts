/**
 * Shared TanStack QueryClient for the admin SPA.
 *
 * One module, one instance, configured once. The App component
 * mounts the provider; every admin page that calls
 * `useQuery` / `useMutation` picks up the same client via
 * `useQueryClient()`.
 *
 * Defaults (per `admin-panel` design):
 * - `staleTime: 30_000` — admin data is rarely hot, but a
 *   navigation within 30 s should hit the cache.
 * - `refetchOnWindowFocus: true` — when the operator returns to
 *   the tab they expect fresh counts. No SSE / WebSocket in
 *   Fase 2 (see `admin-panel` REQ-admin-panel-03 + Out of
 *   Scope item 2).
 * - `retry: 0` — backend failures surface immediately so the
 *   error UI shows; we do NOT want silent retries that confuse
 *   the operator.
 *
 * The QueryClient lives in its own file (not inside App.tsx) so
 * future vitest suites can import it directly and so a future
 * TanStack Query Devtools panel can be added in one place.
 */
import { QueryClient } from "@tanstack/react-query";

export const adminQueryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: true,
      retry: 0,
    },
    mutations: {
      retry: 0,
    },
  },
});
