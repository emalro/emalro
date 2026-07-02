/**
 * @jsxImportSource preact
 *
 * Auth context for the admin SPA.
 *
 * Single source of truth for "who is the current admin". The
 * `<AuthProvider>` wraps the admin app; consumers call
 * `useAuth()` to read the current admin + the `login`/`logout`
 * actions.
 *
 * Lifecycle:
 * 1. On mount, the provider calls `adminApi.me()`. The
 *    httpOnly `emalro_session` cookie is sent automatically
 *    (see `admin-api.ts`).
 *    - 200 → `status = "authenticated"`, `admin` populated.
 *    - 401 (no cookie / expired) → `status = "unauthenticated"`.
 *    - network error → `status = "unauthenticated"`; the
 *      operator can still try to log in (the login request is
 *      a fresh call).
 * 2. `login(email, password)` calls `adminApi.login()`. On
 *    success the backend sets the cookie; we then call
 *    `adminApi.me()` to load the admin. On failure we rethrow
 *    the `AdminApiError` so the form can show the error code.
 * 3. `logout()` calls `adminApi.logout()` (which clears the
 *    cookie) and then resets local state to
 *    `unauthenticated`.
 *
 * 401 propagation: when `adminApi.me()` returns 401 on a
 * subsequent check (e.g., after a long idle), the provider
 * flips back to `unauthenticated`. The route guard in App.tsx
 * handles the redirect to /admin.
 */
import {
  createContext,
  type ComponentChildren,
} from "preact";
import { useContext, useEffect, useState, useCallback } from "preact/hooks";

import {
  adminApi,
  AdminApiError,
  type AdminMe,
} from "../../lib/admin-api";

export type AuthStatus = "loading" | "authenticated" | "unauthenticated";

export type AuthContextValue = {
  status: AuthStatus;
  admin: AdminMe | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error(
      "useAuth() must be used inside <AuthProvider>. Wrap your tree.",
    );
  }
  return ctx;
}

export function AuthProvider({ children }: { children: ComponentChildren }) {
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [admin, setAdmin] = useState<AdminMe | null>(null);

  // On mount: verify the cookie. If the operator already has a
  // valid session, we land them on the dashboard without showing
  // the login form.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const me = await adminApi.me();
        if (cancelled) return;
        setAdmin(me);
        setStatus("authenticated");
      } catch (err) {
        if (cancelled) return;
        // 401 (no cookie / expired) and network errors both
        // land here. Either way, the operator is not
        // authenticated and should see the login form.
        if (err instanceof AdminApiError) {
          setAdmin(null);
          setStatus("unauthenticated");
        } else {
          // Non-AdminApiError — should not happen (adminApi
          // always throws AdminApiError), but be safe.
          setAdmin(null);
          setStatus("unauthenticated");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(
    async (email: string, password: string): Promise<void> => {
      // The login request sets the httpOnly cookie as a side
      // effect. We then re-fetch /me to populate the admin
      // record. If me() fails for any reason, the login still
      // succeeded (the cookie is set) but we surface the error
      // so the caller can decide.
      await adminApi.login(email, password);
      const me = await adminApi.me();
      setAdmin(me);
      setStatus("authenticated");
    },
    [],
  );

  const logout = useCallback(async (): Promise<void> => {
    try {
      await adminApi.logout();
    } finally {
      // Whether or not the backend succeeded, drop local state
      // — the operator is now logged out from the SPA's POV.
      setAdmin(null);
      setStatus("unauthenticated");
    }
  }, []);

  const value: AuthContextValue = {
    status,
    admin,
    isLoading: status === "loading",
    login,
    logout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
