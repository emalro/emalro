"""Admin resume endpoints: list + full CRUD + reorder.

- `GET /admin/resume`            — list ALL resume rows (no is_visible filter).
- `POST /admin/resume`           — create. Server generates `id`,
  `created_at`, `updated_at`. `display_order` defaults to
  `max(display_order) + 1` in the same section when omitted.
- `PUT /admin/resume/{id}`       — full update. Updates `updated_at`.
- `DELETE /admin/resume/{id}`    — hard delete. 204 on success.
- `POST /admin/resume/reorder`   — body `{order: [{id, display_order}, ...]}`.
  Updates the `display_order` of each row in one transaction.
  Returns the full updated resume list (Envelope shape).

`ResumeData` is the most complex model in the schema (free-form
`extra` JSON, section-based grouping, `display_order` for sort).
The create/update request accepts the full editable set.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col, func, select

from app.core.db import get_session
from app.core.security import get_current_admin
from app.models.resume import ResumeData
from app.schemas.admin import (
    AdminResumeCreateRequest,
    AdminResumeEntry,
    AdminResumeReorderRequest,
    AdminResumeUpdateRequest,
)
from app.schemas.envelope import Envelope
from app.schemas.i18n import LocalizedStr


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_uuid() -> str:
    return str(uuid.uuid4())


router = APIRouter(
    prefix="/resume",
    dependencies=[Depends(get_current_admin)],
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


def _resume_to_entry(row: ResumeData) -> AdminResumeEntry:
    try:
        title = LocalizedStr.model_validate(json.loads(row.title))
    except Exception:
        # The list endpoint skips broken rows; the create/update
        # path raises 422 upstream, so a broken title here means
        # the seed data is corrupt. We still return a stub rather
        # than 500 — the admin can re-edit the row.
        title = LocalizedStr(es=row.title, en="")
    description = None
    if row.description:
        try:
            description = LocalizedStr.model_validate(json.loads(row.description))
        except Exception:
            description = None
    try:
        extra = json.loads(row.extra or "{}")
        if not isinstance(extra, dict):
            extra = {}
    except json.JSONDecodeError:
        extra = {}
    return AdminResumeEntry(
        id=row.id,
        section=row.section,
        display_order=row.display_order,
        title=title,
        subtitle=row.subtitle,
        description=description,
        start_date=row.start_date,
        end_date=row.end_date,
        url=row.url,
        image_url=row.image_url,
        tags=_parse_list(row.tags),
        is_visible=row.is_visible,
        extra=extra,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def _next_display_order(session: AsyncSession, section: str) -> int:
    """Return `max(display_order) + 1` in the given section, or 0."""
    stmt = select(func.max(col(ResumeData.display_order))).where(
        col(ResumeData.section) == section
    )
    row = (await session.execute(stmt)).scalar_one()
    return int(row or 0) + 1


# ---------------------------------------------------------------------------
# GET /api/v1/admin/resume
# ---------------------------------------------------------------------------


@router.get("", response_model=Envelope[list[AdminResumeEntry]])
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
# POST /api/v1/admin/resume
# ---------------------------------------------------------------------------


@router.post("", response_model=Envelope[AdminResumeEntry], status_code=status.HTTP_201_CREATED)
async def admin_create_resume(
    payload: AdminResumeCreateRequest,
    session: AsyncSession = Depends(get_session),
) -> Envelope[AdminResumeEntry]:
    """Create a new resume row.

    `display_order` defaults to `max(display_order) + 1` in the
    same section (so a new experience row lands at the end of
    that section's list). The server generates `id`, `created_at`,
    and `updated_at`.
    """
    display_order = (
        payload.display_order
        if payload.display_order is not None
        else await _next_display_order(session, payload.section)
    )

    now = _utcnow()
    row = ResumeData(
        id=_new_uuid(),
        section=payload.section,
        display_order=display_order,
        title=_localized_to_json(payload.title),
        subtitle=payload.subtitle,
        description=_localized_to_json(payload.description) if payload.description else None,
        start_date=payload.start_date,
        end_date=payload.end_date,
        url=payload.url,
        image_url=payload.image_url,
        tags=json.dumps(payload.tags),
        is_visible=payload.is_visible,
        extra=json.dumps(payload.extra or {}),
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return Envelope.ok(_resume_to_entry(row))


# ---------------------------------------------------------------------------
# PUT /api/v1/admin/resume/{id}
# ---------------------------------------------------------------------------


@router.put("/{resume_id}", response_model=Envelope[AdminResumeEntry])
async def admin_update_resume(
    resume_id: str,
    payload: AdminResumeUpdateRequest,
    session: AsyncSession = Depends(get_session),
) -> Envelope[AdminResumeEntry]:
    """Replace a resume row. 404 if not found."""
    row = (
        await session.execute(select(ResumeData).where(col(ResumeData.id) == resume_id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="not_found")

    row.section = payload.section
    row.display_order = payload.display_order
    row.title = _localized_to_json(payload.title)
    row.subtitle = payload.subtitle
    row.description = (
        _localized_to_json(payload.description) if payload.description else None
    )
    row.start_date = payload.start_date
    row.end_date = payload.end_date
    row.url = payload.url
    row.image_url = payload.image_url
    row.tags = json.dumps(payload.tags)
    row.is_visible = payload.is_visible
    row.extra = json.dumps(payload.extra or {})
    row.updated_at = _utcnow()
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return Envelope.ok(_resume_to_entry(row))


# ---------------------------------------------------------------------------
# DELETE /api/v1/admin/resume/{id}
# ---------------------------------------------------------------------------


@router.delete("/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_resume(
    resume_id: str,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Hard-delete a resume row. 404 if not found."""
    row = (
        await session.execute(select(ResumeData).where(col(ResumeData.id) == resume_id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="not_found")
    await session.delete(row)
    await session.commit()


# ---------------------------------------------------------------------------
# POST /api/v1/admin/resume/reorder
# ---------------------------------------------------------------------------


@router.post("/reorder", response_model=Envelope[list[AdminResumeEntry]])
async def admin_reorder_resume(
    payload: AdminResumeReorderRequest,
    session: AsyncSession = Depends(get_session),
) -> Envelope[list[AdminResumeEntry]]:
    """Update the `display_order` of every row in the payload.

    All updates run in a single transaction; if any row id is
    missing, the entire operation is rolled back and a 404 is
    returned. On success, the full resume list (matching the
    `GET /admin/resume` shape) is returned so the FE can replace
    its local state in one round-trip.
    """
    ids = [item.id for item in payload.order]
    if len(set(ids)) != len(ids):
        # Duplicate ids in the payload — that would corrupt the
        # sort order, so reject the request up front.
        raise HTTPException(status_code=400, detail="bad_request")

    # Load every targeted row in one query.
    rows = (
        await session.execute(
            select(ResumeData).where(col(ResumeData.id).in_(ids))
        )
    ).scalars().all()
    by_id = {r.id: r for r in rows}

    if len(by_id) != len(ids):
        raise HTTPException(status_code=404, detail="not_found")

    now = _utcnow()
    for item in payload.order:
        row = by_id[item.id]
        row.display_order = item.display_order
        row.updated_at = now
        session.add(row)
    await session.commit()

    # Return the full list (sorted for stability).
    all_rows = (
        await session.execute(
            select(ResumeData).order_by(
                col(ResumeData.section), col(ResumeData.display_order)
            )
        )
    ).scalars().all()
    return Envelope.ok([_resume_to_entry(r) for r in all_rows])
