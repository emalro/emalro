# emalro — Personal Portfolio

A static, dark-default, mobile-first personal portfolio/CV for a Data Analyst profile. Phase 1 (MVP) ships eight functional requirements with a self-hosted Astro static build; backend, auth, blog, and analytics are deferred to later phases.

## Stack

- **Astro 4.x** with `output: 'static'`, fully prerendered, no SSR.
- **Tailwind CSS** with a CSS-variable theme token system (dark default).
- **TypeScript strict** for content contracts.
- **Ajv** JSON Schema validator enforcing the JSONB `{"es","en"}` shape at build time.
- **Vercel** for hosting (project Root Directory: `frontend/`, build: `npm run build`, output: `dist/`).

## Repository layout

```
emalro/
├── .github/workflows/ci.yml     # MVP CI: frontend job only
├── README.md                    # this file
└── frontend/                    # Astro project (Vercel Root Directory)
    ├── src/
    │   ├── data/                # JSON data files (JSONB shape) + JSON Schemas
    │   ├── types/               # TypeScript content types
    │   ├── scripts/             # head-bootstrap, theme, i18n (PR #2 adds lenis, sort, typed-role)
    │   ├── styles/              # global.css with CSS variables (theme tokens)
    │   ├── layouts/             # Layout.astro
    │   ├── components/          # Navbar, ThemeToggle, LanguageSelector, sections/
    │   └── pages/index.astro
    ├── scripts/validate-i18n.mjs  # build-time JSONB validator
    ├── public/                  # static assets (favicon, img/)
    ├── astro.config.mjs
    ├── tailwind.config.mjs
    ├── tsconfig.json
    └── package.json
```

## MVP scope (Phase 1)

Implemented in this MVP:

- **RF-01** SPA-style smooth scroll (Lenis lands in PR #2)
- **RF-03** Dark/light mode toggle, dark default, persisted
- **RF-05** Hero section (PR #2)
- **RF-06** Experience section with chronological sort (PR #2)
- **RF-07** Education section with chronological sort (PR #2)
- **RF-08** Projects section (PR #3)
- **RF-09** Courses and certifications section (PR #3)
- **RF-12** Footer (minimal in PR #1, full version in PR #3)

Deferred to later phases:

- **Fase 2:** Blog, contact form, auth + JWT, admin CMS + CRUD, image upload, Supabase Postgres, FastAPI backend, Render hosting.
- **Fase 3:** Analytics, tag clickability + `/explore`, breadcrumbs, skeleton loaders.

## Run locally

```bash
cd frontend
npm install
npm run dev          # http://localhost:4321
```

## Build

```bash
cd frontend
npm run build
```

`npm run build` automatically runs `npm run prebuild` first, which validates every JSON data file against its JSON Schema. A violation fails the build.

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

Avatar/cover images currently live locally in `public/img/`. To migrate to Supabase Storage in Fase 2, swap the `image_url` value to a `https://<ref>.supabase.co/storage/v1/object/public/media/...` URL — no code change required.

## Deploy

This project is configured for Vercel with `frontend/` as the Root Directory.

1. Connect the repository in Vercel.
2. Set Root Directory to `frontend/`.
3. Override the build command if needed: `npm run build` (default).
4. Output Directory: `dist/` (Vercel default for Astro).
5. (Optional) set `PUBLIC_API_URL` for Fase 2+ API integration; not used in MVP.

CI (`.github/workflows/ci.yml`) runs the same `npm run build` on every PR to `main` and blocks merge on failure.

## Phase 2 / 3 migration path

When backend, auth, or analytics land in later phases:

- JSONB shape is already in place; no schema migration needed.
- Image URLs swap from local `/img/...` to Supabase Storage URLs without code changes.
- The i18n resolver (`src/scripts/i18n.ts`) and theme resolver (`src/scripts/theme.ts`) become the API client surface; no rewrite required.
- Add a `backend/` folder at the repo root when FastAPI lands; convert the project to a monorepo at that time.

## License

[Add license here before public launch.]
