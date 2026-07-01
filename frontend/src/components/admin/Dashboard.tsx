/**
 * @jsxImportSource preact
 *
 * Admin dashboard.
 *
 * Renders 4 summary cards: projects (visible / drafts), blog
 * (visible / drafts), contacts (total / unread), and resume
 * (rows total). Each card is a link to the relevant management
 * page (placeholder until PR #6 wires the real UIs).
 *
 * Data source: the dashboard makes 5 calls to the existing
 * admin list endpoints (projects, blog, contacts, contacts/trash,
 * resume) and computes the counts in-browser. This is wasteful
 * (5 round trips for 4 numbers) but avoids adding a new
 * `/api/v1/admin/dashboard/counts` endpoint in this PR.
 *
 * TODO(replace-with-aggregated-endpoint): once a
 * `/api/v1/admin/dashboard/counts` endpoint lands, swap the
 * 5 useQuery calls below for a single one. The response shape
 * can stay the same (just compute counts server-side).
 */
import { useQuery } from "@tanstack/react-query";
import { Link } from "wouter";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "./ui/card";
import { Skeleton } from "./ui/skeleton";

import { adminApi, AdminApiError } from "../../lib/admin-api";

type ProjectsList = { data: { is_visible: boolean }[] };
type BlogList = { data: { is_visible: boolean }[] };
type ContactsList = { data: { read_at: string | null; deleted_at: string | null }[] };
type ResumeList = { data: unknown[] };

async function fetchProjects(): Promise<ProjectsList> {
  const res = await fetch(
    `${(import.meta.env.PUBLIC_API_URL as string | undefined ?? "").replace(/\/+$/, "").replace(/\/api\/v1$/, "")}/api/v1/admin/projects?page=1&limit=100`,
    { credentials: "include" },
  );
  if (!res.ok) {
    throw new AdminApiError(res.status, "load_failed", res.statusText, null);
  }
  return (await res.json()) as ProjectsList;
}

async function fetchBlog(): Promise<BlogList> {
  const res = await fetch(
    `${(import.meta.env.PUBLIC_API_URL as string | undefined ?? "").replace(/\/+$/, "").replace(/\/api\/v1$/, "")}/api/v1/admin/blog?page=1&limit=100`,
    { credentials: "include" },
  );
  if (!res.ok) {
    throw new AdminApiError(res.status, "load_failed", res.statusText, null);
  }
  return (await res.json()) as BlogList;
}

async function fetchContacts(): Promise<ContactsList> {
  const res = await fetch(
    `${(import.meta.env.PUBLIC_API_URL as string | undefined ?? "").replace(/\/+$/, "").replace(/\/api\/v1$/, "")}/api/v1/admin/contacts?page=1&limit=100`,
    { credentials: "include" },
  );
  if (!res.ok) {
    throw new AdminApiError(res.status, "load_failed", res.statusText, null);
  }
  return (await res.json()) as ContactsList;
}

async function fetchContactsTrash(): Promise<ContactsList> {
  const res = await fetch(
    `${(import.meta.env.PUBLIC_API_URL as string | undefined ?? "").replace(/\/+$/, "").replace(/\/api\/v1$/, "")}/api/v1/admin/contacts/trash?page=1&limit=100`,
    { credentials: "include" },
  );
  if (!res.ok) {
    throw new AdminApiError(res.status, "load_failed", res.statusText, null);
  }
  return (await res.json()) as ContactsList;
}

async function fetchResume(): Promise<ResumeList> {
  const res = await fetch(
    `${(import.meta.env.PUBLIC_API_URL as string | undefined ?? "").replace(/\/+$/, "").replace(/\/api\/v1$/, "")}/api/v1/admin/resume`,
    { credentials: "include" },
  );
  if (!res.ok) {
    throw new AdminApiError(res.status, "load_failed", res.statusText, null);
  }
  return (await res.json()) as ResumeList;
}

