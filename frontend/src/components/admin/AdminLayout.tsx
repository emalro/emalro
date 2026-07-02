/**
 * @jsxImportSource preact
 *
 * Admin sidebar + content layout.
 *
 * Wraps every authenticated admin page (dashboard, projects,
 * blog, contacts, resume). Renders a fixed sidebar with the
 * brand, navigation links, theme toggle, and a logout button.
 * The active route is highlighted; clicking a link navigates
 * via wouter.
 *
 * The sidebar mirrors the data-terminal aesthetic: slate-900
 * base, amber accent, JetBrains Mono for the brand. The links
 * route to the known admin paths; placeholder routes (e.g.
 * /admin/projects) show a "Próximamente" page until PR #6 ships
 * the real CRUD UIs.
 */
import { Link, useLocation } from "wouter";
import { type ComponentChildren } from "preact";

import { cn } from "../../lib/cn";
import { useAuth } from "./AuthContext";

type NavItem = {
  href: string;
  label: string;
  match: (path: string) => boolean;
};

const NAV_ITEMS: ReadonlyArray<NavItem> = [
  {
    href: "/admin/dashboard",
    label: "Panel",
    match: (p) => p === "/admin" || p === "/admin/" || p === "/admin/dashboard",
  },
  {
    href: "/admin/projects",
    label: "Proyectos",
    match: (p) => p.startsWith("/admin/projects"),
  },
  {
    href: "/admin/blog",
    label: "Blog",
    match: (p) => p.startsWith("/admin/blog"),
  },
  {
    href: "/admin/contacts",
    label: "Contactos",
    match: (p) => p.startsWith("/admin/contacts"),
  },
  {
    href: "/admin/resume",
    label: "Currículum",
    match: (p) => p.startsWith("/admin/resume"),
  },
];

function ThemeToggle() {
  // Read the current theme from <html data-theme> (set by the
  // public Layout.astro's pre-paint inline script) and toggle
  // it. Persists to localStorage so the next paint picks it up
  // via the same inline script.
  const onToggle = () => {
    if (typeof document === "undefined") return;
    const html = document.documentElement;
    const current = html.getAttribute("data-theme") === "light" ? "light" : "dark";
    const next = current === "dark" ? "light" : "dark";
    html.setAttribute("data-theme", next);
    try {
      localStorage.setItem("theme", next);
    } catch (_) {
      // ignore quota / disabled storage
    }
  };
  return (
    <button
      type="button"
      onClick={onToggle}
      class="rounded-md border border-border bg-bg-surface px-3 py-1.5 text-xs uppercase tracking-wide text-ink-secondary hover:bg-bg-elevated"
      aria-label="Cambiar tema"
    >
      Tema
    </button>
  );
}

export default function AdminLayout({
  children,
}: {
  children: ComponentChildren;
}) {
  const { admin, logout } = useAuth();
  const [location, navigate] = useLocation();

  const onLogout = async () => {
    await logout();
    navigate("/admin", { replace: true });
  };

  return (
    <div class="flex min-h-[calc(100vh-4rem)]">
      <aside class="sticky top-0 flex h-screen w-64 shrink-0 flex-col border-r border-border bg-bg-surface">
        <div class="flex items-center gap-2 border-b border-border px-5 py-4">
          <span class="font-mono text-sm font-semibold uppercase tracking-widest text-accent">
            emalro
          </span>
          <span class="text-xs text-ink-tertiary">admin</span>
        </div>
        <nav class="flex-1 overflow-y-auto px-3 py-4">
          <ul class="flex flex-col gap-1">
            {NAV_ITEMS.map((item) => {
              const active = item.match(location);
              return (
                <li>
                  <Link
                    href={item.href}
                    class={cn(
                      "block rounded-md px-3 py-2 text-sm transition-colors",
                      active
                        ? "bg-bg-elevated text-ink-primary"
                        : "text-ink-secondary hover:bg-bg-elevated hover:text-ink-primary",
                    )}
                  >
                    {item.label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>
        <div class="flex flex-col gap-2 border-t border-border px-4 py-3">
          {admin ? (
            <p class="truncate text-xs text-ink-tertiary" title={admin.email}>
              {admin.email}
            </p>
          ) : null}
          <div class="flex items-center justify-between gap-2">
            <ThemeToggle />
            <button
              type="button"
              onClick={onLogout}
              class="rounded-md border border-border bg-transparent px-3 py-1.5 text-xs uppercase tracking-wide text-ink-secondary hover:bg-error/10 hover:text-error"
            >
              Cerrar sesión
            </button>
          </div>
        </div>
      </aside>
      <main class="flex-1 overflow-x-hidden">{children}</main>
    </div>
  );
}
