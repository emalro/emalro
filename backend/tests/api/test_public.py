"""Public read endpoints: envelope, LocalizedStr, is_visible, ETag/304.

Walks every public route mounted in `app/api/v1/public.py`:

- GET /api/v1/cv
- GET /api/v1/projects
- GET /api/v1/blog
- GET /api/v1/blog/{slug}
- GET /api/v1/explore
- GET /api/v1/tags

Mandatory tests (per the orchestrator's brief):
- JSONB contract on every public endpoint (LocalizedStr shape).
- Envelope shape on every response.
- Public list+detail happy path.
- is_visible filter (drafts excluded from public, hidden from detail).
- ETag + 304 on If-None-Match.
- The 6th contact POST from same IP returns 429 (test_contacts.py).
- Validation errors return 422 envelope (test_contacts.py).
- Honeypot returns 400 (test_contacts.py).
- Admin read+list with auth (test_admin.py).
"""

from __future__ import annotations

import pytest

from tests.api._seed import (
    seed_blog_post,
    seed_project,
    seed_resume_course,
    seed_resume_education,
    seed_resume_experience,
    seed_resume_personal,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _assert_envelope_shape(body: dict) -> None:
    assert set(body.keys()) >= {"data", "error"}, body
    assert body["error"] is None


def _assert_localized(value, field: str) -> None:
    """Assert that `value` is a `LocalizedStr` dict with es+en keys."""
    assert isinstance(value, dict), f"{field} is not a dict: {value!r}"
    assert "es" in value, f"{field} missing 'es' key"
    assert "en" in value, f"{field} missing 'en' key"
    assert isinstance(value["es"], str), f"{field}.es is not a string"
    assert isinstance(value["en"], str), f"{field}.en is not a string"
    assert value["es"].strip(), f"{field}.es is empty"


# ---------------------------------------------------------------------------
# GET /api/v1/cv
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cv_returns_envelope_and_sections(client, db_session):
    await seed_resume_personal(db_session)
    await seed_resume_experience(db_session, organization="Arbusta")
    await seed_resume_education(db_session, institution="Urquiza")
    await seed_resume_course(db_session, platform="Coderhouse", name="Data Analytics")

    r = client.get("/api/v1/cv")
    assert r.status_code == 200
    body = r.json()
    _assert_envelope_shape(body)
    data = body["data"]
    assert "personal" in data
    assert "experience" in data
    assert "education" in data
    assert "courses" in data
    # LocalizedStr contract: personal.name and role are LocalizedStr.
    assert "es" in data["personal"]["name"]
    assert "en" in data["personal"]["name"]
    # Experience entry title is LocalizedStr.
    assert "es" in data["experience"][0]["title"]


@pytest.mark.asyncio
async def test_cv_excludes_hidden_resume_entries(client, db_session):
    """REQ-drafts-visibility-06: hidden experience entry is excluded."""
    await seed_resume_personal(db_session)
    await seed_resume_experience(db_session, organization="Visible Co", display_order=0)
    await seed_resume_experience(
        db_session, organization="Hidden Co", display_order=1, is_visible=False
    )

    r = client.get("/api/v1/cv")
    body = r.json()
    data = body["data"]
    orgs = [e["subtitle"] for e in data["experience"]]
    assert "Visible Co" in orgs
    assert "Hidden Co" not in orgs


# ---------------------------------------------------------------------------
# GET /api/v1/projects
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_projects_list_returns_visible_only(client, db_session):
    await seed_project(db_session, slug="visible", tags=["excel"])
    await seed_project(db_session, slug="draft", tags=["excel"], is_visible=False)

    r = client.get("/api/v1/projects")
    assert r.status_code == 200
    body = r.json()
    _assert_envelope_shape(body)
    data = body["data"]
    assert len(data) == 1
    assert data[0]["slug"] == "visible"
    # meta pagination block
    assert body["meta"]["total"] == 1
    assert body["meta"]["page"] == 1


@pytest.mark.asyncio
async def test_projects_localizedstr_shape(client, db_session):
    """REQ-api-public-02: every localizable field is a LocalizedStr."""
    await seed_project(db_session, slug="apexlogic")

    r = client.get("/api/v1/projects")
    data = r.json()["data"]
    assert len(data) == 1
    _assert_localized(data[0]["title"], "title")
    _assert_localized(data[0]["description"], "description")
    for tech in data[0]["technologies"]:
        _assert_localized(tech, "technologies[]")


@pytest.mark.asyncio
async def test_projects_tag_filter(client, db_session):
    await seed_project(db_session, slug="excel-proj", tags=["excel"])
    await seed_project(db_session, slug="sql-proj", tags=["sql"])

    r = client.get("/api/v1/projects?tag=excel")
    body = r.json()
    slugs = [p["slug"] for p in body["data"]]
    assert slugs == ["excel-proj"]


# ---------------------------------------------------------------------------
# GET /api/v1/blog
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_blog_list_returns_visible_only(client, db_session):
    await seed_blog_post(db_session, slug="visible-post", tags=["intro"])
    await seed_blog_post(
        db_session, slug="draft-post", tags=["intro"], is_visible=False
    )

    r = client.get("/api/v1/blog")
    body = r.json()
    data = body["data"]
    slugs = [p["slug"] for p in data]
    assert "visible-post" in slugs
    assert "draft-post" not in slugs


@pytest.mark.asyncio
async def test_blog_localizedstr_shape(client, db_session):
    """REQ-api-public-02: blog list item has LocalizedStr title + excerpt."""
    await seed_blog_post(db_session, slug="hello")

    r = client.get("/api/v1/blog")
    data = r.json()["data"]
    assert len(data) == 1
    _assert_localized(data[0]["title"], "title")
    # excerpt is computed from content; may be a LocalizedStr or None
    if data[0]["excerpt"] is not None:
        _assert_localized(data[0]["excerpt"], "excerpt")


# ---------------------------------------------------------------------------
# GET /api/v1/blog/{slug}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_blog_detail_returns_localizedstr_body(client, db_session):
    await seed_blog_post(db_session, slug="hello")
    r = client.get("/api/v1/blog/hello")
    assert r.status_code == 200
    body = r.json()
    _assert_envelope_shape(body)
    data = body["data"]
    _assert_localized(data["title"], "title")
    _assert_localized(data["content"], "content")


@pytest.mark.asyncio
async def test_blog_detail_draft_returns_404(client, db_session):
    """REQ-drafts-visibility-02: drafts return 404 on the public detail."""
    await seed_blog_post(db_session, slug="draft-post", is_visible=False)
    r = client.get("/api/v1/blog/draft-post")
    assert r.status_code == 404
    body = r.json()
    assert body["data"] is None
    assert body["error"]["code"] == "not_found"


@pytest.mark.asyncio
async def test_blog_detail_nonexistent_returns_404(client):
    r = client.get("/api/v1/blog/this-does-not-exist")
    assert r.status_code == 404
    body = r.json()
    assert body["error"]["code"] == "not_found"


@pytest.mark.asyncio
async def test_blog_detail_invalid_slug_returns_400(client):
    r = client.get("/api/v1/blog/" + ("x" * 200))
    # Either 400 (invalid slug shape) or 404 (not found) is acceptable.
    assert r.status_code in (400, 404)


# ---------------------------------------------------------------------------
# ETag + 304
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_public_endpoint_returns_etag_and_304(client, db_session):
    await seed_project(db_session, slug="apexlogic")

    r1 = client.get("/api/v1/projects")
    assert r1.status_code == 200
    etag = r1.headers.get("etag")
    assert etag is not None
    assert etag.startswith('"') and etag.endswith('"')

    r2 = client.get("/api/v1/projects", headers={"If-None-Match": etag})
    assert r2.status_code == 304
    # 304 must echo the ETag header.
    assert r2.headers.get("etag") == etag


@pytest.mark.asyncio
async def test_cv_endpoint_returns_etag_and_304(client, db_session):
    await seed_resume_personal(db_session)

    r1 = client.get("/api/v1/cv")
    etag = r1.headers.get("etag")
    assert etag is not None

    r2 = client.get("/api/v1/cv", headers={"If-None-Match": etag})
    assert r2.status_code == 304


# ---------------------------------------------------------------------------
# GET /api/v1/explore
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_explore_unified_returns_projects_and_blog(client, db_session):
    await seed_project(db_session, slug="proj-1", tags=["python"])
    await seed_blog_post(db_session, slug="post-1", tags=["python"])

    r = client.get("/api/v1/explore?tags=python")
    body = r.json()
    assert "data" in body
    types = {item["type"] for item in body["data"]}
    assert "project" in types
    assert "blog_post" in types
    # meta block
    assert body["meta"]["total"] == 2


@pytest.mark.asyncio
async def test_explore_and_match(client, db_session):
    await seed_project(
        db_session, slug="both", tags=["python", "sql"]
    )
    await seed_project(
        db_session, slug="only-py", tags=["python"]
    )

    r = client.get("/api/v1/explore?tags=python,sql&match=and")
    body = r.json()
    slugs = [item["slug"] for item in body["data"]]
    assert "both" in slugs
    assert "only-py" not in slugs


@pytest.mark.asyncio
async def test_explore_or_match(client, db_session):
    await seed_project(
        db_session, slug="both", tags=["python", "sql"]
    )
    await seed_project(
        db_session, slug="only-py", tags=["python"]
    )
    await seed_project(
        db_session, slug="only-sql", tags=["sql"]
    )

    r = client.get("/api/v1/explore?tags=python,sql&match=or")
    body = r.json()
    slugs = sorted([item["slug"] for item in body["data"]])
    assert slugs == ["both", "only-py", "only-sql"]


@pytest.mark.asyncio
async def test_explore_default_match_is_and(client, db_session):
    """REQ-data-explore-api-02: default match is AND."""
    await seed_project(
        db_session, slug="both", tags=["python", "sql"]
    )
    await seed_project(
        db_session, slug="only-py", tags=["python"]
    )

    r = client.get("/api/v1/explore?tags=python,sql")
    body = r.json()
    slugs = [item["slug"] for item in body["data"]]
    assert "both" in slugs
    assert "only-py" not in slugs


@pytest.mark.asyncio
async def test_explore_invalid_match_returns_400(client, db_session):
    r = client.get("/api/v1/explore?tags=python&match=invalid")
    assert r.status_code == 400
    body = r.json()
    assert body["error"]["code"] == "invalid_parameter"


@pytest.mark.asyncio
async def test_explore_excludes_drafts(client, db_session):
    await seed_project(db_session, slug="visible", tags=["x"], is_visible=True)
    await seed_project(db_session, slug="draft", tags=["x"], is_visible=False)
    await seed_blog_post(db_session, slug="visible-post", tags=["x"], is_visible=True)
    await seed_blog_post(
        db_session, slug="draft-post", tags=["x"], is_visible=False
    )

    r = client.get("/api/v1/explore?tags=x")
    slugs = [item["slug"] for item in r.json()["data"]]
    assert "visible" in slugs
    assert "visible-post" in slugs
    assert "draft" not in slugs
    assert "draft-post" not in slugs


@pytest.mark.asyncio
async def test_explore_pagination_meta(client, db_session):
    for i in range(5):
        await seed_project(
            db_session, slug=f"p-{i}", tags=["common"]
        )
    r = client.get("/api/v1/explore?tags=common&page=1&limit=2")
    body = r.json()
    assert len(body["data"]) == 2
    assert body["meta"]["total"] == 5
    assert body["meta"]["page"] == 1
    assert body["meta"]["limit"] == 2
    assert body["meta"]["pages"] == 3


@pytest.mark.asyncio
async def test_explore_empty_tags_returns_recent(client, db_session):
    """REQ-data-explore-api-04: no tags returns the most recent content."""
    await seed_project(db_session, slug="recent-1")
    await seed_blog_post(db_session, slug="recent-2")
    r = client.get("/api/v1/explore")
    body = r.json()
    assert body["meta"]["total"] == 2


@pytest.mark.asyncio
async def test_explore_response_uses_localizedstr(client, db_session):
    """REQ-data-explore-api-05: explore items have LocalizedStr title."""
    await seed_project(db_session, slug="p-1", tags=["x"])
    r = client.get("/api/v1/explore?tags=x")
    data = r.json()["data"]
    assert len(data) == 1
    _assert_localized(data[0]["title"], "title")


# ---------------------------------------------------------------------------
# GET /api/v1/tags
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tags_dedup_and_sort(client, db_session):
    await seed_project(
        db_session,
        slug="p-1",
        tags=["python", "sql"],
    )
    await seed_project(
        db_session,
        slug="p-2",
        tags=["python", "data"],
    )
    await seed_blog_post(
        db_session,
        slug="post-1",
        tags=["data", "intro"],
    )

    r = client.get("/api/v1/tags")
    body = r.json()
    data = body["data"]
    # Each tag appears once.
    assert len(data) == len(set(data))
    # Sorted alphabetically (case-insensitive).
    assert data == sorted(data, key=lambda s: s.lower())
    assert "python" in data
    assert "sql" in data
    assert "data" in data
    assert "intro" in data


@pytest.mark.asyncio
async def test_tags_excludes_drafts(client, db_session):
    await seed_project(
        db_session,
        slug="visible",
        tags=["visible-tag"],
    )
    await seed_project(
        db_session,
        slug="draft",
        tags=["draft-tag"],
        is_visible=False,
    )
    r = client.get("/api/v1/tags")
    data = r.json()["data"]
    assert "visible-tag" in data
    assert "draft-tag" not in data


# ---------------------------------------------------------------------------
# Public read sanitization (content polish).
#
# The public read path sanitizes the markdown `description` and
# `summary` fields so the response carries safe HTML. The admin read
# path keeps the raw markdown so the operator can edit the source
# (PR #6 will wire the CodeMirror editor). See
# `tests/api/test_admin.py` for the matching admin-side assertions.
# ---------------------------------------------------------------------------


from app.schemas.i18n import LocalizedStr


@pytest.mark.asyncio
async def test_cv_sanitizes_personal_summary(client, db_session):
    """`/api/v1/cv` returns sanitized HTML for `personal.summary`."""
    from tests.api._seed import seed_resume_personal

    await seed_resume_personal(
        db_session,
        extra={
            "name": {"es": "Emanuel", "en": "Emanuel"},
            "role": {"es": "Data Analyst", "en": "Data Analyst"},
            "summary": {
                "es": "**Hello** and [see](https://example.com) for context.",
                "en": "**Hello** and [see](https://example.com) for context.",
            },
            "avatar_url": "/img/avatar.svg",
            "hardSkills": [],
            "softSkills": [],
        },
    )

    r = client.get("/api/v1/cv")
    data = r.json()["data"]
    summary = data["personal"]["summary"]
    # Markdown was rendered to HTML.
    assert "<strong>Hello</strong>" in summary["es"]
    assert 'href="https://example.com"' in summary["es"]
    # Wrapped in a <p>.
    assert summary["es"].startswith("<p>")


@pytest.mark.asyncio
async def test_cv_sanitizes_experience_description(client, db_session):
    """`/api/v1/cv` returns sanitized bullet list for experience descriptions."""
    from tests.api._seed import seed_resume_experience

    await seed_resume_experience(
        db_session,
        organization="Acme",
        # Custom description with markdown bullets.
    )
    # Override the description after the default seed: re-fetch the row
    # and patch the description directly.
    from sqlmodel import col, select
    from app.models.resume import ResumeData

    row = (
        await db_session.execute(
            select(ResumeData).where(col(ResumeData.organization if False else ResumeData.subtitle) == "Acme")  # type: ignore[arg-type]
        )
    ).scalars().one()
    row.description = LocalizedStr(
        es="* clean data\n* build reports",
        en="* clean data\n* build reports",
    ).model_dump_json()
    await db_session.commit()

    r = client.get("/api/v1/cv")
    data = r.json()["data"]
    desc = data["experience"][0]["description"]
    assert desc["es"] == "<ul><li>clean data</li><li>build reports</li></ul>"


@pytest.mark.asyncio
async def test_cv_sanitizes_education_description(client, db_session):
    """`/api/v1/cv` returns sanitized education description."""
    from tests.api._seed import seed_resume_education

    await seed_resume_education(
        db_session,
        institution="Urquiza",
    )
    from sqlmodel import col, select
    from app.models.resume import ResumeData
    from app.schemas.i18n import LocalizedStr

    row = (
        await db_session.execute(
            select(ResumeData).where(col(ResumeData.subtitle) == "Urquiza")
        )
    ).scalars().one()
    row.description = LocalizedStr(
        es="**Specialized** training in *UML*.",
        en="**Specialized** training in *UML*.",
    ).model_dump_json()
    await db_session.commit()

    r = client.get("/api/v1/cv")
    data = r.json()["data"]
    desc = data["education"][0]["description"]
    assert "<strong>Specialized</strong>" in desc["es"]
    assert "<em>UML</em>" in desc["es"]


@pytest.mark.asyncio
async def test_projects_endpoint_sanitizes_description(client, db_session):
    """`/api/v1/projects` returns sanitized HTML for project descriptions."""
    from tests.api._seed import seed_project

    await seed_project(
        db_session,
        slug="apexlogic",
        description=LocalizedStr(
            es="* Cleaning data\n* Building reports",
            en="* Cleaning data\n* Building reports",
        ),
    )

    r = client.get("/api/v1/projects")
    data = r.json()["data"]
    assert len(data) == 1
    desc = data[0]["description"]
    assert desc["es"] == "<ul><li>Cleaning data</li><li>Building reports</li></ul>"


@pytest.mark.asyncio
async def test_projects_endpoint_strips_xss_in_description(client, db_session):
    """Public project description is sanitized against XSS payloads."""
    from tests.api._seed import seed_project

    await seed_project(
        db_session,
        slug="evil",
        description=LocalizedStr(
            es="[click](javascript:alert(1))",
            en="[click](javascript:alert(1))",
        ),
    )

    r = client.get("/api/v1/projects")
    data = r.json()["data"]
    desc = data[0]["description"]
    assert "javascript:" not in desc["es"]
    assert "<a " not in desc["es"]
    # The label is preserved as plain text.
    assert "click" in desc["es"]


@pytest.mark.asyncio
async def test_explore_sanitizes_project_excerpt(client, db_session):
    """`/api/v1/explore` returns sanitized project excerpt (built from description)."""
    from tests.api._seed import seed_project

    await seed_project(
        db_session,
        slug="p-1",
        tags=["x"],
        description=LocalizedStr(
            es="* Cleans data\n* Builds reports",
            en="* Cleans data\n* Builds reports",
        ),
    )

    r = client.get("/api/v1/explore?tags=x")
    data = r.json()["data"]
    assert len(data) == 1
    excerpt = data[0]["excerpt"]
    assert excerpt is not None
    assert "<ul>" in excerpt["es"]
    assert "<li>Cleans data</li>" in excerpt["es"]

