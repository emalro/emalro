"""Public read endpoints (no JWT required).

Six routes under `/api/v1/`:

- `GET /cv` — full CV (personal, experience, education, courses).
- `GET /projects` — visible projects, paginated, optional `?tag` filter.
- `GET /blog` — visible blog posts, paginated, optional `?tag` filter.
- `GET /blog/{slug}` — single visible blog post, 404 if draft.
- `GET /explore` — unified projects + blog posts, tag-filtered (AND/OR).
- `GET /tags` — distinct tags across visible content, sorted.

All responses use the standard envelope. The `is_visible` filter is
applied at the SQLModel query level (per `drafts-visibility` REQ-02).
HTTP cache headers (`Cache-Control` + `ETag`) and `If-None-Match`
304 handling are added by `EnvelopeMiddleware` in `app/middleware/`.
"""

from __future__ import annotations

import json
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col, or_, select

from app.core.db import get_session
from app.models.blog import BlogPost
from app.models.project import Project
from app.models.resume import ResumeData
from app.schemas.blog import BlogPostDetail, BlogPostSummary
from app.schemas.cv import (
    CVResponse,
    PersonalData,
    ResumeEntryResponse,
)
from app.schemas.envelope import Envelope, PageMeta, PaginatedEnvelope
from app.schemas.explore import ExploreItem, ExploreItemType, ExploreMatch
from app.schemas.i18n import LocalizedStr
from app.schemas.project import ProjectResponse
from app.services.sanitize import sanitize_localized, sanitize_markdown

router = APIRouter()


# ---------------------------------------------------------------------------
# GET /api/v1/cv
# ---------------------------------------------------------------------------


@router.get("/cv", response_model=Envelope[CVResponse])
async def get_cv(session: AsyncSession = Depends(get_session)) -> Envelope[CVResponse]:
    """Return the full CV grouped by section."""
    # Fetch every visible row. Section list is small (one per data
    # file: personal, experience, education, course) so a single
    # SELECT is fine.
    result = await session.execute(
        select(ResumeData)
        .where(col(ResumeData.is_visible).is_(True))
        .order_by(col(ResumeData.section), col(ResumeData.display_order))
    )
    rows = list(result.scalars())

    personal: Optional[PersonalData] = None
    experience: list[ResumeEntryResponse] = []
    education: list[ResumeEntryResponse] = []
    courses: list[ResumeEntryResponse] = []

    for row in rows:
        entry = ResumeEntryResponse.from_row(row)
        section = (row.section or "").lower()
        if section == "personal":
            # The personal row stores the structured `PersonalData`
            # in the `extra` JSON column.
            try:
                extra_raw = json.loads(row.extra or "{}")
            except json.JSONDecodeError:
                extra_raw = {}
            try:
                personal_obj = PersonalData.model_validate(extra_raw)
            except Exception:
                # Defensive: if `extra` is malformed, return None
                # for personal rather than 500ing the entire CV.
                personal_obj = None
            # Sanitize the markdown `summary` field on the public
            # read path so the response carries safe HTML. The admin
            # endpoint (see `app/api/v1/admin.py`) returns the raw
            # markdown so the operator can edit the source in the
            # CodeMirror editor (PR #6).
            if personal_obj is not None:
                personal_obj.summary = LocalizedStr.model_validate(
                    sanitize_localized(personal_obj.summary.model_dump())
                )
            personal = personal_obj
        elif section == "experience":
            # Sanitize the markdown `description` field on the
            # public read path. Admin endpoint keeps the raw source.
            if entry.description is not None:
                entry.description = LocalizedStr.model_validate(
                    sanitize_localized(entry.description.model_dump())
                )
            experience.append(entry)
        elif section == "education":
            if entry.description is not None:
                entry.description = LocalizedStr.model_validate(
                    sanitize_localized(entry.description.model_dump())
                )
            education.append(entry)
        elif section in ("course", "courses"):
            courses.append(entry)

    return Envelope.ok(
        CVResponse(
            personal=personal,
            experience=experience,
            education=education,
            courses=courses,
        )
    )


# ---------------------------------------------------------------------------
# GET /api/v1/projects
# ---------------------------------------------------------------------------


