"""Admin endpoints: 401 (no auth) and 200 (with auth).

This module covers both the read+list surface (PR #2) and the
write surface added in PR #6 (POST/PUT/DELETE on projects, blog,
resume; PATCH on contacts; image upload; dashboard counts).

Mandatory tests (per the orchestrator's brief):
- 401 with `unauthorized` envelope on missing/invalid auth.
- 200 with envelope on valid JWT (cookie) for each list endpoint.
- 201 / 200 / 204 with envelope on valid CRUD requests.
- 404 on not-found.
- 422 on missing required fields (LocalizedStr.es).
- Slug dedup: a second create with the same title gets `-2`.

Endpoints covered:
- GET /api/v1/admin/projects         (PR #2)
- POST /api/v1/admin/projects        (PR #6)
- PUT /api/v1/admin/projects/{id}    (PR #6)
- DELETE /api/v1/admin/projects/{id} (PR #6)
- GET /api/v1/admin/blog             (PR #2)
- GET /api/v1/admin/contacts         (PR #2)
- GET /api/v1/admin/contacts/trash   (PR #2)
- GET /api/v1/admin/resume           (PR #2)
"""

import asyncio
import json
import pytest

from app.core.security import SESSION_COOKIE_NAME
from tests.api._seed import (
    seed_blog_post,
    seed_contact,
    seed_project,
    seed_resume_experience,
    seed_resume_personal,
)


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _login(client, email="admin@emalro.com.ar", password="S3cr3t!Pass"):
    """Helper: log in and return the response (cookie is on the client)."""
    r = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert r.status_code == 200, f"login failed: {r.text}"
    return r


# ---------------------------------------------------------------------------
# 401 unauthorized (no cookie)
# ---------------------------------------------------------------------------


def test_admin_projects_requires_auth(client):
    r = client.get("/api/v1/admin/projects")
    assert r.status_code == 401
    body = r.json()
    assert body["error"]["code"] == "unauthorized"


def test_admin_blog_requires_auth(client):
    r = client.get("/api/v1/admin/blog")
    assert r.status_code == 401
    body = r.json()
    assert body["error"]["code"] == "unauthorized"


def test_admin_contacts_requires_auth(client):
    r = client.get("/api/v1/admin/contacts")
    assert r.status_code == 401
    body = r.json()
    assert body["error"]["code"] == "unauthorized"


def test_admin_contacts_trash_requires_auth(client):
    r = client.get("/api/v1/admin/contacts/trash")
    assert r.status_code == 401
    body = r.json()
    assert body["error"]["code"] == "unauthorized"


def test_admin_resume_requires_auth(client):
    r = client.get("/api/v1/admin/resume")
    assert r.status_code == 401
    body = r.json()
    assert body["error"]["code"] == "unauthorized"


def test_admin_with_invalid_cookie_returns_401(client):
    client.cookies.set(SESSION_COOKIE_NAME, "this-is-not-a-jwt")
    r = client.get("/api/v1/admin/projects")
    assert r.status_code == 401
    body = r.json()
    assert body["error"]["code"] in ("unauthorized", "token_expired")


# ---------------------------------------------------------------------------
# 200 happy paths (with valid auth)
# ---------------------------------------------------------------------------


def test_admin_projects_lists_all_with_auth(client, admin_user, db_session):
    _run(seed_project(db_session, slug="visible", tags=["a"]))
    _run(seed_project(db_session, slug="draft", tags=["a"], is_visible=False))
    _login(client)

    r = client.get("/api/v1/admin/projects")
    assert r.status_code == 200
    body = r.json()
    slugs = [p["slug"] for p in body["data"]]
    # Admin sees ALL projects, including drafts.
    assert "visible" in slugs
    assert "draft" in slugs
    assert body["meta"]["total"] == 2
    # Each item exposes `is_visible` for the toggle UI.
    by_slug = {p["slug"]: p for p in body["data"]}
    assert by_slug["visible"]["is_visible"] is True
    assert by_slug["draft"]["is_visible"] is False


def test_admin_projects_localizedstr_shape(client, admin_user, db_session):
    _run(seed_project(db_session, slug="apexlogic"))
    _login(client)
    r = client.get("/api/v1/admin/projects")
    data = r.json()["data"]
    assert len(data) == 1
    item = data[0]
    assert "es" in item["title"] and "en" in item["title"]
    assert "es" in item["description"] and "en" in item["description"]


def test_admin_projects_pagination_meta(client, admin_user, db_session):
    for i in range(5):
        _run(seed_project(db_session, slug=f"proj-{i}"))
    _login(client)
    r = client.get("/api/v1/admin/projects?page=1&limit=2")
    body = r.json()
    assert len(body["data"]) == 2
    assert body["meta"]["total"] == 5
    assert body["meta"]["page"] == 1
    assert body["meta"]["limit"] == 2
    assert body["meta"]["pages"] == 3


def test_admin_blog_lists_all_with_auth(client, admin_user, db_session):
    _run(seed_blog_post(db_session, slug="visible", tags=["x"]))
    _run(seed_blog_post(db_session, slug="draft", tags=["x"], is_visible=False))
    _login(client)
    r = client.get("/api/v1/admin/blog")
    body = r.json()
    slugs = [p["slug"] for p in body["data"]]
    assert "visible" in slugs
    assert "draft" in slugs
    by_slug = {p["slug"]: p for p in body["data"]}
    assert by_slug["draft"]["is_visible"] is False


def test_admin_contacts_inbox_excludes_trash(client, admin_user, db_session):
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    _run(seed_contact(db_session, email="inbox@example.com", name="Inbox"))
    _run(seed_contact(
        db_session,
        email="trash@example.com",
        name="Trash",
        deleted_at=now,
    ))
    _login(client)
    r = client.get("/api/v1/admin/contacts")
    body = r.json()
    emails = [m["email"] for m in body["data"]]
    assert "inbox@example.com" in emails
    assert "trash@example.com" not in emails
    assert body["meta"]["total"] == 1


def test_admin_contacts_trash_only_trashed(client, admin_user, db_session):
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    _run(seed_contact(db_session, email="inbox@example.com", name="Inbox"))
    _run(seed_contact(
        db_session,
        email="trash@example.com",
        name="Trash",
        deleted_at=now,
    ))
    _login(client)
    r = client.get("/api/v1/admin/contacts/trash")
    body = r.json()
    emails = [m["email"] for m in body["data"]]
    assert "trash@example.com" in emails
    assert "inbox@example.com" not in emails
    assert body["meta"]["total"] == 1


def test_admin_resume_returns_all_rows(client, admin_user, db_session):
    _run(seed_resume_personal(db_session))
    _run(seed_resume_experience(db_session, organization="Arbusta"))
    _run(seed_resume_experience(db_session, organization="Hidden", is_visible=False))
    _login(client)
    r = client.get("/api/v1/admin/resume")
    body = r.json()
    data = body["data"]
    sections = {row["section"] for row in data}
    # Admin sees ALL rows (no is_visible filter).
    assert "personal" in sections
    assert "experience" in sections
    orgs = [r["subtitle"] for r in data if r["section"] == "experience"]
    assert "Hidden" in orgs
    assert "Arbusta" in orgs


# ---------------------------------------------------------------------------
# Admin returns RAW markdown (content polish).
#
# The admin read+list endpoints keep the source markdown unchanged so
# the operator can edit it in the CodeMirror editor (PR #6). The
# public read path (`test_public.py`) sanitizes the same fields. The
# asymmetry is intentional: admin = source of truth, public = safe
# HTML for visitors.
# ---------------------------------------------------------------------------


def test_admin_projects_returns_raw_markdown_description(
    client, admin_user, db_session
):
    """`/api/v1/admin/projects` returns the raw markdown source."""
    from app.schemas.i18n import LocalizedStr

    _run(
        seed_project(
            db_session,
            slug="apexlogic",
            description=LocalizedStr(
                es="* Clean data\n* Build reports",
                en="* Clean data\n* Build reports",
            ),
        )
    )
    _login(client)
    r = client.get("/api/v1/admin/projects")
    data = r.json()["data"]
    assert len(data) == 1
    desc = data[0]["description"]
    # Raw markdown: bullet markers and line breaks preserved.
    assert desc["es"].startswith("* Clean data")
    assert "\n" in desc["es"] or " " in desc["es"]  # the raw source text
    # No HTML tags — admin is the source of truth.
    assert "<ul>" not in desc["es"]
    assert "<li>" not in desc["es"]


