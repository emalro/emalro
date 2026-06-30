# emalro backend

FastAPI + SQLModel + Alembic + Supabase Postgres for the emalro portfolio
CMS. This is the foundation service for the Fase 2 backend change. The
public Astro frontend (in `../frontend/`) consumes this API at
`/api/v1/*`. The admin SPA (mounted at `/admin/*` in the frontend) is
JWT-protected.

## Requirements

- Python 3.11+
- PostgreSQL 16 (via Docker Compose locally; via Supabase pooler in prod)
- See `.env.example` for required environment variables

## Local development

```bash
# 1. Start the local Postgres
docker compose up -d

# 2. Install Python dependencies
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env with the local values

# 4. Run migrations (no-op in PR #1; first migration lands in PR #2)
alembic upgrade head

# 5. Run the test suite
pytest -v

# 6. Boot the dev server
uvicorn app.main:app --reload
```

## Endpoints (PR #1 scope)

- `GET /api/v1/health` — process-alive check, no auth, no DB.
- `POST /api/v1/auth/login` — admin login; issues a JWT and sets the
  `emalro_session` httpOnly cookie. Rate-limited (5/minute per IP).
- `POST /api/v1/auth/logout` (PR #1 scaffold) — clears the cookie.

All responses use the `{"data": ..., "error": null}` envelope.

## Project layout

```
app/
  main.py              FastAPI app, lifespan, CORS, slowapi, exception handlers
  core/                config, security, db session, deps
  schemas/             Pydantic models (i18n, envelope, auth)
  models/              SQLModel tables
  api/                 deps, v1 routers
  middleware/          envelope, request_id
  scripts/             create_admin CLI
alembic/               migrations
tests/                 pytest suite
```

## Links

- Root README: [`../README.md`](../README.md) for the full-stack story.
- Design: engram observation 306 (`sdd/fase-2-backend-cms/design`).
- Spec: engram observation 308 (`sdd/fase-2-backend-cms/spec/backend-foundation`).
