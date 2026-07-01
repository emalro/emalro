/**
 * Frontend API client (per `data-pipeline` REQ-data-pipeline-03).
 *
 * This is the SINGLE integration point between the Astro/Preact
 * frontend and the FastAPI backend. Components MUST NOT call `fetch`
 * directly. The wrapper:
 *
 * - Prepends `PUBLIC_API_URL` to relative paths.
 * - Sets a 15 s `AbortController` timeout on every request so a
 *   stalled backend cannot leave the caller hanging forever.
 * - Sets `keepalive: true` for write requests (POST/PUT/PATCH/DELETE)
 *   so an in-flight submission survives an accidental tab close.
 * - Sends and reads `X-Request-Id` for log correlation with the
 *   backend (the server echoes any client-supplied id back on the
 *   response).
 * - Makes `credentials: "include"` opt-in (admin auth callers pass
 *   it explicitly; public endpoints omit it).
 * - Unwraps the response envelope: on success returns `data`; on
 *   error throws a typed `ApiError` (the caller catches and renders).
 * - On `TypeError` (network failure, CORS, abort) rethrows as
 *   `ApiError("network_error", ..., 0)` so callers can branch on
 *   `err.status === 0` / `err.code === "network_error"`.
 *
 * No retries, no token refresh (per ADR-03 — no refresh tokens).
 * The admin SPA handles 401 -> logout at the TanStack Query layer;
 * the public site does not need retry on a transient failure.
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

import type { LocalizedStr } from "../types/content";

export type { LocalizedStr };

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
  /**
   * The `X-Request-Id` echoed by the backend (or `null` if the
   * failure happened before we got a response — e.g. timeout,
   * network error). Callers can log this to correlate a user
   * complaint with a specific backend log line.
   */
  requestId: string | null;
  constructor(
    code: string,
    message: string,
    status: number,
    requestId: string | null = null,
  ) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
    this.requestId = requestId;
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

/**
 * Public contact form payload (per `contact-form` REQ-03).
 *
 * `website` is the honeypot field. The backend rejects any submission
 * with a non-empty `website` (400 `bad_request`). The frontend renders
 * it off-screen + `tabindex=-1` + `aria-hidden="true"` so real users
 * never fill it; bots that fill all fields trigger the silent rejection.
 */
export type ContactPayload = {
  name: string;
  email: string;
  subject?: string;
  message: string;
  website?: string;
};

/** Response on the 201 path. */
export type ContactCreateResponse = {
  id: string;
  received_at: string;
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

/** Per-request timeout (ms). 15 s is generous for a public form
 *  POST and well under any reasonable user patience threshold.
 *  The backend rate-limits at 5/hour per IP, so a stalled request
 *  is almost certainly a backend problem, not a slow client. */
const REQUEST_TIMEOUT_MS = 15_000;

/** Methods that mutate state and benefit from `keepalive: true` so
 *  an accidental tab close does not drop the submission. The 64 KB
 *  cap is plenty for our payloads. */
const WRITE_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

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
 *
 * The `credentials` flag is opt-in (defaults to `"omit"`) so the
 * public endpoints do not send cookies they do not need. Admin
 * auth callers pass `"include"` explicitly to send the httpOnly
 * session cookie.
 */
async function request<T>(
  path: string,
  init: RequestInit = {},
  options: { unwrap?: boolean; credentials?: RequestCredentials } = {},
): Promise<T> {
  const url = path.startsWith("http") ? path : `${API_BASE}${path}`;

  // Generate a request id for log correlation. The backend's
  // `RequestIdMiddleware` echoes this back in the `X-Request-Id`
  // response header; we stash it on the `ApiError` so callers can
  // include it in support requests.
  const requestId =
    typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "X-Request-Id": requestId,
    ...(init.headers as Record<string, string> | undefined),
  };

  const method = (init.method ?? "GET").toUpperCase();
  const isWrite = WRITE_METHODS.has(method);

  // Per-request timeout via `AbortController`. Without this a
  // stalled connection would leave the form stuck on "submitting…"
  // until the browser's own (much longer) default timeout fired.
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  let res: Response;
  try {
    res = await fetch(url, {
      ...init,
      method,
      headers,
      credentials: options.credentials ?? "omit",
      // `keepalive: true` lets the browser keep the request alive
      // past tab close for write methods. Capped at 64 KB by the
      // browser, which is well above our payload size.
      keepalive: isWrite,
      signal: controller.signal,
    });
  } catch (err) {
    clearTimeout(timer);
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new ApiError(
        "network_error",
        `Request to ${path} timed out after ${REQUEST_TIMEOUT_MS}ms`,
        0,
        requestId,
      );
    }
    // `fetch` throws `TypeError` on network failure, CORS rejection,
    // DNS failure, offline, etc. — never returns `status: 0`.
    throw new ApiError(
      "network_error",
      `Network error contacting ${path}: ${(err as Error).message ?? "unknown"}`,
      0,
      requestId,
    );
  } finally {
    clearTimeout(timer);
  }

  // Capture the request id echoed by the backend (or fall back to
  // the one we sent, which is what the middleware will use if the
  // header wasn't propagated for some reason).
  const responseRequestId = res.headers.get("X-Request-Id") ?? requestId;

  let payload: { data?: unknown; error?: unknown; meta?: unknown };
  try {
    payload = (await res.json()) as typeof payload;
  } catch (err) {
    throw new ApiError(
      "parse_error",
      `Invalid JSON from ${path}: ${(err as Error).message}`,
      res.status,
      responseRequestId,
    );
  }
  if (payload.error) {
    const err = payload.error as { code: string; message: string };
    throw new ApiError(err.code, err.message, res.status, responseRequestId);
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
  options: { unwrap?: boolean; credentials?: RequestCredentials } = {},
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
  /**
   * Submit a contact-form message. The endpoint is unauthenticated
   * (no JWT) and rate-limited per IP at 5/hour (slowapi). The 6th
   * submission in a window returns 429 `rate_limited` with a
   * `Retry-After` header. The caller catches `ApiError` and renders
   * the localized error banner.
   */
  contacts: {
    submit: (payload: ContactPayload) =>
      request<ContactCreateResponse>("/api/v1/contacts", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
  },
};
