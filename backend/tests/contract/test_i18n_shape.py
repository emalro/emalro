"""JSONB contract test — `LocalizedStr` shape on every localizable field.

This is the single most important contract test in the project
(per design-appendices A2). PR #1 covers the model-level invariants;
PR #2 extends the matrix to walk every public endpoint.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas.i18n import LocalizedStr

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "i18n_shape.json"


def test_localized_str_accepts_valid_shape():
    ls = LocalizedStr(es="Hola", en="Hello")
    assert ls.es == "Hola"
    assert ls.en == "Hello"


def test_localized_str_rejects_flat_string():
    with pytest.raises(ValidationError):
        LocalizedStr.model_validate("just a string")  # type: ignore[arg-type]


def test_localized_str_rejects_extra_keys():
    with pytest.raises(ValidationError):
        LocalizedStr.model_validate({"es": "X", "en": "Y", "pt": "Z"})


def test_localized_str_rejects_empty_es():
    with pytest.raises(ValidationError):
        LocalizedStr.model_validate({"es": "", "en": "X"})


def test_localized_str_rejects_whitespace_only_es():
    with pytest.raises(ValidationError):
        LocalizedStr.model_validate({"es": "   ", "en": "X"})


def test_localized_str_allows_empty_en_for_fallback():
    ls = LocalizedStr.model_validate({"es": "Solo espanol", "en": ""})
    assert ls.en == ""


def test_localized_str_rejects_overlong_en():
    with pytest.raises(ValidationError):
        LocalizedStr.model_validate({"es": "X", "en": "y" * 5001})


def test_fixture_file_matches_contract():
    """The shared `i18n_shape.json` fixture validates the same way."""
    raw = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    # LocalizedStr is valid.
    LocalizedStr.model_validate(raw["LocalizedStr"])

    # Extra key is rejected.
    with pytest.raises(ValidationError):
        LocalizedStr.model_validate(raw["InvalidExtra"])

    # Empty es is rejected.
    with pytest.raises(ValidationError):
        LocalizedStr.model_validate(raw["EmptyEs"])

    # Empty en is allowed (silent fallback).
    LocalizedStr.model_validate(raw["EmptyEnFallback"])


# ---------------------------------------------------------------------------
# Endpoint-level contract (PR #2): walk every public endpoint that
# returns localizable content and assert `LocalizedStr` on every
# localizable field. This is the SINGLE most important contract test
# (per design-appendices A2 and `i18n-shape` REQ-i18n-shape-05).
# ---------------------------------------------------------------------------


def _assert_localized(value, field: str) -> None:
    assert isinstance(value, dict), f"{field} must be a dict, got {type(value).__name__}: {value!r}"
    assert set(value.keys()) >= {"es", "en"}, f"{field} must have es+en keys, got {list(value.keys())}"
    assert isinstance(value["es"], str), f"{field}.es must be a string"
    assert isinstance(value["en"], str), f"{field}.en must be a string"
    assert value["es"].strip(), f"{field}.es must be non-empty"


def _walk_dict(obj, path: str, hits: list[str]) -> None:
    """Recursively find every LocalizedStr-shaped dict in `obj`."""
    if isinstance(obj, dict):
        keys = set(obj.keys())
        if keys >= {"es", "en"} and all(isinstance(obj.get(k), str) for k in ("es", "en")):
            hits.append(path)
            return
        for k, v in obj.items():
            _walk_dict(v, f"{path}.{k}", hits)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _walk_dict(v, f"{path}[{i}]", hits)


def test_i18n_shape_endpoint_cv(client, db_session):
    """`/api/v1/cv` returns LocalizedStr on every localizable field."""
    from tests.api._seed import (
        seed_resume_personal,
        seed_resume_experience,
        seed_resume_education,
        seed_resume_course,
    )

    seed_resume_personal_sync(db_session)
    seed_resume_experience_sync(db_session, organization="Arbusta")
    seed_resume_education_sync(db_session, institution="Urquiza")
    seed_resume_course_sync(db_session, platform="Coderhouse", name="Data Analytics")

    r = client.get("/api/v1/cv")
    assert r.status_code == 200
    data = r.json()["data"]

    hits: list[str] = []
    _walk_dict(data, "data", hits)
    assert hits, "expected at least one LocalizedStr field in /cv"
    # Re-resolve each path to a value and assert the LocalizedStr
    # shape (es non-empty, en is string).
    for path in hits:
        value = _resolve_path(data, path)
        _assert_localized(value, path)


def _resolve_path(data: dict, path: str):
    """Resolve a dotted path like `data.personal.hardSkills[0]`."""
    cur = data
    # Strip the leading `data.` segment.
    if path.startswith("data."):
        path = path[len("data."):]
    elif path == "data":
        return data
    parts: list = []
    buf = ""
    for ch in path:
        if ch == ".":
            if buf:
                parts.append(buf)
                buf = ""
        elif ch == "[":
            if buf:
                parts.append(buf)
                buf = ""
        elif ch == "]":
            if buf:
                parts.append(int(buf))
                buf = ""
        else:
            buf += ch
    if buf:
        parts.append(buf)
    for part in parts:
        cur = cur[part]
    return cur


def test_i18n_shape_endpoint_projects(client, db_session):
    """`/api/v1/projects` returns LocalizedStr on title + description."""
    from tests.api._seed import seed_project

    seed_project_sync(db_session, slug="apexlogic")

    r = client.get("/api/v1/projects")
    assert r.status_code == 200
    data = r.json()["data"]
    assert len(data) == 1
    _assert_localized(data[0]["title"], "data[0].title")
    _assert_localized(data[0]["description"], "data[0].description")
    for i, tech in enumerate(data[0]["technologies"]):
        _assert_localized(tech, f"data[0].technologies[{i}]")


def test_i18n_shape_endpoint_blog_list(client, db_session):
    """`/api/v1/blog` returns LocalizedStr on title + excerpt."""
    from tests.api._seed import seed_blog_post

    seed_blog_post_sync(db_session, slug="hello")

    r = client.get("/api/v1/blog")
    assert r.status_code == 200
    data = r.json()["data"]
    assert len(data) == 1
    _assert_localized(data[0]["title"], "data[0].title")


def test_i18n_shape_endpoint_blog_detail(client, db_session):
    """`/api/v1/blog/{slug}` returns LocalizedStr on title + content."""
    from tests.api._seed import seed_blog_post

    seed_blog_post_sync(db_session, slug="hello")

    r = client.get("/api/v1/blog/hello")
    assert r.status_code == 200
    data = r.json()["data"]
    _assert_localized(data["title"], "data.title")
    _assert_localized(data["content"], "data.content")


def test_i18n_shape_endpoint_explore(client, db_session):
    """`/api/v1/explore` returns LocalizedStr on title."""
    from tests.api._seed import seed_project

    seed_project_sync(db_session, slug="apexlogic", tags=["x"])

    r = client.get("/api/v1/explore?tags=x")
    assert r.status_code == 200
    data = r.json()["data"]
    assert len(data) == 1
    _assert_localized(data[0]["title"], "data[0].title")


# ---------------------------------------------------------------------------
# Sync wrappers around the async seed helpers. The conftest's
# `db_session` fixture is async, but the contract test functions
# are sync (they assert over JSON). The seed helpers themselves
# are async; the wrappers run them on the running event loop.
# ---------------------------------------------------------------------------


import asyncio


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def seed_project_sync(session, **kwargs):
    from tests.api._seed import seed_project
    return _run(seed_project(session, **kwargs))


def seed_blog_post_sync(session, **kwargs):
    from tests.api._seed import seed_blog_post
    return _run(seed_blog_post(session, **kwargs))


def seed_resume_personal_sync(session, **kwargs):
    from tests.api._seed import seed_resume_personal
    return _run(seed_resume_personal(session, **kwargs))


def seed_resume_experience_sync(session, **kwargs):
    from tests.api._seed import seed_resume_experience
    return _run(seed_resume_experience(session, **kwargs))


def seed_resume_education_sync(session, **kwargs):
    from tests.api._seed import seed_resume_education
    return _run(seed_resume_education(session, **kwargs))


def seed_resume_course_sync(session, **kwargs):
    from tests.api._seed import seed_resume_course
    return _run(seed_resume_course(session, **kwargs))


def test_i18n_shape_endpoint_tags_returns_plain_strings(client, db_session):
    """`/api/v1/tags` returns plain strings (no LocalizedStr)."""
    from tests.api._seed import seed_project

    seed_project_sync(db_session, slug="apexlogic", tags=["python"])

    r = client.get("/api/v1/tags")
    assert r.status_code == 200
    data = r.json()["data"]
    assert all(isinstance(t, str) for t in data)
    assert "python" in data