@router.get("/projects", response_model=PaginatedEnvelope[ProjectResponse])
async def list_projects(
    tag: Optional[str] = Query(default=None, max_length=64),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> PaginatedEnvelope[ProjectResponse]:
    """List visible projects, optionally filtered by a single tag."""
    base_query = select(Project).where(col(Project.is_visible).is_(True))
    count_query = select(Project).where(col(Project.is_visible).is_(True))
    if tag:
        # tags is a JSON-encoded list. Use LIKE on the JSON text
        # to find the tag (works on both Postgres and SQLite).
        like_pattern = f'%"{_escape_json_string(tag)}"%'
        base_query = base_query.where(col(Project.tags).like(like_pattern))
        count_query = count_query.where(col(Project.tags).like(like_pattern))

    total = (await session.execute(count_query)).scalars().all()
    total_count = len(total)

    rows = (
        await session.execute(
            base_query.order_by(col(Project.created_at).desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
    ).scalars().all()

    items = [ProjectResponse.from_row(r) for r in rows]
    # Sanitize the markdown `description` on the public read path so
    # the response carries safe HTML. Admin endpoint keeps the raw
    # source so the operator can edit the source markdown.
    for item in items:
        item.description = LocalizedStr.model_validate(
            sanitize_localized(item.description.model_dump())
        )
    return PaginatedEnvelope[ProjectResponse](
        data=items,
        meta=PageMeta(
            total=total_count,
            page=page,
            limit=limit,
            pages=_pages(total_count, limit),
        ),
    )


# ---------------------------------------------------------------------------
# GET /api/v1/blog
# ---------------------------------------------------------------------------


@router.get("/blog", response_model=PaginatedEnvelope[BlogPostSummary])
async def list_blog_posts(
    tag: Optional[str] = Query(default=None, max_length=64),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> PaginatedEnvelope[BlogPostSummary]:
    """List visible blog posts, optionally filtered by a single tag."""
    base_query = select(BlogPost).where(col(BlogPost.is_visible).is_(True))
    count_query = select(BlogPost).where(col(BlogPost.is_visible).is_(True))
    if tag:
        like_pattern = f'%"{_escape_json_string(tag)}"%'
        base_query = base_query.where(col(BlogPost.tags).like(like_pattern))
        count_query = count_query.where(col(BlogPost.tags).like(like_pattern))

    rows = (
        await session.execute(count_query)
    ).scalars().all()
    total_count = len(rows)

    rows = (
        await session.execute(
            base_query.order_by(col(BlogPost.published_at).desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
    ).scalars().all()

    items = [BlogPostSummary.from_row(r) for r in rows]
    return PaginatedEnvelope[BlogPostSummary](
        data=items,
        meta=PageMeta(
            total=total_count,
            page=page,
            limit=limit,
            pages=_pages(total_count, limit),
        ),
    )


# ---------------------------------------------------------------------------
# GET /api/v1/blog/{slug}
# ---------------------------------------------------------------------------


@router.get("/blog/{slug}", response_model=Envelope[BlogPostDetail])
async def get_blog_post(
    slug: str,
    session: AsyncSession = Depends(get_session),
) -> Envelope[BlogPostDetail]:
    """Return a single visible blog post. 404 for drafts or missing."""
    if not _valid_slug(slug):
        raise HTTPException(status_code=400, detail="invalid_parameter")

    result = await session.execute(
        select(BlogPost).where(
            col(BlogPost.slug) == slug,
            col(BlogPost.is_visible).is_(True),
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="not_found")
    return Envelope.ok(BlogPostDetail.from_row(row))


# ---------------------------------------------------------------------------
# GET /api/v1/explore
# ---------------------------------------------------------------------------


@router.get("/explore", response_model=PaginatedEnvelope[ExploreItem])
async def explore(
    tags: Optional[str] = Query(
        default=None,
        description="Comma-separated tag list (e.g. 'python,sql').",
    ),
    match: str = Query(default="and"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> PaginatedEnvelope[ExploreItem]:
    """Unified projects + blog posts, tag-filtered, paginated."""
    if match not in (m.value for m in ExploreMatch):
        raise HTTPException(
            status_code=400, detail="invalid_parameter"
        )
    match_enum = ExploreMatch(match)
    tag_list = [t.strip() for t in (tags or "").split(",") if t.strip()]

    project_items = await _projects_for_explore(session, tag_list, match_enum)
    blog_items = await _blog_posts_for_explore(session, tag_list, match_enum)

    # Interleave by date descending.
    combined = sorted(
        project_items + blog_items,
        key=lambda it: it["date"],
        reverse=True,
    )
    total = len(combined)
    start = (page - 1) * limit
    page_items = combined[start : start + limit]

    items = [ExploreItem.model_validate(it) for it in page_items]
    return PaginatedEnvelope[ExploreItem](
        data=items,
        meta=PageMeta(
            total=total,
            page=page,
            limit=limit,
            pages=_pages(total, limit),
        ),
    )


async def _projects_for_explore(
    session: AsyncSession,
    tag_list: list[str],
    match: ExploreMatch,
) -> list[dict]:
    """Build `ExploreItem`-shaped dicts for visible projects."""
    base = select(Project).where(col(Project.is_visible).is_(True))
    base = _apply_tag_filter(base, Project.tags, tag_list, match)
    rows = (await session.execute(base.order_by(col(Project.created_at).desc()))).scalars().all()
    out: list[dict] = []
    for r in rows:
        try:
            title = LocalizedStr.model_validate(json.loads(r.title))
            description = LocalizedStr.model_validate(json.loads(r.description))
        except Exception:
            continue
        # Sanitize the description on the public read path.
        sanitized_description = LocalizedStr.model_validate(
            sanitize_localized(description.model_dump())
        )
        out.append(
            {
                "type": ExploreItemType.PROJECT.value,
                "id": r.id,
                "slug": r.slug,
                "title": title,
                "excerpt": sanitized_description,
                "tags": _parse_list(r.tags),
                "date": r.created_at,
                "cover_image_url": None,
                "image_url": r.image_url,
            }
        )
    return out


async def _blog_posts_for_explore(
    session: AsyncSession,
    tag_list: list[str],
    match: ExploreMatch,
) -> list[dict]:
    """Build `ExploreItem`-shaped dicts for visible blog posts."""
    base = select(BlogPost).where(col(BlogPost.is_visible).is_(True))
    base = _apply_tag_filter(base, BlogPost.tags, tag_list, match)
    rows = (
        await session.execute(base.order_by(col(BlogPost.published_at).desc()))
    ).scalars().all()
    out: list[dict] = []
    for r in rows:
        try:
            title = LocalizedStr.model_validate(json.loads(r.title))
            content = LocalizedStr.model_validate(json.loads(r.content))
        except Exception:
            continue
        excerpt = LocalizedStr(
            es=(content.es[:199] + "\u2026") if len(content.es) > 200 else content.es,
            en=(content.en[:199] + "\u2026") if len(content.en) > 200 else content.en,
        )
        out.append(
            {
                "type": ExploreItemType.BLOG_POST.value,
                "id": r.id,
                "slug": r.slug,
                "title": title,
                "excerpt": excerpt,
                "tags": _parse_list(r.tags),
                "date": r.published_at or r.created_at,
                "cover_image_url": r.cover_image_url,
                "image_url": None,
            }
        )
    return out


# ---------------------------------------------------------------------------
# GET /api/v1/tags
# ---------------------------------------------------------------------------


@router.get("/tags", response_model=Envelope[list[str]])
async def list_tags(
    session: AsyncSession = Depends(get_session),
) -> Envelope[list[str]]:
    """Distinct, sorted tags across visible projects + blog posts."""
    project_rows = (
        await session.execute(
            select(Project.tags).where(col(Project.is_visible).is_(True))
        )
    ).scalars().all()
    blog_rows = (
        await session.execute(
            select(BlogPost.tags).where(col(BlogPost.is_visible).is_(True))
        )
    ).scalars().all()

    seen: set[str] = set()
    for raw in (*project_rows, *blog_rows):
        for tag in _parse_list(raw):
            if isinstance(tag, str) and tag:
                seen.add(tag)

    return Envelope.ok(sorted(seen, key=lambda s: s.lower()))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _pages(total: int, limit: int) -> int:
    if total <= 0 or limit <= 0:
        return 0
    return (total + limit - 1) // limit


_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,119}$")


def _valid_slug(slug: str) -> bool:
    return bool(_SLUG_RE.match(slug))


def _escape_json_string(s: str) -> str:
    """Escape a string for safe inclusion in a JSON literal (for LIKE)."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _parse_list(raw: str) -> list:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def _apply_tag_filter(query, tags_column, tag_list: list[str], match: ExploreMatch):
    """Add a tag-filter clause to a SQLModel select.

    `tags` is stored as a JSON-encoded string. We use SQL `LIKE` to
    find rows whose JSON text contains each tag. This works on both
    Postgres and SQLite; the GIN index on Postgres is a future
    optimization (not in PR #2 scope).
    """
    if not tag_list:
        return query
    if match == ExploreMatch.OR:
        clauses = [
            col(tags_column).like(f'%"{_escape_json_string(t)}"%')
            for t in tag_list
        ]
        return query.where(or_(*clauses))
    # AND: every tag must be present.
    for t in tag_list:
        query = query.where(
            col(tags_column).like(f'%"{_escape_json_string(t)}"%')
        )
    return query