function CountCard({
  title,
  primary,
  secondary,
  href,
}: {
  title: string;
  primary: string;
  secondary: string;
  href: string;
}) {
  return (
    <Link href={href} class="block transition-transform hover:scale-[1.01]">
      <Card class="h-full">
        <CardHeader>
          <CardTitle>{title}</CardTitle>
        </CardHeader>
        <CardContent>
          <p class="font-mono text-3xl text-ink-primary">{primary}</p>
          <CardDescription class="mt-1">{secondary}</CardDescription>
        </CardContent>
      </Card>
    </Link>
  );
}

function CountCardSkeleton() {
  return (
    <Card>
      <CardHeader>
        <Skeleton class="h-3 w-24" />
      </CardHeader>
      <CardContent>
        <Skeleton class="h-9 w-16" />
        <Skeleton class="mt-2 h-3 w-32" />
      </CardContent>
    </Card>
  );
}

export default function Dashboard() {
  const projects = useQuery({ queryKey: ["admin", "counts", "projects"], queryFn: fetchProjects });
  const blog = useQuery({ queryKey: ["admin", "counts", "blog"], queryFn: fetchBlog });
  const contacts = useQuery({ queryKey: ["admin", "counts", "contacts"], queryFn: fetchContacts });
  const contactsTrash = useQuery({ queryKey: ["admin", "counts", "contacts-trash"], queryFn: fetchContactsTrash });
  const resume = useQuery({ queryKey: ["admin", "counts", "resume"], queryFn: fetchResume });

  const isLoading =
    projects.isLoading ||
    blog.isLoading ||
    contacts.isLoading ||
    contactsTrash.isLoading ||
    resume.isLoading;
  const hasError =
    projects.isError || blog.isError || contacts.isError || contactsTrash.isError || resume.isError;

  const projectsTotal = projects.data?.data.length ?? 0;
  const projectsPublished =
    projects.data?.data.filter((p) => p.is_visible).length ?? 0;
  const projectsDrafts = projectsTotal - projectsPublished;

  const blogTotal = blog.data?.data.length ?? 0;
  const blogPublished = blog.data?.data.filter((p) => p.is_visible).length ?? 0;
  const blogDrafts = blogTotal - blogPublished;

  const contactsInbox = contacts.data?.data ?? [];
  const contactsTotal = contactsInbox.length;
  const contactsUnread = contactsInbox.filter((c) => c.read_at === null).length;
  const contactsTrashCount = contactsTrash.data?.data.length ?? 0;

  const resumeTotal = resume.data?.data.length ?? 0;

  return (
    <section class="mx-auto max-w-6xl px-6 py-8">
      <div class="mb-6">
        <h1 class="font-mono text-2xl text-ink-primary">Panel</h1>
        <p class="mt-1 text-sm text-ink-secondary">
          Resumen de contenido y mensajes.
        </p>
      </div>
      {hasError ? (
        <p class="mb-4 rounded-md border border-error/40 bg-error/10 px-3 py-2 text-sm text-error">
          No se pudieron cargar los conteos. Reintentá recargando la página.
        </p>
      ) : null}
      <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {isLoading ? (
          <>
            <CountCardSkeleton />
            <CountCardSkeleton />
            <CountCardSkeleton />
            <CountCardSkeleton />
          </>
        ) : (
          <>
            <CountCard
              title="Proyectos"
              primary={`${projectsPublished} publicados`}
              secondary={`${projectsDrafts} borradores · ${projectsTotal} total`}
              href="/admin/projects"
            />
            <CountCard
              title="Blog"
              primary={`${blogPublished} publicados`}
              secondary={`${blogDrafts} borradores · ${blogTotal} total`}
              href="/admin/blog"
            />
            <CountCard
              title="Mensajes"
              primary={`${contactsTotal} en inbox`}
              secondary={`${contactsUnread} no leídos · ${contactsTrashCount} en papelera`}
              href="/admin/contacts"
            />
            <CountCard
              title="Currículum"
              primary={`${resumeTotal} filas`}
              secondary="Experiencia + educación + cursos"
              href="/admin/resume"
            />
          </>
        )}
      </div>
    </section>
  );
}
