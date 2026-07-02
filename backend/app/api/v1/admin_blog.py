"""Admin blog endpoints: list + full CRUD.

- `GET /admin/blog`     — list ALL blog posts (including drafts).
- `POST /admin/blog`    — create. Server generates `id` (UUID),
  `slug` (kebab-case from `title.es` or `title.en`, deduped with a
  `-2`, `-3`, ... suffix on conflict), `created_at`, `updated_at`.
  If `is_visible=True` and `published_at` is null, the server sets
  `published_at` to now.
- `PUT /admin/blog/{id}` — full update. Updates `updated_at`. If
  `is_visible` flips from false to true and `published_at` is null,
  the server sets `published_at` to now.
- `DELETE /admin/blog/{id}` — hard delete. 204 on success.

Mounted at `/admin/blog` under the `get_current_admin` gate.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col, select

from app.core.db import get_session
from app.core.security import get_current_admin
from app.models.blog import BlogPost
from app.schemas.admin import AdminBlogCreateRequest, AdminBlogListItem, AdminBlogUpdateRequest
from app.schemas.envelope import Envelope, PageMeta, PaginatedEnvelope
from app.schemas.i18n import LocalizedStr
from app.services.slug import slugify

router = APIRouter(
    prefix="/blog",
    dependencies=[Depends(get_current_admin)],
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_uuid() -> str:
    return str(uuid.uuid4())


def _parse_list(raw: Optional[str]) -> list:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def _localized_to_json(value: LocalizedStr) -> str:
    return value.model_dump_json()


def _blog_to_list_item(row: BlogPost) -> AdminBlogListItem:
    return AdminBlogListItem(
        id=row.id,
        slug=row.slug,
        title=LocalizedStr.model_validate(json.loads(row.title)),
        cover_image_url=row.cover_image_url,
        tags=_parse_list(row.tags),
        is_visible=row.is_visible,
        published_at=row.published_at,
        created_at=row.created_at,
    )


async def _ensure_unique_slug(
    session: AsyncSession, base: str, exclude_id: Optional[str] = None
) -> str:
    """Return a slug derived from `base` that is not yet in use."""
    candidate = base
    n = 2
    while True:
        stmt = select(BlogPost).where(col(BlogPost.slug) == candidate)
        if exclude_id is not None:
            stmt = stmt.where(col(BlogPost.id) != exclude_id)
        existing = (await session.execute(stmt)).scalar_one_or_none()
        if existing is None:
            return candidate
        candidate = f"{base}-{n}"
        n += 1
        if n > 1000:  # pragma: no cover - defensive
            raise HTTPException(status_code=500, detail="server_error")


def _pages(total: int, limit: int) -> int:
    if total <= 0 or limit <= 0:
        return 0
    return (total + limit - 1) // limit


# ---------------------------------------------------------------------------
# GET /api/v1/admin/blog
# ---------------------------------------------------------------------------


@router.get("", response_model=PaginatedEnvelope[AdminBlogListItem])
async def admin_list_blog(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> PaginatedEnvelope[AdminBlogListItem]:
    """List all blog posts, including drafts. Admin view."""
    total_rows = (await session.execute(select(BlogPost))).scalars().all()
    total_count = len(total_rows)

    rows = (
        await session.execute(
            select(BlogPost)
            .order_by(col(BlogPost.published_at).desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
    ).scalars().all()

    items = [_blog_to_list_item(r) for r in rows]
    return PaginatedEnvelope[AdminBlogListItem](
        data=items,
        meta=PageMeta(
            total=total_count, page=page, limit=limit, pages=_pages(total_count, limit)
        ),
    )


# ---------------------------------------------------------------------------
# POST /api/v1/admin/blog
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=Envelope[AdminBlogListItem],
    status_code=status.HTTP_201_CREATED,
)
async def admin_create_blog_post(
    payload: AdminBlogCreateRequest,
    session: AsyncSession = Depends(get_session),
) -> Envelope[AdminBlogListItem]:
    """Create a new blog post.

    If `is_visible=True` and `published_at` is null, the server sets
    `published_at` to now. Otherwise the post is saved as a draft.
    """
    base_slug = slugify(payload.title.es) or slugify(payload.title.en) or "post"
    slug = await _ensure_unique_slug(session, base_slug)

    now = _utcnow()
    published_at = payload.published_at
    if published_at is None and payload.is_visible:
        published_at = now

    row = BlogPost(
        id=_new_uuid(),
        slug=slug,
        title=_localized_to_json(payload.title),
        content=_localized_to_json(payload.content),
        cover_image_url=payload.cover_image_url,
        tags=json.dumps(payload.tags),
        is_visible=payload.is_visible,
        published_at=published_at,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return Envelope.ok(_blog_to_list_item(row))


# ---------------------------------------------------------------------------
# PUT /api/v1/admin/blog/{id}
# ---------------------------------------------------------------------------


@router.put("/{post_id}", response_model=Envelope[AdminBlogListItem])
async def admin_update_blog_post(
    post_id: str,
    payload: AdminBlogUpdateRequest,
    session: AsyncSession = Depends(get_session),
) -> Envelope[AdminBlogListItem]:
    """Replace a blog post.

    `slug` is preserved. `updated_at` is set to now. If the post
    was previously a draft (`is_visible=False`) and the new
    payload flips it to `True` with no `published_at`, the server
    sets `published_at` to now.
    """
    row = (
        await session.execute(select(BlogPost).where(col(BlogPost.id) == post_id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="not_found")

    was_visible = bool(row.is_visible)
    new_published_at = payload.published_at
    if new_published_at is None and not was_visible and payload.is_visible:
        new_published_at = _utcnow()

    row.title = _localized_to_json(payload.title)
    row.content = _localized_to_json(payload.content)
    row.cover_image_url = payload.cover_image_url
    row.tags = json.dumps(payload.tags)
    row.is_visible = payload.is_visible
    row.published_at = new_published_at
    row.updated_at = _utcnow()
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return Envelope.ok(_blog_to_list_item(row))


# ---------------------------------------------------------------------------
# DELETE /api/v1/admin/blog/{id}
# ---------------------------------------------------------------------------


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_blog_post(
    post_id: str,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Hard-delete a blog post. 404 if it does not exist."""
    row = (
        await session.execute(select(BlogPost).where(col(BlogPost.id) == post_id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="not_found")
    await session.delete(row)
    await session.commit()
