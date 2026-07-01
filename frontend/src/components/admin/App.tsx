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
 * Auth + login form: wired in commit 7.
 */
import { Route, Switch, Link } from "wouter";
import { QueryClientProvider } from "@tanstack/react-query";

import { adminQueryClient } from "../../lib/admin-query";

/** Placeholder dashboard. Replaced by the real Dashboard in commit 8. */
function Dashboard() {
  return (
    <section class="mx-auto max-w-3xl px-6 py-12">
      <h1 class="font-mono text-2xl text-ink-primary">Dashboard</h1>
      <p class="mt-3 text-sm text-ink-secondary">
        Admin shell — el dashboard se monta en el commit 8.
      </p>
      <p class="mt-6 text-xs text-ink-tertiary">
        <Link href="/admin">← Volver al inicio de admin</Link>
      </p>
    </section>
  );
}

/** Admin landing — login page. Replaced by LoginForm in commit 7. */
function LoginPlaceholder() {
  return (
    <section class="mx-auto max-w-md px-6 py-16">
      <h1 class="font-mono text-2xl text-ink-primary">Acceso admin</h1>
      <p class="mt-3 text-sm text-ink-secondary">
        El formulario de inicio de sesión llega en el commit 7.
      </p>
      <p class="mt-6 text-xs text-ink-tertiary">
        <Link href="/admin/dashboard">Ir al dashboard (placeholder)</Link>
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
      <Switch>
        <Route path="/admin" component={LoginPlaceholder} />
        <Route path="/admin/dashboard" component={Dashboard} />
        <Route component={NotFound} />
      </Switch>
    </QueryClientProvider>
  );
}
