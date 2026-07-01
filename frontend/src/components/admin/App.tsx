/**
 * @jsxImportSource preact
 *
 * Admin SPA shell.
 *
 * This component is the entry point of the admin SPA. It is
 * mounted by `src/pages/admin/[...path].astro` with
 * `client:only="preact"` so the admin bundle is not linked from
 * the public site.
 *
 * Routing: wouter (a tiny Preact-compatible router). The
 * catch-all Astro route at `/admin/*` means Astro only ever
 * renders this component; everything inside (login redirect,
 * dashboard, CRUD) is purely client-side.
 *
 * Data layer: TanStack Query, via the shared `adminQueryClient`
 * (see `src/lib/admin-query.ts`). The provider lives inside
 * `<App>` so the QueryClient runtime is only loaded for the
 * admin bundle — the public site never imports it.
 *
 * Auth: `<AuthProvider>` wraps the SPA and exposes
 * `useAuth()`. The route guard below enforces the redirect
 * rules from `admin-panel` REQ-admin-panel-02:
 * - Unauthenticated visitor at any /admin/* path other than
 *   /admin itself → redirect to /admin (the login page).
 * - Authenticated visitor at /admin → redirect to
 *   /admin/dashboard.
 */
import { Route, Switch, Link, useLocation } from "wouter";
import { QueryClientProvider } from "@tanstack/react-query";
import { useEffect } from "preact/hooks";

import { adminQueryClient } from "../../lib/admin-query";
import { AuthProvider, useAuth } from "./AuthContext";
import LoginForm from "./LoginForm";

/**
 * Splash while the auth state is being resolved on first load.
 * Prevents a "flash of login form" for users who already have
 * a valid session.
 */
function Splash() {
  return (
    <section class="mx-auto flex min-h-[70vh] max-w-md items-center px-6">
      <p class="w-full text-center text-sm text-ink-tertiary">Cargando…</p>
    </section>
  );
}

/**
 * Route guard. Reads the current auth status and either
 * renders the requested route or redirects.
 */
function GuardedRoutes() {
  const { status } = useAuth();
  const [location, navigate] = useLocation();

  // /admin = login route. /admin/<x> = authenticated routes.
  const isLoginRoute =
    location === "/admin" || location === "/admin/" || location === "/admin/";

  useEffect(() => {
    if (status === "loading") return;
    if (status === "unauthenticated" && !isLoginRoute) {
      // Unauthenticated visitor trying to access a protected
      // page → bounce to login.
      navigate("/admin", { replace: true });
    } else if (status === "authenticated" && isLoginRoute) {
      // Logged-in visitor at the login page → land on the
      // dashboard.
      navigate("/admin/dashboard", { replace: true });
    }
  }, [status, isLoginRoute, navigate]);

  if (status === "loading") {
    return <Splash />;
  }

  return (
    <Switch>
      <Route path="/admin" component={LoginForm} />
      <Route path="/admin/dashboard" component={DashboardPlaceholder} />
      <Route component={NotFound} />
    </Switch>
  );
}

/** Placeholder dashboard. Replaced by the real Dashboard in commit 8. */
function DashboardPlaceholder() {
  return (
    <section class="mx-auto max-w-3xl px-6 py-12">
      <h1 class="font-mono text-2xl text-ink-primary">Dashboard</h1>
      <p class="mt-3 text-sm text-ink-secondary">
        El dashboard con conteos llega en el commit 8.
      </p>
      <p class="mt-6 text-xs text-ink-tertiary">
        <Link href="/admin">← Volver al inicio de admin</Link>
      </p>
    </section>
  );
}

function NotFound() {
  return (
    <section class="mx-auto max-w-md px-6 py-16">
      <h1 class="font-mono text-2xl text-ink-primary">404</h1>
      <p class="mt-3 text-sm text-ink-secondary">
        Esa ruta no existe dentro del panel.
      </p>
      <p class="mt-6 text-xs text-ink-tertiary">
        <Link href="/admin">Volver al inicio de admin</Link>
      </p>
    </section>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={adminQueryClient}>
      <AuthProvider>
        <GuardedRoutes />
      </AuthProvider>
    </QueryClientProvider>
  );
}