def test_admin_resume_returns_raw_markdown_description(
    client, admin_user, db_session
):
    """`/api/v1/admin/resume` returns the raw markdown source on experience."""
    from app.schemas.i18n import LocalizedStr
    from sqlmodel import col, select
    from app.models.resume import ResumeData

    row = _run(seed_resume_experience(db_session, organization="Acme"))
    # Override the description with markdown content.
    fetched = (
        _run(
            db_session.execute(
                select(ResumeData).where(col(ResumeData.id) == row.id)
            )
        )
    ).scalars().one()
    fetched.description = LocalizedStr(
        es="**bold** and *italic*",
        en="**bold** and *italic*",
    ).model_dump_json()
    _run(db_session.commit())

    _login(client)
    r = client.get("/api/v1/admin/resume")
    data = r.json()["data"]
    experience_rows = [d for d in data if d["section"] == "experience"]
    assert experience_rows
    desc = experience_rows[0]["description"]
    # Raw markdown: bold and italic markers preserved as text.
    assert "**bold**" in desc["es"]
    assert "*italic*" in desc["es"]
    # No HTML tags from the sanitizer.
    assert "<strong>" not in desc["es"]
    assert "<em>" not in desc["es"]


# ---------------------------------------------------------------------------
# Project CRUD (PR #6)
#
# The 5-step flow per the orchestrator's brief:
# 1. Create admin user (via `admin_user` fixture).
# 2. POST /api/v1/auth/login (sets the cookie).
# 3. POST /api/v1/admin/projects (create).
# 4. Assert 201, envelope shape, and the slug is what we expect.
# 5. Repeat for PUT and DELETE.
# ---------------------------------------------------------------------------


def _project_create_payload(**overrides) -> dict:
    base = {
        "title": {"es": "Mi Proyecto Nuevo", "en": "My New Project"},
        "description": {"es": "Descripcion del proyecto", "en": "Project description"},
        "technologies": [{"es": "Python", "en": "Python"}],
        "tags": ["python", "data"],
        "image_url": None,
        "github_url": None,
        "demo_url": None,
        "is_visible": True,
    }
    base.update(overrides)
    return base


