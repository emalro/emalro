"""Admin read+list endpoints (PR #2) — projects/blog/contacts sub-routers (PR #6).

`GET /admin/projects`, `GET /admin/blog`, and the contact endpoints
(GET inbox, GET trash, PATCH, DELETE) have moved into their own
sub-routers. This module is now the aggregator for the resource
sub-routers.

- `GET /admin/resume` — list ALL resume rows (no is_visible filter).

Plus the sub-routers mounted via `include_router`:

- `admin_projects.router` — projects CRUD (`/admin/projects`).
- `admin_blog.router`     — blog CRUD (`/admin/blog`).
- `admin_contacts.router` — contacts list/trash/PATCH/DELETE (`/admin/contacts`).

The JWT is read from the `emalro_session` httpOnly cookie by
`get_current_admin`.
"""

from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col, select

from app.api.v1 import admin_blog, admin_contacts, admin_projects
from app.core.db import get_session
from app.core.security import get_current_admin
from app.models.resume import ResumeData
from app.schemas.admin import AdminResumeEntry
from app.schemas.envelope import Envelope
from app.schemas.i18n import LocalizedStr

router = APIRouter(
    prefix="/admin",
    dependencies=[Depends(get_current_admin)],
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
router.include_router(admin_contacts.router)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_list(raw: str) -> list:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []
