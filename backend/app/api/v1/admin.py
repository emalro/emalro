"""Admin read+list endpoints (PR #2) — projects + blog sub-routers (PR #6).

`GET /admin/projects` moved to `admin_projects.py` along with the
new `POST`/`PUT`/`DELETE` endpoints. `GET /admin/blog` moved to
`admin_blog.py` along with the new `POST`/`PUT`/`DELETE` endpoints.
This module is the aggregator for the resource sub-routers.

- `GET /admin/contacts`        — list non-trashed contact messages.
- `GET /admin/contacts/trash`  — list trashed contact messages.
- `GET /admin/resume`          — list ALL resume rows (no is_visible filter).

Plus the sub-routers mounted via `include_router`:

- `admin_projects.router` — projects CRUD (`/admin/projects`).
- `admin_blog.router`     — blog CRUD (`/admin/blog`).

The JWT is read from the `emalro_session` httpOnly cookie by
`get_current_admin`.
"""

from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col, select

from app.api.v1 import admin_blog, admin_projects
from app.core.db import get_session
from app.core.security import get_current_admin
from app.models.contact import ContactMessage
from app.models.resume import ResumeData
from app.schemas.admin import AdminResumeEntry
from app.schemas.contact import ContactListItem
from app.schemas.envelope import Envelope, PageMeta, PaginatedEnvelope
from app.schemas.i18n import LocalizedStr

router = APIRouter(
    prefix="/admin",
    dependencies=[Depends(get_current_admin)],
)


# ---------------------------------------------------------------------------
# GET /api/v1/admin/contacts
# ---------------------------------------------------------------------------


@router.get("/contacts", response_model=PaginatedEnvelope[ContactListItem])
async def admin_list_contacts(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> PaginatedEnvelope[ContactListItem]:
    """List non-trashed contact messages (inbox)."""
    base = select(ContactMessage).where(col(ContactMessage.deleted_at).is_(None))
    total = (await session.execute(base)).scalars().all()
    total_count = len(total)

    rows = (
        await session.execute(
            base.order_by(col(ContactMessage.received_at).desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
    ).scalars().all()

    items = [ContactListItem.model_validate(r, from_attributes=True) for r in rows]
    return PaginatedEnvelope[ContactListItem](
        data=items,
        meta=PageMeta(
            total=total_count, page=page, limit=limit, pages=_pages(total_count, limit)
        ),
    )


# ---------------------------------------------------------------------------
# GET /api/v1/admin/contacts/trash
# ---------------------------------------------------------------------------


@router.get("/contacts/trash", response_model=PaginatedEnvelope[ContactListItem])
async def admin_list_contacts_trash(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> PaginatedEnvelope[ContactListItem]:
    """List trashed contact messages (deleted_at IS NOT NULL)."""
    base = select(ContactMessage).where(col(ContactMessage.deleted_at).is_not(None))
    total = (await session.execute(base)).scalars().all()
    total_count = len(total)

    rows = (
        await session.execute(
            base.order_by(col(ContactMessage.received_at).desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
    ).scalars().all()

    items = [ContactListItem.model_validate(r, from_attributes=True) for r in rows]
    return PaginatedEnvelope[ContactListItem](
        data=items,
        meta=PageMeta(
            total=total_count, page=page, limit=limit, pages=_pages(total_count, limit)
        ),
    )


# ---------------------------------------------------------------------------
# GET /api/v1/admin/resume
# ---------------------------------------------------------------------------


@router.get("/resume", response_model=Envelope[list[AdminResumeEntry]])
async def admin_list_resume(
    session: AsyncSession = Depends(get_session),
) -> Envelope[list[AdminResumeEntry]]:
    """List all resume rows, no `is_visible` filter. Admin view."""
    rows = (
        await session.execute(
            select(ResumeData).order_by(
                col(ResumeData.section), col(ResumeData.display_order)
            )
        )
    ).scalars().all()

    items: list[AdminResumeEntry] = []
    for r in rows:
        try:
            title = LocalizedStr.model_validate(json.loads(r.title))
        except Exception:
            continue
        description = None
        if r.description:
            try:
                description = LocalizedStr.model_validate(json.loads(r.description))
            except Exception:
                description = None
        try:
            extra = json.loads(r.extra or "{}")
            if not isinstance(extra, dict):
                extra = {}
        except json.JSONDecodeError:
            extra = {}
        items.append(
            AdminResumeEntry(
                id=r.id,
                section=r.section,
                display_order=r.display_order,
                title=title,
                subtitle=r.subtitle,
                description=description,
                start_date=r.start_date,
                end_date=r.end_date,
                url=r.url,
                image_url=r.image_url,
                tags=_parse_list(r.tags),
                is_visible=r.is_visible,
                extra=extra,
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
        )
    return Envelope.ok(items)


# ---------------------------------------------------------------------------
# Sub-routers (mounted with their own prefixes)
# ---------------------------------------------------------------------------


router.include_router(admin_projects.router)
router.include_router(admin_blog.router)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _pages(total: int, limit: int) -> int:
    if total <= 0 or limit <= 0:
        return 0
    return (total + limit - 1) // limit


def _parse_list(raw: str) -> list:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []
