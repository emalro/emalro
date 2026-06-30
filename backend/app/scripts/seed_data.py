"""One-shot seed script: load the frontend JSON content into the DB.

Usage:
    python -m app.scripts.seed_data

Reads the static data files from `frontend/src/data/` and upserts
them into the `Projects`, `BlogPosts`, and `ResumeData` tables.
The script is idempotent: re-running it leaves existing rows
intact (matched by `slug` or `id`-equivalent identifier) and only
inserts rows that don't already exist.

Used for two purposes:
- Local dev: the operator can run this once to populate a fresh
  Supabase project with the MVP's content.
- CI smoke test: after `alembic upgrade head`, the verification
  gate runs this script to demonstrate the endpoints return real
  data (per the orchestrator's PR #2 brief).

Contact messages are NOT seeded — those come from real form
submissions. The script logs progress as it goes.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlmodel import select

from app.core.db import get_session_factory
from app.models.blog import BlogPost
from app.models.project import Project
from app.models.resume import ResumeData
from app.schemas.i18n import LocalizedStr

# Repo root: backend/app/scripts/seed_data.py -> ../../../..
REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / "frontend" / "src" / "data"


def _log(msg: str) -> None:
    print(f"[seed] {msg}", flush=True)


def _load_json(filename: str) -> Any:
    """Load a JSON file from the frontend data dir, or return None."""
    path = DATA_DIR / filename
    if not path.exists():
        _log(f"  ! {filename} not found, skipping")
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _ls(value: LocalizedStr) -> str:
    return value.model_dump_json()


def _slugify_localized(ls: LocalizedStr) -> str:
    """Derive an English-kebab slug from a LocalizedStr."""
    from app.services.slug import slugify
    return slugify(ls.es) or slugify(ls.en) or "item"


async def _upsert_projects(session, data: list[dict]) -> int:
    """Insert/upsert projects. Returns the number of new rows."""
    inserted = 0
    for entry in data:
        title = LocalizedStr.model_validate(entry["title"])
        description = LocalizedStr.model_validate(entry.get("description", {"es": "", "en": ""}))
        slug = entry.get("slug") or _slugify_localized(title)

        # Skip if a row with this slug already exists.
        existing = (
            await session.execute(select(Project).where(Project.slug == slug))
        ).scalar_one_or_none()
        if existing is not None:
            _log(f"  - project {slug!r} already exists, skipping")
            continue

        technologies_ls = [
            LocalizedStr.model_validate(t) for t in entry.get("technologies", [])
        ]
        technologies_json = "[" + ",".join(_ls(t) for t in technologies_ls) + "]"

        project = Project(
            id=entry.get("id") or None,  # use id from JSON if present
            slug=slug,
            title=_ls(title),
            description=_ls(description),
            technologies=technologies_json,
            tags=json.dumps(entry.get("tags", [])),
            image_url=entry.get("image_url"),
            github_url=entry.get("github_url"),
            demo_url=entry.get("demo_url"),
            is_visible=entry.get("is_visible", True),
            created_at=datetime.fromisoformat(entry["created_at"])
            if entry.get("created_at")
            else datetime.utcnow(),
        )
        session.add(project)
        inserted += 1
    return inserted


async def _upsert_blog_posts(session, data: list[dict]) -> int:
    """Insert/upsert blog posts. Returns the number of new rows."""
    inserted = 0
    for entry in data:
        title = LocalizedStr.model_validate(entry["title"])
        slug = entry.get("slug") or _slugify_localized(title)

        existing = (
            await session.execute(select(BlogPost).where(BlogPost.slug == slug))
        ).scalar_one_or_none()
        if existing is not None:
            _log(f"  - blog post {slug!r} already exists, skipping")
            continue

        content = LocalizedStr.model_validate(entry.get("content", {"es": "", "en": ""}))
        post = BlogPost(
            id=entry.get("id") or None,
            slug=slug,
            title=_ls(title),
            content=_ls(content),
            cover_image_url=entry.get("cover_image_url"),
            tags=json.dumps(entry.get("tags", [])),
            is_visible=entry.get("is_visible", True),
            published_at=datetime.fromisoformat(entry["published_at"])
            if entry.get("published_at")
            else datetime.utcnow(),
        )
        session.add(post)
        inserted += 1
    return inserted


async def _upsert_resume_personal(session, data: dict) -> int:
    """Insert the single personal row. Returns 1 if inserted, 0 if skipped."""
    # Check if a personal row already exists.
    existing = (
        await session.execute(
            select(ResumeData).where(ResumeData.section == "personal")
        )
    ).scalar_one_or_none()
    if existing is not None:
        _log("  - resume personal row already exists, skipping")
        return 0

    extra = {
        "name": data["name"],
        "role": data["role"],
        "summary": data["summary"],
        "avatar_url": data.get("avatar_url"),
        "hardSkills": data.get("hardSkills", []),
        "softSkills": data.get("softSkills", []),
    }
    row = ResumeData(
        section="personal",
        display_order=0,
        title=json.dumps(data["name"]),  # store name as title for the admin list
        extra=json.dumps(extra),
        is_visible=True,
    )
    session.add(row)
    return 1


async def _upsert_resume_experience(session, data: list[dict]) -> int:
    """Insert experience rows. Returns the number of new rows."""
    inserted = 0
    for i, entry in enumerate(data):
        # Match on subtitle (organization) + section. The MVP doesn't
        # have stable IDs for resume entries; we use order + subtitle
        # to detect duplicates.
        org = entry.get("organization", "")
        existing = (
            await session.execute(
                select(ResumeData).where(
                    ResumeData.section == "experience",
                    ResumeData.subtitle == org,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            _log(f"  - experience {org!r} already exists, skipping")
            continue

        row = ResumeData(
            section="experience",
            display_order=i,
            title=json.dumps(entry["role"]),
            subtitle=org,
            description=json.dumps(entry.get("description", {"es": "", "en": ""})),
            start_date=entry.get("start_date"),
            end_date=entry.get("end_date"),
            image_url=entry.get("logo_url"),
            is_visible=True,
        )
        session.add(row)
        inserted += 1
    return inserted


async def _upsert_resume_education(session, data: list[dict]) -> int:
    """Insert education rows. Returns the number of new rows."""
    inserted = 0
    for i, entry in enumerate(data):
        institution = entry.get("institution", "")
        existing = (
            await session.execute(
                select(ResumeData).where(
                    ResumeData.section == "education",
                    ResumeData.subtitle == institution,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            _log(f"  - education {institution!r} already exists, skipping")
            continue

        row = ResumeData(
            section="education",
            display_order=i,
            title=json.dumps(entry.get("degree", {"es": "", "en": ""})),
            subtitle=institution,
            description=json.dumps(entry.get("description", {"es": "", "en": ""})),
            start_date=entry.get("start_date"),
            end_date=entry.get("end_date"),
            image_url=entry.get("logo_url"),
            is_visible=True,
        )
        session.add(row)
        inserted += 1
    return inserted


async def _upsert_resume_courses(session, data: list[dict]) -> int:
    """Insert course rows. Returns the number of new rows."""
    inserted = 0
    for i, entry in enumerate(data):
        # Match on (platform, name).
        platform = entry.get("platform", "")
        name_obj = entry.get("name", {"es": "", "en": ""})
        title_str = json.dumps(name_obj, sort_keys=True)

        existing = (
            await session.execute(
                select(ResumeData).where(
                    ResumeData.section == "course",
                    ResumeData.subtitle == platform,
                    ResumeData.title == title_str,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            _log(
                f"  - course {platform}/{name_obj.get('en', '')!r} already exists, skipping"
            )
            continue

        row = ResumeData(
            section="course",
            display_order=i,
            title=title_str,
            subtitle=platform,
            url=entry.get("verification_url"),
            image_url=entry.get("platform_logo_url"),
            is_visible=True,
        )
        session.add(row)
        inserted += 1
    return inserted


async def _run() -> int:
    if not DATA_DIR.exists():
        _log(f"data dir not found: {DATA_DIR}")
        return 1

    _log(f"data dir: {DATA_DIR}")

    SessionLocal = get_session_factory()
    async with SessionLocal() as session:
        # Personal (single row).
        personal = _load_json("personal.json")
        if personal is not None:
            n = await _upsert_resume_personal(session, personal)
            _log(f"Personal: {n} row")

        # Projects.
        projects = _load_json("projects.json")
        if projects is not None:
            n = await _upsert_projects(session, projects)
            _log(f"Projects: {n} rows")

        # Blog posts (none in MVP data, but the script handles it).
        blog_posts = _load_json("blog.json")
        if blog_posts is None:
            blog_posts = []
        n = await _upsert_blog_posts(session, blog_posts)
        _log(f"BlogPosts: {n} rows")

        # Experience.
        experience = _load_json("experience.json")
        if experience is not None:
            n = await _upsert_resume_experience(session, experience)
            _log(f"Experience: {n} rows")

        # Education.
        education = _load_json("education.json")
        if education is not None:
            n = await _upsert_resume_education(session, education)
            _log(f"Education: {n} rows")

        # Courses.
        courses = _load_json("courses.json")
        if courses is not None:
            n = await _upsert_resume_courses(session, courses)
            _log(f"Courses: {n} rows")

        await session.commit()
        _log("done")
    return 0


def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    sys.exit(main())
