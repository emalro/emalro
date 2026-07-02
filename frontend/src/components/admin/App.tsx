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
 * (see `src/lib/admin-query.ts`).
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
import { useEffect, type ComponentChildren } from "preact/hooks";

import { adminQueryClient } from "../../lib/admin-query";
import { AuthProvider, useAuth } from "./AuthContext";
import LoginForm from "./LoginForm";
import AdminLayout from "./AdminLayout";
import Dashboard from "./Dashboard";

/** Splash while the auth state is being resolved on first load. */
function Splash() {
  return (
    <section class="mx-auto flex min-h-[70vh] max-w-md items-center px-6">
      <p class="w-full text-center text-sm text-ink-tertiary">Cargando…</p>
    </section>
  );
}

/** Placeholder for the CRUD pages that ship with PR #6. */
function ComingSoon({ feature }: { feature: string }) {
  return (
    <section class="mx-auto max-w-3xl px-6 py-16">
      <h1 class="font-mono text-2xl text-ink-primary">{feature}</h1>
      <p class="mt-3 text-sm text-ink-secondary">
        Próximamente: gestión de {feature.toLowerCase()}.
      </p>
      <p class="mt-6 text-xs text-ink-tertiary">
        <Link href="/admin/dashboard">← Volver al panel</Link>
      </p>
    </section>
  );
}

function NotFound() {
  return (
    <AdminLayout>
      <section class="mx-auto max-w-md px-6 py-16">
        <h1 class="font-mono text-2xl text-ink-primary">404</h1>
        <p class="mt-3 text-sm text-ink-secondary">
          Esa ruta no existe dentro del panel.
        </p>
        <p class="mt-6 text-xs text-ink-tertiary">
          <Link href="/admin/dashboard">Volver al panel</Link>
        </p>
      </section>
    </AdminLayout>
  );
}

/**
 * Authenticated routes, wrapped in <AdminLayout>.
 * The dashboard is the first route; the CRUD UIs are
 * placeholders until PR #6.
 */
function AuthenticatedRoutes() {
  return (
    <AdminLayout>
      <Switch>
        <Route path="/admin/dashboard" component={Dashboard} />
        <Route path="/admin/projects">
          <ComingSoon feature="Proyectos" />
        </Route>
        <Route path="/admin/blog">
          <ComingSoon feature="Blog" />
        </Route>
        <Route path="/admin/contacts">
          <ComingSoon feature="Contactos" />
        </Route>
        <Route path="/admin/resume">
          <ComingSoon feature="Currículum" />
        </Route>
      </Switch>
    </AdminLayout>
  );
}

/**
 * Route guard. Reads the current auth status and either
 * renders the requested route or redirects.
 */
function GuardedRoutes() {
  const { status } = useAuth();
  const [location, navigate] = useLocation();

  const isLoginRoute =
    location === "/admin" || location === "/admin/";

  useEffect(() => {
    if (status === "loading") return;
    if (status === "unauthenticated" && !isLoginRoute) {
      navigate("/admin", { replace: true });
    } else if (status === "authenticated" && isLoginRoute) {
      navigate("/admin/dashboard", { replace: true });
    }
  }, [status, isLoginRoute, navigate]);

  if (status === "loading") {
    return <Splash />;
  }

  if (status === "unauthenticated") {
    // Only the login route is reachable for unauthenticated
    // visitors; the guard above already redirected any other
    // path.
    return (
      <Switch>
        <Route path="/admin" component={LoginForm} />
      </Switch>
    );
  }

  return <AuthenticatedRoutes />;
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
