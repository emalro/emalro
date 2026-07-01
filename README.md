# emalro — Personal Portfolio

Owner: Emanuel Romero · emalro.com.ar

A dark-default, mobile-first personal portfolio/CV for a Data Analyst profile. Phase 1 (MVP) ships the public site as a self-hosted Astro static build; Phase 2 adds a FastAPI + Supabase backend with an admin SPA for content management.

## Stack

### Frontend (Fase 1 + 2)

- **Astro 4.x** with `output: 'static'`, fully prerendered, no SSR.
- **Tailwind CSS** with a CSS-variable theme token system (dark default).
- **Preact + Wouter** for the admin SPA mounted at `/admin/*` (PR #14 + #6b).
- **TanStack Query** for the admin's data fetching (PR #14).
- **TypeScript strict** for content contracts.
- **Ajv** JSON Schema validator enforcing the JSONB `{"es","en"}` shape at build time.
- **Vercel** for hosting (project Root Directory: `frontend/`, build: `npm run build`, output: `dist/`).

### Backend (Fase 2)

- **FastAPI** (Python 3.11) — REST API + admin auth + image upload.
- **SQLModel + asyncpg** — async ORM on top of SQLAlchemy 2.
- **PostgreSQL** on **Supabase** — pooler on port 6543 in production.
- **Supabase Storage** — image bucket `media` (public, prod-only).
- **JWT (HS256)** cookie auth — `emalro_session` httpOnly cookie.
- **Render** for hosting (project Root Directory: `backend/`, build: `pip install -r requirements.txt`, start: `uvicorn app.main:app`).

## Repository layout

```
emalro/
├── .github/workflows/ci.yml     # CI: frontend build + backend tests
├── README.md                    # this file
├── backend/                     # FastAPI project (Render Root Directory)
│   ├── app/
│   │   ├── api/v1/              # routers: auth, public, contacts, admin (split per-resource)
│   │   ├── core/                # config, db, security, rate_limit
│   │   ├── middleware/          # envelope + request-id
│   │   ├── models/              # SQLModel tables
│   │   ├── schemas/             # Pydantic request/response shapes
│   │   ├── scripts/             # create_admin, seed_data
│   │   └── services/            # storage, sanitize, slug, cache_purge
│   ├── alembic/                 # DB migrations
│   ├── tests/                   # pytest suite (api / contract / unit)
│   ├── requirements.txt
│   └── .env.example
└── frontend/                    # Astro + Preact project (Vercel Root Directory)
    ├── src/
    │   ├── data/                # JSON data files (JSONB shape) + JSON Schemas
    │   ├── types/               # TypeScript content types
    │   ├── scripts/             # head-bootstrap, theme, i18n
    │   ├── styles/              # global.css with CSS variables (theme tokens)
    │   ├── layouts/             # Layout.astro
    │   ├── components/          # Navbar, ThemeToggle, LanguageSelector, sections/
    │   ├── lib/                 # api.ts (admin + public clients)
    │   ├── pages/               # Astro pages (index, blog, contact, [slug])
    │   └── pages/admin/         # Admin SPA (Preact, mounted at /admin/*)
    ├── scripts/validate-i18n.mjs  # build-time JSONB validator
    ├── public/                  # static assets (favicon, img/)
    └── package.json
```

## MVP scope (Phase 1)

Implemented in this MVP:

- **RF-01** SPA-style smooth scroll
- **RF-03** Dark/light mode toggle, dark default, persisted
- **RF-05** Hero section
- **RF-06** Experience section with chronological sort
- **RF-07** Education section with chronological sort
- **RF-08** Projects section
- **RF-09** Courses and certifications section
- **RF-12** Footer

## Fase 2 (backend + admin SPA)

Phase 2 adds a FastAPI backend and an admin SPA for content management. The public site remains a static build; the admin SPA is a Preact app mounted under `/admin/*`.

### Backend env vars (Render)

| Var                       | Required | Default                  | Notes                                                                                  |
| ------------------------- | -------- | ------------------------ | -------------------------------------------------------------------------------------- |
| `DATABASE_URL`            | yes      | —                        | Local: `postgresql+asyncpg://emalro:emalro@localhost:5432/emalro`. Prod: pooler on 6543. |
| `SUPABASE_URL`            | yes      | —                        | `https://<project-ref>.supabase.co`                                                     |
| `SUPABASE_SERVICE_KEY`    | yes      | —                        | Service-role key (NOT the anon key). Never expose to the FE.                           |
| `JWT_SECRET`              | yes      | —                        | 32+ chars of high-entropy random data. `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `JWT_EXPIRATION_HOURS`    | no       | `8`                      |                                                                                        |
| `ALLOWED_ORIGINS`         | no       | `http://localhost:4321`  | Comma-separated. Add the Vercel + admin origins in prod.                                |
| `ENV`                     | no       | `dev`                    | `dev` / `test` / `prod`. Controls the image storage backend.                          |
| `PORT`                    | no       | `8000`                   |                                                                                        |
| `LOGIN_RATE_LIMIT`        | no       | `5/minute`               | slowapi bucket for `/auth/login`.                                                       |
| `CONTACT_RATE_LIMIT`      | no       | `5/hour`                 | slowapi bucket for `POST /contacts`.                                                     |
| `IMAGE_MAX_BYTES`         | no       | `5242880` (5 MB)         | Upload size cap.                                                                        |
| `UPLOAD_DIR`              | no       | `./uploads`              | Local-dev / test storage root. Ignored when `ENV=prod` (Supabase Storage is used).      |

### Creating the first admin

The backend ships a provisioning CLI. Run it from the `backend/` directory:

```bash
cd backend
python -m app.scripts.create_admin <email> <password>
```

The script is idempotent: re-running with the same email updates the password hash. The admin must be active (`is_active=True`) to log in.

### Admin SPA

The admin SPA is mounted at `/admin/*` in the frontend. It is gated by the `emalro_session` httpOnly cookie that the backend issues on successful login.

To log in:

1. Navigate to `/admin` — the SPA shows the login form.
2. Submit the email + password — the backend sets the cookie and the SPA re-fetches the admin profile.
3. Once authenticated, the SPA renders the dashboard and the per-resource views.

What the admin can do (each view calls a dedicated endpoint):

- **Dashboard** (`/admin`) — card counts: projects (published/drafts), blog (published/drafts), contacts (total/unread/trashed), resume (total). Backed by `GET /api/v1/admin/dashboard/counts`.
- **Projects** (`/admin/projects`) — list + create + edit + delete. Backed by `GET/POST /api/v1/admin/projects` and `PUT/DELETE /api/v1/admin/projects/{id}`.
- **Blog** (`/admin/blog`) — list + create + edit + delete. Drafts auto-publish when `is_visible` flips true. Backed by `GET/POST /api/v1/admin/blog` and `PUT/DELETE /api/v1/admin/blog/{id}`.
- **Contacts** (`/admin/contacts`) — inbox + trash + read toggle. Backed by `GET /api/v1/admin/contacts`, `GET /api/v1/admin/contacts/trash`, `PATCH /api/v1/admin/contacts/{id}`, `PATCH /api/v1/admin/contacts/{id}/read`, `DELETE /api/v1/admin/contacts/{id}`.
- **Resume** (`/admin/resume`) — list + create + edit + delete + drag-to-reorder. Backed by `GET/POST /api/v1/admin/resume`, `PUT/DELETE /api/v1/admin/resume/{id}`, and `POST /api/v1/admin/resume/reorder`.

The admin copy is hardcoded in Spanish (no i18n yet — the operator is the only user).

### Local image storage

In dev / test (`ENV=dev` or `ENV=test`), uploaded images land on disk under `backend/uploads/` (gitignored). The upload endpoint returns a dev URL of the shape `/api/v1/admin/images/<path>`, and a static-serve route streams the file back so the round-trip works end-to-end without Supabase.

In production (`ENV=prod`), the upload endpoint forwards the file to Supabase Storage (bucket `media`) via the REST API. The returned URL is a Supabase public URL of the shape `https://<ref>.supabase.co/storage/v1/object/public/media/...`. The `LocalStorage` backend is unused in prod.

The env switch is automatic — operators do not need to toggle anything between local and prod beyond setting `ENV` and the Supabase env vars.

## Run locally

### Frontend

```bash
cd frontend
npm install
npm run dev          # http://localhost:4321
```

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # then fill in DATABASE_URL, SUPABASE_URL, SUPABASE_SERVICE_KEY, JWT_SECRET
alembic upgrade head
python -m app.scripts.seed_data
python -m app.scripts.create_admin admin@emalro.com.ar 'YourSecurePassword'
uvicorn app.main:app --reload --port 8000
```

## Build

```bash
cd frontend
npm run build
```

`npm run build` automatically runs `npm run prebuild` first, which validates every JSON data file against its JSON Schema. A violation fails the build.

## Test

```bash
cd backend
./.venv/bin/pytest -v
```

The suite covers the API contract (auth, contacts, admin CRUD), the LocalizedStr JSONB shape, and the markdown sanitizer.

```bash
cd frontend
npm test            # vitest (ContactForm)
npm run validate:i18n
```

## The JSONB shape contract (non-negotiable)

Every localizable prose string in `frontend/src/data/*.json` is an object of shape `{"es": "<non-empty string>", "en": "<string>"}`. The Spanish value is required; the English value may be empty (the UI falls back to Spanish silently). The build-time validator in `scripts/validate-i18n.mjs` enforces this on every `npm run build`, including CI.

Why: adopting the shape from day 1 prevents a Fase 3 migration sweep of every static file when full i18n ships.

## Replace placeholders with real content

Every data file currently contains entries prefixed with `[PLACEHOLDER]`. **These are release-blockers** — search for `[PLACEHOLDER]` before any public launch and replace with real CV data. The shape stays the same; only the values change.

Field-by-field checklist:

- `src/data/personal.json` — name, role, summary, hard/soft skills, avatar
- `src/data/experience.json` — organization, role, dates, description
- `src/data/education.json` — institution, degree, dates, description
- `src/data/projects.json` — title, description, cover image, technologies, tags, links
- `src/data/courses.json` — platform, name, verification URL
- `src/data/social.json` — LinkedIn, GitHub, Kaggle, Tableau Public URLs

Avatar/cover images currently live locally in `public/img/`. The admin image upload endpoint (Fase 2) returns Supabase URLs in prod and local dev URLs (`/api/v1/admin/images/...`) in dev — the `image_url` field on projects/blog/resume accepts both.

## Deploy

This project is configured for Vercel (frontend) + Render (backend).

### Frontend (Vercel)

1. Connect the repository in Vercel.
2. Set Root Directory to `frontend/`.
3. Build command: `npm run build` (default).
4. Output Directory: `dist/` (Vercel default for Astro).
5. Set `PUBLIC_API_URL` to the backend's public URL (e.g. `https://emalro-api.onrender.com`).

### Backend (Render)

1. Create a new Web Service from the repository.
2. Set Root Directory to `backend/`.
3. Build command: `pip install -r requirements.txt`.
4. Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
5. Set all the env vars from the table above (`DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `JWT_SECRET`, `ENV=prod`, `ALLOWED_ORIGINS`).
6. Run `alembic upgrade head` once via the Render shell, then `python -m app.scripts.create_admin <email> <password>` to provision the first admin.

CI (`.github/workflows/ci.yml`) runs the frontend build (with the backend started in the background for the build-time fetch) and the backend pytest suite on every PR to `main` and blocks merge on failure.

## License

[Add license here before public launch.]
