/**
 * Frontend API client (per `data-pipeline` REQ-data-pipeline-03).
 *
 * This is the SINGLE integration point between the Astro/Preact
 * frontend and the FastAPI backend. Components MUST NOT call `fetch`
 * directly. The wrapper:
 *
 * - Prepends `PUBLIC_API_URL` to relative paths.
 * - Sets `credentials: "include"` so the admin httpOnly cookie
 *   (set by `POST /api/v1/auth/login`) is sent on admin calls.
 * - Unwraps the response envelope: on success returns `data`; on
 *   error throws a typed `ApiError` (the caller catches and renders).
 *
 * No retries, no token refresh (per ADR-03 — no refresh tokens).
 * The admin SPA (PR #5) handles 401 -> logout at the TanStack Query
 * layer; the public site does not need retry on a transient failure.
 *
 * Hand-written types mirror the backend Pydantic shapes (no codegen
 * per design decision N1). The backend `tests/contract/test_i18n_shape.py`
 * catches drift if the response shape changes.
 *
 * Build-time vs runtime: this module is imported by both Astro pages
 * (build time, via `Astro.fetch` / `getStaticPaths`) and by admin
 * Preact islands (runtime, via TanStack Query). The `request()`
 * helper uses the global `fetch` in both contexts.
 */

export type LocalizedStr = { es: string; en: string };

/** Standard success/error envelope for non-paginated endpoints. */
export type Envelope<T> =
  | { data: T; error: null }
  | { data: null; error: { code: string; message: string } };

/** Paginated response shape: `data` is the list, `meta` is pagination info. */
export type PaginatedResponse<T> = {
  data: T[];
  meta: PageMeta;
  error: null;
};

export type PageMeta = {
  total: number;
  page: number;
  limit: number;
  pages: number;
};

export class ApiError extends Error {
  code: string;
  status: number;
  constructor(code: string, message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
  }
}

export type BlogPostSummary = {
  id: string;
  slug: string;
  title: LocalizedStr;
  excerpt: LocalizedStr | null;
  cover_image_url: string | null;
  tags: string[];
  is_visible: boolean;
  published_at: string | null;
  created_at: string;
};

export type BlogPostDetail = {
  id: string;
  slug: string;
  title: LocalizedStr;
  content: LocalizedStr;
  cover_image_url: string | null;
  tags: string[];
  is_visible: boolean;
  published_at: string | null;
  created_at: string;
  updated_at: string;
};

const API_BASE: string = (() => {
  const raw = (import.meta.env.PUBLIC_API_URL as string | undefined) ?? "";
  // Normalize trailing slashes and the optional `/api/v1` suffix.
  // The brief allows `http://localhost:8000/api/v1` as a convenience
  // for local dev, but the canonical form is the bare origin
  // (matching the design Section 15 example: paths include the
  // `/api/v1/...` prefix). Strip the suffix so both forms work.
  let base = raw.replace(/\/+$/, "");
  base = base.replace(/\/api\/v1$/, "");
  return base;
})();

/**
 * Make a typed request to the backend. The response shape varies
 * by endpoint:
 * - Non-paginated (e.g. `/api/v1/blog/{slug}`): standard envelope
 *   `{ data: T, error: null }`. We unwrap and return `T`.
 * - Paginated (e.g. `/api/v1/blog`): the response is
 *   `{ data: T[], meta: PageMeta, error: null }`. The top-level
 *   `data` is already the list, so we treat the entire response
 *   as `PaginatedResponse<T>` (no double-unwrap).
 *
 * To keep the call site simple, this helper just returns whatever
 * `envelope.data` is. For non-paginated endpoints that means a
 * single `T`; for paginated endpoints it means a `T[]` (the inner
 * `data` of the `PaginatedEnvelope`).
 *
 * The `unwrap` flag selects the behavior:
 * - `unwrap: true` (default for non-paginated): returns `envelope.data`
 *   (assumed to be `T`).
 * - `unwrap: false` (paginated): returns the full `PaginatedResponse<T>`
 *   object (which has its own `data` field, the list).
 */
async function request<T>(
  path: string,
  init: RequestInit = {},
  options: { unwrap?: boolean } = {},
): Promise<T> {
  const url = path.startsWith("http") ? path : `${API_BASE}${path}`;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init.headers as Record<string, string> | undefined),
  };
  const res = await fetch(url, {
    ...init,
    headers,
    credentials: "include",
  });
  if (!res.ok && res.status === 0) {
    throw new ApiError("network_error", `Request to ${path} failed`, 0);
  }
  let payload: { data?: unknown; error?: unknown; meta?: unknown };
  try {
    payload = (await res.json()) as typeof payload;
  } catch (err) {
    throw new ApiError(
      "parse_error",
      `Invalid JSON from ${path}: ${(err as Error).message}`,
      res.status,
    );
  }
  if (payload.error) {
    const err = payload.error as { code: string; message: string };
    throw new ApiError(err.code, err.message, res.status);
  }
  const unwrap = options.unwrap !== false; // default true
  if (unwrap) {
    return payload.data as T;
  }
  return payload as unknown as T;
}

/**
 * Build-time guard for `getStaticPaths`. When the backend is
 * unreachable at build time, Astro throws a 5xx build error. This
 * wrapper lets the blog list/detail pages fail fast with a clear
 * message identifying the unreachable route.
 */
export async function requestBuildTime<T>(
  path: string,
  context: string,
  options: { unwrap?: boolean } = {},
): Promise<T> {
  try {
    return await request<T>(path, {}, options);
  } catch (err) {
    if (err instanceof ApiError) {
      throw new Error(
        `Build-time fetch failed for ${context} (${path}): ` +
          `[${err.code}] ${err.message} (status=${err.status}). ` +
          `Ensure PUBLIC_API_URL is set and the backend is running.`,
      );
    }
    throw err;
  }
}

/**
 * Public API surface. The same names are used in PR #4 (contact form)
 * and PR #5/#6 (admin), which add more methods to this object.
 *
 * Paginated endpoints (`api.blog`) return the full
 * `PaginatedResponse<T>` so the caller can read both `data` (the
 * list) and `meta` (pagination). Non-paginated endpoints return
 * the unwrapped `T` directly.
 */
export const api = {
  blog: (q: { tag?: string; page?: number; limit?: number } = {}) => {
    const params = new URLSearchParams();
    if (q.tag) params.set("tag", q.tag);
    if (q.page) params.set("page", String(q.page));
    if (q.limit) params.set("limit", String(q.limit));
    const qs = params.toString();
    return request<PaginatedResponse<BlogPostSummary>>(
      `/api/v1/blog${qs ? `?${qs}` : ""}`,
      {},
      { unwrap: false },
    );
  },
  blogPost: (slug: string) =>
    request<BlogPostDetail>(`/api/v1/blog/${encodeURIComponent(slug)}`),
};