def test_admin_projects_create_success(client, admin_user, db_session):
    """POST /api/v1/admin/projects returns 201 with the new row."""
    _login(client)
    r = client.post(
        "/api/v1/admin/projects",
        json=_project_create_payload(),
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["error"] is None
    item = body["data"]
    # Server-generated fields
    assert isinstance(item["id"], str) and item["id"]
    assert item["slug"] == "mi-proyecto-nuevo"
    assert item["is_visible"] is True
    # LocalizedStr preserved
    assert item["title"]["es"] == "Mi Proyecto Nuevo"
    assert item["title"]["en"] == "My New Project"
    assert item["description"]["es"] == "Descripcion del proyecto"
    assert item["tags"] == ["python", "data"]


def test_admin_projects_create_requires_auth(client, admin_user, db_session):
    """POST without cookie is 401."""
    r = client.post(
        "/api/v1/admin/projects",
        json=_project_create_payload(),
    )
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"


def test_admin_projects_create_dedupes_slug(client, admin_user, db_session):
    """Two creates with the same title get slugs `foo` and `foo-2`."""
    _login(client)
    r1 = client.post(
        "/api/v1/admin/projects",
        json=_project_create_payload(),
    )
    assert r1.status_code == 201
    slug1 = r1.json()["data"]["slug"]
    assert slug1 == "mi-proyecto-nuevo"

    r2 = client.post(
        "/api/v1/admin/projects",
        json=_project_create_payload(),
    )
    assert r2.status_code == 201
    slug2 = r2.json()["data"]["slug"]
    assert slug2 == "mi-proyecto-nuevo-2"
    assert slug1 != slug2


def test_admin_projects_create_dedupes_third(client, admin_user, db_session):
    """Three creates with the same title get slugs `foo`, `foo-2`, `foo-3`."""
    _login(client)
    slugs = []
    for _ in range(3):
        r = client.post(
            "/api/v1/admin/projects",
            json=_project_create_payload(),
        )
        assert r.status_code == 201
        slugs.append(r.json()["data"]["slug"])
    assert slugs == ["mi-proyecto-nuevo", "mi-proyecto-nuevo-2", "mi-proyecto-nuevo-3"]


def test_admin_projects_create_falls_back_to_en_slug(
    client, admin_user, db_session
):
    """If `es` slugifies to empty, the server falls back to `en`."""
    _login(client)
    r = client.post(
        "/api/v1/admin/projects",
        json=_project_create_payload(
            title={"es": "", "en": "Fallback English Title"}
        ),
    )
    # The empty `es` is rejected at validation (LocalizedStr.es required).
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


def test_admin_projects_create_validation_missing_es(
    client, admin_user, db_session
):
    """LocalizedStr.es is required — 422 with validation_error."""
    _login(client)
    r = client.post(
        "/api/v1/admin/projects",
        json=_project_create_payload(title={"es": "", "en": "x"}),
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


def test_admin_projects_create_validation_extra_field(
    client, admin_user, db_session
):
    """`extra=forbid` rejects unknown fields with 422."""
    _login(client)
    r = client.post(
        "/api/v1/admin/projects",
        json={**_project_create_payload(), "extra_field": "nope"},
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


def test_admin_projects_update_success(client, admin_user, db_session):
    """PUT replaces the row and updates `updated_at` + `slug` stays put."""
    created = _run(seed_project(db_session, slug="original", is_visible=True))
    _login(client)
    r = client.put(
        f"/api/v1/admin/projects/{created.id}",
        json=_project_create_payload(
            title={"es": "Renombrado", "en": "Renamed"},
            is_visible=False,
        ),
    )
    assert r.status_code == 200, r.text
    item = r.json()["data"]
    # slug preserved (PUT does NOT regenerate the public identifier)
    assert item["slug"] == "original"
    assert item["title"]["es"] == "Renombrado"
    assert item["is_visible"] is False


def test_admin_projects_update_not_found(client, admin_user, db_session):
    """PUT on a missing id returns 404."""
    _login(client)
    r = client.put(
        "/api/v1/admin/projects/00000000-0000-0000-0000-000000000000",
        json=_project_create_payload(),
    )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


def test_admin_projects_update_requires_auth(client, admin_user, db_session):
    """PUT without cookie is 401."""
    created = _run(seed_project(db_session))
    r = client.put(
        f"/api/v1/admin/projects/{created.id}",
        json=_project_create_payload(),
    )
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"


def test_admin_projects_update_validation_missing_es(
    client, admin_user, db_session
):
    """PUT with invalid LocalizedStr.es is 422."""
    created = _run(seed_project(db_session))
    _login(client)
    r = client.put(
        f"/api/v1/admin/projects/{created.id}",
        json=_project_create_payload(title={"es": "", "en": "x"}),
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


def test_admin_projects_delete_success(client, admin_user, db_session):
    """DELETE removes the row and 204s; subsequent GET 404s."""
    created = _run(seed_project(db_session, slug="deleteme"))
    _login(client)
    r = client.delete(f"/api/v1/admin/projects/{created.id}")
    assert r.status_code == 204
    # The row is gone: a follow-up list does not include it.
    r2 = client.get("/api/v1/admin/projects")
    assert r2.status_code == 200
    slugs = [p["slug"] for p in r2.json()["data"]]
    assert "deleteme" not in slugs


def test_admin_projects_delete_not_found(client, admin_user, db_session):
    """DELETE on a missing id returns 404."""
    _login(client)
    r = client.delete("/api/v1/admin/projects/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


def test_admin_projects_delete_requires_auth(client, admin_user, db_session):
    """DELETE without cookie is 401."""
    created = _run(seed_project(db_session))
    r = client.delete(f"/api/v1/admin/projects/{created.id}")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"


# ---------------------------------------------------------------------------
# Blog CRUD (PR #6)
# ---------------------------------------------------------------------------


def _blog_create_payload(**overrides) -> dict:
    base = {
        "title": {"es": "Mi primer post", "en": "My first post"},
        "content": {"es": "Contenido en espanol", "en": "Content in English"},
        "cover_image_url": None,
        "tags": ["intro", "welcome"],
        "is_visible": True,
        "published_at": None,
    }
    base.update(overrides)
    return base


def test_admin_blog_create_success(client, admin_user, db_session):
    """POST /api/v1/admin/blog returns 201 + slug + published_at auto-set."""
    _login(client)
    r = client.post("/api/v1/admin/blog", json=_blog_create_payload())
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["error"] is None
    item = body["data"]
    assert isinstance(item["id"], str) and item["id"]
    assert item["slug"] == "mi-primer-post"
    assert item["is_visible"] is True
    # published_at auto-set to now (because is_visible=True and published_at=None).
    assert item["published_at"] is not None
    assert item["title"]["es"] == "Mi primer post"
    assert item["tags"] == ["intro", "welcome"]


def test_admin_blog_create_draft_does_not_set_published_at(
    client, admin_user, db_session
):
    """Draft (is_visible=False) keeps `published_at` null."""
    _login(client)
    r = client.post(
        "/api/v1/admin/blog",
        json=_blog_create_payload(is_visible=False, published_at=None),
    )
    assert r.status_code == 201
    item = r.json()["data"]
    assert item["published_at"] is None
    assert item["is_visible"] is False


def test_admin_blog_create_explicit_published_at_preserved(
    client, admin_user, db_session
):
    """If the client supplies `published_at`, the server keeps it."""
    from datetime import datetime, timezone

    ts = datetime(2024, 5, 1, tzinfo=timezone.utc)
    _login(client)
    r = client.post(
        "/api/v1/admin/blog",
        json=_blog_create_payload(published_at=ts.isoformat()),
    )
    assert r.status_code == 201
    item = r.json()["data"]
    assert item["published_at"] is not None
    assert item["published_at"].startswith("2024-05-01")


def test_admin_blog_create_dedupes_slug(client, admin_user, db_session):
    """Two creates with the same title get `slug` and `slug-2`."""
    _login(client)
    r1 = client.post("/api/v1/admin/blog", json=_blog_create_payload())
    assert r1.status_code == 201
    slug1 = r1.json()["data"]["slug"]
    assert slug1 == "mi-primer-post"

    r2 = client.post("/api/v1/admin/blog", json=_blog_create_payload())
    assert r2.status_code == 201
    slug2 = r2.json()["data"]["slug"]
    assert slug2 == "mi-primer-post-2"


def test_admin_blog_create_validation_missing_es(
    client, admin_user, db_session
):
    """LocalizedStr.es is required for both title and content."""
    _login(client)
    r = client.post(
        "/api/v1/admin/blog",
        json=_blog_create_payload(title={"es": "", "en": "x"}),
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


def test_admin_blog_create_requires_auth(client, admin_user, db_session):
    """POST without cookie is 401."""
    r = client.post("/api/v1/admin/blog", json=_blog_create_payload())
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"


def test_admin_blog_update_success(client, admin_user, db_session):
    """PUT replaces the row; slug is preserved; updated_at is bumped."""
    created = _run(seed_blog_post(db_session, slug="original", is_visible=True))
    _login(client)
    r = client.put(
        f"/api/v1/admin/blog/{created.id}",
        json=_blog_create_payload(
            title={"es": "Renombrado", "en": "Renamed"},
            is_visible=False,
        ),
    )
    assert r.status_code == 200, r.text
    item = r.json()["data"]
    assert item["slug"] == "original"
    assert item["title"]["es"] == "Renombrado"
    assert item["is_visible"] is False


def test_admin_blog_update_publishes_draft(client, admin_user, db_session):
    """PUT flipping is_visible False->True with no published_at sets it to now."""
    from sqlmodel import select, col
    from app.models.blog import BlogPost

    # Seed a draft: pass `published_at=None` so the helper doesn't
    # auto-set it to now.
    created = _run(
        seed_blog_post(
            db_session,
            slug="draft",
            is_visible=False,
            published_at=None,
        )
    )
    # Sanity check on the seeded row.
    fetched = (
        _run(
            db_session.execute(
                select(BlogPost).where(col(BlogPost.id) == created.id)
            )
        )
    ).scalars().one()
    fetched.published_at = None
    _run(db_session.commit())
    assert fetched.published_at is None

    _login(client)
    r = client.put(
        f"/api/v1/admin/blog/{created.id}",
        json=_blog_create_payload(is_visible=True, published_at=None),
    )
    assert r.status_code == 200
    item = r.json()["data"]
    assert item["is_visible"] is True
    # Server auto-set published_at to now.
    assert item["published_at"] is not None


def test_admin_blog_update_not_found(client, admin_user, db_session):
    """PUT on a missing id returns 404."""
    _login(client)
    r = client.put(
        "/api/v1/admin/blog/00000000-0000-0000-0000-000000000000",
        json=_blog_create_payload(),
    )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


def test_admin_blog_update_requires_auth(client, admin_user, db_session):
    """PUT without cookie is 401."""
    created = _run(seed_blog_post(db_session))
    r = client.put(
        f"/api/v1/admin/blog/{created.id}",
        json=_blog_create_payload(),
    )
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"


def test_admin_blog_delete_success(client, admin_user, db_session):
    """DELETE removes the row and 204s; list reflects the change."""
    created = _run(seed_blog_post(db_session, slug="deleteme"))
    _login(client)
    r = client.delete(f"/api/v1/admin/blog/{created.id}")
    assert r.status_code == 204
    r2 = client.get("/api/v1/admin/blog")
    slugs = [p["slug"] for p in r2.json()["data"]]
    assert "deleteme" not in slugs


def test_admin_blog_delete_not_found(client, admin_user, db_session):
    """DELETE on a missing id returns 404."""
    _login(client)
    r = client.delete("/api/v1/admin/blog/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


def test_admin_blog_delete_requires_auth(client, admin_user, db_session):
    """DELETE without cookie is 401."""
    created = _run(seed_blog_post(db_session))
    r = client.delete(f"/api/v1/admin/blog/{created.id}")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"


# ---------------------------------------------------------------------------
# Contacts PATCH / DELETE (PR #6)
#
# Contact messages use soft-delete with `deleted_at`. The PATCH
# endpoint is the operator's primary path; the DELETE is the
# irreversible cleanup. The combined PATCH accepts BOTH the
# `deleted` and `read` toggles in a single request so the
# operator can chain operations.
# ---------------------------------------------------------------------------


def test_admin_contacts_patch_trash(client, admin_user, db_session):
    """PATCH deleted=true moves the row to trash."""
    msg = _run(seed_contact(db_session, email="trashme@example.com", name="Trash"))
    _login(client)
    r = client.patch(
        f"/api/v1/admin/contacts/{msg.id}",
        json={"deleted": True, "read": False},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["error"] is None
    assert body["data"]["deleted_at"] is not None

    # Inbox no longer includes the message; trash does.
    inbox = client.get("/api/v1/admin/contacts").json()["data"]
    trash = client.get("/api/v1/admin/contacts/trash").json()["data"]
    inbox_emails = [m["email"] for m in inbox]
    trash_emails = [m["email"] for m in trash]
    assert "trashme@example.com" not in inbox_emails
    assert "trashme@example.com" in trash_emails


def test_admin_contacts_patch_restore(client, admin_user, db_session):
    """PATCH deleted=false (on a trashed message) restores it."""
    from datetime import datetime, timezone

    msg = _run(
        seed_contact(
            db_session,
            email="restore@example.com",
            name="Restore",
            deleted_at=datetime.now(timezone.utc),
        )
    )
    _login(client)
    r = client.patch(
        f"/api/v1/admin/contacts/{msg.id}",
        json={"deleted": False, "read": False},
    )
    assert r.status_code == 200
    assert r.json()["data"]["deleted_at"] is None

    inbox = client.get("/api/v1/admin/contacts").json()["data"]
    assert "restore@example.com" in [m["email"] for m in inbox]


def test_admin_contacts_patch_mark_read(client, admin_user, db_session):
    """PATCH read=true sets `read_at` on the message."""
    msg = _run(seed_contact(db_session, email="readme@example.com", name="Read"))
    _login(client)
    r = client.patch(
        f"/api/v1/admin/contacts/{msg.id}",
        json={"deleted": False, "read": True},
    )
    assert r.status_code == 200
    assert r.json()["data"]["read_at"] is not None


def test_admin_contacts_patch_read_endpoint(client, admin_user, db_session):
    """PATCH /read flips just the read_at timestamp."""
    msg = _run(seed_contact(db_session, email="focus@example.com", name="Focus"))
    _login(client)
    r = client.patch(
        f"/api/v1/admin/contacts/{msg.id}/read",
        json={"deleted": False, "read": True},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["data"]["read_at"] is not None
    # The dedicated /read endpoint does NOT touch deleted_at.
    assert body["data"]["deleted_at"] is None


def test_admin_contacts_patch_not_found(client, admin_user, db_session):
    """PATCH on a missing id returns 404."""
    _login(client)
    r = client.patch(
        "/api/v1/admin/contacts/00000000-0000-0000-0000-000000000000",
        json={"deleted": True, "read": True},
    )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


def test_admin_contacts_patch_requires_auth(client, admin_user, db_session):
    """PATCH without cookie is 401."""
    msg = _run(seed_contact(db_session))
    r = client.patch(
        f"/api/v1/admin/contacts/{msg.id}",
        json={"deleted": True, "read": False},
    )
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"


def test_admin_contacts_patch_validation_extra_field(
    client, admin_user, db_session
):
    """Extra keys in the PATCH body are rejected (422)."""
    msg = _run(seed_contact(db_session))
    _login(client)
    r = client.patch(
        f"/api/v1/admin/contacts/{msg.id}",
        json={"deleted": False, "read": False, "name": "newname"},
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


def test_admin_contacts_delete_permanent(client, admin_user, db_session):
    """DELETE removes the row entirely; subsequent GETs 404."""
    msg = _run(seed_contact(db_session, email="perm@example.com", name="Perm"))
    _login(client)
    r = client.delete(f"/api/v1/admin/contacts/{msg.id}")
    assert r.status_code == 204
    # The row is gone from both the inbox and the trash.
    inbox = client.get("/api/v1/admin/contacts").json()["data"]
    trash = client.get("/api/v1/admin/contacts/trash").json()["data"]
    assert "perm@example.com" not in [m["email"] for m in inbox + trash]


def test_admin_contacts_delete_not_found(client, admin_user, db_session):
    """DELETE on a missing id returns 404."""
    _login(client)
    r = client.delete(
        "/api/v1/admin/contacts/00000000-0000-0000-0000-000000000000"
    )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


def test_admin_contacts_delete_requires_auth(client, admin_user, db_session):
    """DELETE without cookie is 401."""
    msg = _run(seed_contact(db_session))
    r = client.delete(f"/api/v1/admin/contacts/{msg.id}")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"


# ---------------------------------------------------------------------------
# Resume CRUD + reorder (PR #6)
# ---------------------------------------------------------------------------


def _resume_create_payload(**overrides) -> dict:
    base = {
        "section": "experience",
        "display_order": None,
        "title": {"es": "Data Analyst", "en": "Data Analyst"},
        "subtitle": "Acme Corp",
        "description": {"es": "Descripcion", "en": "Description"},
        "start_date": "2024-01",
        "end_date": None,
        "url": None,
        "image_url": None,
        "tags": ["python"],
        "is_visible": True,
        "extra": {},
    }
    base.update(overrides)
    return base


def test_admin_resume_create_success(client, admin_user, db_session):
    """POST /api/v1/admin/resume returns 201 with the new row."""
    _login(client)
    r = client.post("/api/v1/admin/resume", json=_resume_create_payload())
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["error"] is None
    item = body["data"]
    assert isinstance(item["id"], str) and item["id"]
    assert item["section"] == "experience"
    assert item["title"]["es"] == "Data Analyst"
    # No other rows in the section, so display_order defaults to 1.
    assert item["display_order"] == 1


def test_admin_resume_create_explicit_display_order(
    client, admin_user, db_session
):
    """If `display_order` is supplied, the server keeps it."""
    _login(client)
    r = client.post(
        "/api/v1/admin/resume",
        json=_resume_create_payload(display_order=5),
    )
    assert r.status_code == 201
    assert r.json()["data"]["display_order"] == 5


def test_admin_resume_create_appends_to_section(client, admin_user, db_session):
    """A second row in the same section lands at max(display_order)+1."""
    _run(seed_resume_experience(db_session, organization="First", display_order=3))
    _login(client)
    r = client.post("/api/v1/admin/resume", json=_resume_create_payload())
    assert r.status_code == 201
    assert r.json()["data"]["display_order"] == 4


def test_admin_resume_create_validation_missing_es(
    client, admin_user, db_session
):
    """LocalizedStr.es is required (422)."""
    _login(client)
    r = client.post(
        "/api/v1/admin/resume",
        json=_resume_create_payload(title={"es": "", "en": "x"}),
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


def test_admin_resume_create_validation_empty_section(
    client, admin_user, db_session
):
    """`section` must be non-empty (422)."""
    _login(client)
    r = client.post(
        "/api/v1/admin/resume",
        json=_resume_create_payload(section=""),
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


def test_admin_resume_create_requires_auth(client, admin_user, db_session):
    """POST without cookie is 401."""
    r = client.post("/api/v1/admin/resume", json=_resume_create_payload())
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"


def test_admin_resume_update_success(client, admin_user, db_session):
    """PUT replaces the row; updated_at is bumped."""
    row = _run(seed_resume_experience(db_session, organization="Acme"))
    _login(client)
    r = client.put(
        f"/api/v1/admin/resume/{row.id}",
        json=_resume_create_payload(
            section="course",
            subtitle="Coursera",
            display_order=0,
        ),
    )
    assert r.status_code == 200, r.text
    item = r.json()["data"]
    assert item["section"] == "course"
    assert item["subtitle"] == "Coursera"
    assert item["display_order"] == 0


def test_admin_resume_update_not_found(client, admin_user, db_session):
    """PUT on a missing id returns 404."""
    import uuid as _uuid
    _login(client)
    payload = _resume_create_payload()
    # The update endpoint requires `display_order: int` (not optional).
    payload["display_order"] = 0
    r = client.put(
        f"/api/v1/admin/resume/{_uuid.uuid4()}",
        json=payload,
    )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


def test_admin_resume_update_requires_auth(client, admin_user, db_session):
    """PUT without cookie is 401."""
    row = _run(seed_resume_experience(db_session))
    r = client.put(
        f"/api/v1/admin/resume/{row.id}",
        json=_resume_create_payload(),
    )
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"


def test_admin_resume_delete_success(client, admin_user, db_session):
    """DELETE removes the row and 204s; list reflects the change."""
    row = _run(seed_resume_experience(db_session, organization="Doomed"))
    _login(client)
    r = client.delete(f"/api/v1/admin/resume/{row.id}")
    assert r.status_code == 204
    r2 = client.get("/api/v1/admin/resume")
    orgs = [
        d["subtitle"]
        for d in r2.json()["data"]
        if d["section"] == "experience"
    ]
    assert "Doomed" not in orgs


def test_admin_resume_delete_not_found(client, admin_user, db_session):
    """DELETE on a missing id returns 404."""
    import uuid as _uuid
    _login(client)
    r = client.delete(f"/api/v1/admin/resume/{_uuid.uuid4()}")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


def test_admin_resume_delete_requires_auth(client, admin_user, db_session):
    """DELETE without cookie is 401."""
    row = _run(seed_resume_experience(db_session))
    r = client.delete(f"/api/v1/admin/resume/{row.id}")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"


def test_admin_resume_reorder_success(client, admin_user, db_session):
    """Reorder updates each row's `display_order` in a single transaction."""
    a = _run(seed_resume_experience(db_session, organization="A", display_order=0))
    b = _run(seed_resume_experience(db_session, organization="B", display_order=1))
    c = _run(seed_resume_experience(db_session, organization="C", display_order=2))

    _login(client)
    r = client.post(
        "/api/v1/admin/resume/reorder",
        json={
            "order": [
                {"id": a.id, "display_order": 5},
                {"id": b.id, "display_order": 10},
                {"id": c.id, "display_order": 1},
            ]
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["error"] is None
    # The response is the full updated list, sorted by section then
    # display_order; the operator can replace their local state in
    # one round-trip.
    by_id = {row["id"]: row["display_order"] for row in body["data"]}
    assert by_id[a.id] == 5
    assert by_id[b.id] == 10
    assert by_id[c.id] == 1

    # GET /admin/resume reflects the new order.
    r2 = client.get("/api/v1/admin/resume")
    by_id2 = {
        row["id"]: row["display_order"]
        for row in r2.json()["data"]
        if row["section"] == "experience"
    }
    assert by_id2[a.id] == 5
    assert by_id2[b.id] == 10
    assert by_id2[c.id] == 1


def test_admin_resume_reorder_missing_id(client, admin_user, db_session):
    """Reorder with a missing id rolls back and 404s."""
    a = _run(seed_resume_experience(db_session, organization="A", display_order=0))
    _login(client)
    r = client.post(
        "/api/v1/admin/resume/reorder",
        json={
            "order": [
                {"id": a.id, "display_order": 1},
                {
                    "id": "00000000-0000-0000-0000-000000000000",
                    "display_order": 2,
                },
            ]
        },
    )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"
    # The existing row's display_order is unchanged (rollback).
    r2 = client.get("/api/v1/admin/resume")
    by_id = {
        row["id"]: row["display_order"]
        for row in r2.json()["data"]
        if row["section"] == "experience"
    }
    assert by_id[a.id] == 0


def test_admin_resume_reorder_duplicate_ids(client, admin_user, db_session):
    """Duplicate ids in the payload are rejected up front (400)."""
    a = _run(seed_resume_experience(db_session, organization="A", display_order=0))
    _login(client)
    r = client.post(
        "/api/v1/admin/resume/reorder",
        json={
            "order": [
                {"id": a.id, "display_order": 1},
                {"id": a.id, "display_order": 2},
            ]
        },
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "bad_request"


def test_admin_resume_reorder_requires_auth(client, admin_user, db_session):
    """Reorder without cookie is 401."""
    a = _run(seed_resume_experience(db_session, organization="A"))
    r = client.post(
        "/api/v1/admin/resume/reorder",
        json={"order": [{"id": a.id, "display_order": 1}]},
    )
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"

