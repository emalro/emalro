"""Admin contact-messages endpoints: list + soft-delete + permanent delete.

- `GET /admin/contacts`           — list non-trashed messages (inbox).
- `GET /admin/contacts/trash`     — list trashed messages.
- `PATCH /admin/contacts/{id}`    — body `{deleted: bool}`. Trashes or
  restores the message (sets/clears `deleted_at`).
- `PATCH /admin/contacts/{id}/read` — body `{read: bool}`. Marks the
  message as read/unread (sets/clears `read_at`).
- `DELETE /admin/contacts/{id}`   — permanent delete. 204 on success.

The contact message is a public submission (no FK to admin users).
Soft-delete uses `deleted_at IS NULL`; trash endpoint returns rows
where `deleted_at IS NOT NULL`. Hard delete removes the row entirely.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col, select

from app.core.db import get_session
from app.core.security import get_current_admin
from app.models.contact import ContactMessage
from app.schemas.contact import ContactListItem
from app.schemas.envelope import Envelope, PageMeta, PaginatedEnvelope


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


router = APIRouter(
    prefix="/contacts",
    dependencies=[Depends(get_current_admin)],
)


# ---------------------------------------------------------------------------
# PATCH bodies
# ---------------------------------------------------------------------------


class AdminContactPatchRequest(BaseModel):
    """Body for `PATCH /admin/contacts/{id}` and `/read`.

    `extra=forbid` keeps the surface area tight: only the two
    toggles the operator can act on. `deleted` and `read` map
    directly to the `deleted_at` and `read_at` timestamps on the
    `ContactMessage` row.
    """

    model_config = ConfigDict(extra="forbid")

    deleted: bool = Field(..., description="Trash (true) or restore (false) the message")
    read: bool = Field(..., description="Mark the message as read (true) or unread (false)")


def _contact_to_list_item(row: ContactMessage) -> ContactListItem:
    return ContactListItem.model_validate(row, from_attributes=True)


def _pages(total: int, limit: int) -> int:
    if total <= 0 or limit <= 0:
        return 0
    return (total + limit - 1) // limit


# ---------------------------------------------------------------------------
# GET /api/v1/admin/contacts
# ---------------------------------------------------------------------------


@router.get("", response_model=PaginatedEnvelope[ContactListItem])
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

    items = [_contact_to_list_item(r) for r in rows]
    return PaginatedEnvelope[ContactListItem](
        data=items,
        meta=PageMeta(
            total=total_count, page=page, limit=limit, pages=_pages(total_count, limit)
        ),
    )


# ---------------------------------------------------------------------------
# GET /api/v1/admin/contacts/trash
# ---------------------------------------------------------------------------


@router.get("/trash", response_model=PaginatedEnvelope[ContactListItem])
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

    items = [_contact_to_list_item(r) for r in rows]
    return PaginatedEnvelope[ContactListItem](
        data=items,
        meta=PageMeta(
            total=total_count, page=page, limit=limit, pages=_pages(total_count, limit)
        ),
    )


# ---------------------------------------------------------------------------
# PATCH /api/v1/admin/contacts/{id}
# ---------------------------------------------------------------------------


@router.patch("/{contact_id}", response_model=Envelope[ContactListItem])
async def admin_patch_contact(
    contact_id: str,
    payload: AdminContactPatchRequest,
    session: AsyncSession = Depends(get_session),
) -> Envelope[ContactListItem]:
    """Trash or restore + mark read/unread in a single PATCH.

    The endpoint accepts BOTH the `deleted` and `read` toggles in
    the same body so the operator can chain operations (e.g.
    "trash and mark as read" after handling the message). 404 if
    the message does not exist.
    """
    row = (
        await session.execute(
            select(ContactMessage).where(col(ContactMessage.id) == contact_id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="not_found")

    now = _utcnow()
    row.deleted_at = now if payload.deleted else None
    row.read_at = now if payload.read else None
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return Envelope.ok(_contact_to_list_item(row))


# ---------------------------------------------------------------------------
# PATCH /api/v1/admin/contacts/{id}/read
# ---------------------------------------------------------------------------


@router.patch("/{contact_id}/read", response_model=Envelope[ContactListItem])
async def admin_patch_contact_read(
    contact_id: str,
    payload: AdminContactPatchRequest,
    session: AsyncSession = Depends(get_session),
) -> Envelope[ContactListItem]:
    """Read-only toggle endpoint.

    The combined `PATCH /admin/contacts/{id}` already accepts the
    `read` field, but the dedicated `/read` route is the one the
    TanStack table in PR #6b calls when the operator clicks the
    "mark as read" button on a single row. Keeping the two paths
    distinct lets the FE use a focused endpoint for the common
    case while the combined PATCH handles bulk flows.
    """
    row = (
        await session.execute(
            select(ContactMessage).where(col(ContactMessage.id) == contact_id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="not_found")

    now = _utcnow()
    row.read_at = now if payload.read else None
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return Envelope.ok(_contact_to_list_item(row))


# ---------------------------------------------------------------------------
# DELETE /api/v1/admin/contacts/{id}
# ---------------------------------------------------------------------------


@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_contact(
    contact_id: str,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Permanent delete. 404 if it does not exist.

    Soft-delete (`PATCH /admin/contacts/{id}` with `deleted: true`)
    is the operator's primary path; this endpoint is for irreversible
    cleanup (e.g., spam or after the 30-day retention window).
    """
    row = (
        await session.execute(
            select(ContactMessage).where(col(ContactMessage.id) == contact_id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="not_found")
    await session.delete(row)
    await session.commit()
