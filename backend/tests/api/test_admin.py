"""Admin read+list endpoints: 401 (no auth) and 200 (with auth).

Mandatory tests (per the orchestrator's brief):
- 401 with `unauthorized` envelope on missing/invalid auth.
- 200 with envelope on valid JWT (cookie) for each list endpoint.

Endpoints covered (PR #2 scope: read+list only):
- GET /api/v1/admin/projects
- GET /api/v1/admin/blog
- GET /api/v1/admin/contacts
- GET /api/v1/admin/contacts/trash
- GET /api/v1/admin/resume
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
