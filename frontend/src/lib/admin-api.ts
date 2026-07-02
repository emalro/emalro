/**
 * Frontend API client for the admin SPA (per `auth-jwt` REQ-auth-jwt
 * and `admin-panel` REQ-admin-panel-02).
 *
 * This is the admin-side counterpart to `frontend/src/lib/api.ts`
 * (the public client). They are kept as separate files so:
 * - The public client stays thin and tree-shakable; the admin
 *   client carries the admin auth surface and is loaded only by
 *   the /admin/* bundle.
 * - The two clients can evolve independently (e.g., admin gets
 *   `credentials: "include"` on every call; public stays
 *   `credentials: "omit"`).
 *
 * Behavior contract (mirrors the public client):
 * - `credentials: "include"` on every fetch so the httpOnly
 *   `emalro_session` cookie (set by `POST /api/v1/auth/login`) is
 *   sent on every call. Per `auth-jwt` REQ-auth-jwt-04 the token
 *   is held in the cookie, not in JS-readable storage.
 * - 15 s `AbortController` timeout on every request.
 * - Sends `X-Request-Id` and reads the echoed value off the
 *   response so error reports include the backend log id.
 * - Unwraps the `{data, error}` envelope: on success returns
 *   `data`; on error throws a typed `AdminApiError`.
 * - On `TypeError` (network failure, CORS, abort) rethrows as
 *   `AdminApiError(0, "network_error", ...)`.
 *
 * NO retries, no token refresh (per ADR-03 — no refresh tokens).
 * The SPA's `useAuth` hook handles 401 → logout at the
 * application layer.
 *
 * Hand-written types mirror the backend Pydantic shapes
 * (no codegen per design decision N1). The backend
 * `tests/contract/test_i18n_shape.py` and admin endpoint tests
 * catch drift if the response shape changes.
 */
import type { LocalizedStr } from "../types/content";

// Re-export so admin components can `import type { LocalizedStr }
// from "@/lib/admin-api"` alongside the api methods.
export type { LocalizedStr };

/** Error envelope returned by the backend on a non-2xx response. */
export type AdminError = {
  code: string;
  message: string;
};

/** Standard `{ data, error }` envelope shape. */
export type AdminEnvelope<T> =
  | { data: T; error: null }
  | { data: null; error: AdminError };

/** `GET /api/v1/auth/me` response (PR #5a backend). */
export type AdminMe = {
  id: string;
  email: string;
  is_active: boolean;
};

/** `POST /api/v1/auth/login` response. The httpOnly cookie is also
 *  set on the response (not visible to JS). */
export type AdminLoginResponse = {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
};

export class AdminApiError extends Error {
  /** HTTP status (0 for network/abort failures — never a real status). */
  status: number;
  /** Locked error code from the envelope, or "network_error" for
   *  pre-response failures. */
  code: string;
  /** The `X-Request-Id` echoed by the backend, or `null` if the
   *  failure happened before we got a response. Callers can log
   *  this to correlate a user complaint with a backend log line. */
  requestId: string | null;
  constructor(
    status: number,
    code: string,
    message: string,
    requestId: string | null,
  ) {
    super(message);
    this.name = "AdminApiError";
    this.status = status;
    this.code = code;
    this.requestId = requestId;
  }
}

const API_BASE: string = (() => {
  const raw = (import.meta.env.PUBLIC_API_URL as string | undefined) ?? "";
  // Same normalization as the public client: strip trailing slashes
  // and the optional `/api/v1` suffix so the caller can pass
  // `http://localhost:8000` OR `http://localhost:8000/api/v1`.
  let base = raw.replace(/\/+$/, "");
  base = base.replace(/\/api\/v1$/, "");
  return base;
})();

const REQUEST_TIMEOUT_MS = 15_000;

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const url = path.startsWith("http") ? path : `${API_BASE}${path}`;
  const requestId =
    typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "X-Request-Id": requestId,
    ...(init.headers as Record<string, string> | undefined),
  };

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  let res: Response;
  try {
    // `credentials: "include"` sends the httpOnly `emalro_session`
    // cookie on every admin call. The public client defaults to
    // `omit`; admin is always `include`.
    res = await fetch(url, {
      ...init,
      headers,
      credentials: "include",
      signal: controller.signal,
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new AdminApiError(
        0,
        "network_error",
        `Request to ${path} timed out after ${REQUEST_TIMEOUT_MS}ms`,
        requestId,
      );
    }
    throw new AdminApiError(
      0,
      "network_error",
      `Network error contacting ${path}: ${(err as Error).message ?? "unknown"}`,
      requestId,
    );
  } finally {
    clearTimeout(timer);
  }

  const responseRequestId = res.headers.get("X-Request-Id") ?? requestId;
  const payload = (await res.json().catch(() => ({}))) as {
    data?: unknown;
    error?: AdminError;
  };
  if (!res.ok || payload?.error) {
    const err: AdminError = payload?.error ?? {
      code: "server_error",
      message: res.statusText,
    };
    throw new AdminApiError(res.status, err.code, err.message, responseRequestId);
  }
  return (payload?.data !== undefined ? payload.data : payload) as T;
}

/**
 * Public admin API surface.
 *
 * - `me()` — verify the httpOnly session cookie is still valid and
 *   load the current admin's email for the dashboard header.
 * - `login()` — POST credentials; backend sets the cookie and
 *   returns a JWT in the body (the cookie is what the SPA uses;
 *   the body is the canonical confirmation).
 * - `logout()` — POST to clear the cookie. No-op if not logged in.
 *
 * CRUD methods (projects, blog, contacts, resume) are added in
 * PR #6 (the CRUD UIs). This PR only ships the auth surface.
 */
export const adminApi = {
  me: () => request<AdminMe>("/api/v1/auth/me"),
  login: (email: string, password: string) =>
    request<AdminLoginResponse>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  logout: () =>
    request<{ status: "logged_out" }>("/api/v1/auth/logout", {
      method: "POST",
    }),
};
