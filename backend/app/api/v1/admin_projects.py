"""Admin projects endpoints: list + full CRUD.

- `GET /admin/projects` — list ALL projects (including drafts).
- `POST /admin/projects` — create. Server generates `id` (UUID),
  `slug` (kebab-case from `title.es` or `title.en`, deduped with a
  `-2`, `-3`, ... suffix on conflict), `created_at`, `updated_at`.
- `PUT /admin/projects/{id}` — full update. Updates `updated_at`.
- `DELETE /admin/projects/{id}` — hard delete. 204 on success.

The router is mounted at `/admin/projects` and gated by the
`get_current_admin` cookie auth dependency (added in `admin.py`).
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
from app.models.project import Project
from app.schemas.admin import (
    AdminProjectCreateRequest,
    AdminProjectListItem,
    AdminProjectUpdateRequest,
)
from app.schemas.envelope import Envelope, PageMeta, PaginatedEnvelope
from app.schemas.i18n import LocalizedStr
from app.services.slug import slugify

router = APIRouter(
    prefix="/projects",
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


async def _ensure_unique_slug(session: AsyncSession, base: str, exclude_id: Optional[str] = None) -> str:
    """Return a slug derived from `base` that is not yet in use.

    Appends `-2`, `-3`, ... until a free slug is found. The original
    `base` is tried first. If `exclude_id` is provided, that row is
    excluded from the conflict check (used by PUT to keep its own slug
    when the title hasn't changed).
    """
    candidate = base
    n = 2
    while True:
        stmt = select(Project).where(col(Project.slug) == candidate)
        if exclude_id is not None:
            stmt = stmt.where(col(Project.id) != exclude_id)
        existing = (await session.execute(stmt)).scalar_one_or_none()
        if existing is None:
            return candidate
        candidate = f"{base}-{n}"
        n += 1
        if n > 1000:  # pragma: no cover - defensive
            raise HTTPException(status_code=500, detail="server_error")


def _localized_to_json(value: LocalizedStr) -> str:
    return value.model_dump_json()


def _project_to_list_item(row: Project) -> AdminProjectListItem:
    return AdminProjectListItem(
        id=row.id,
        slug=row.slug,
        title=LocalizedStr.model_validate(json.loads(row.title)),
        description=LocalizedStr.model_validate(json.loads(row.description)),
        tags=_parse_list(row.tags),
        image_url=row.image_url,
        is_visible=row.is_visible,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _pages(total: int, limit: int) -> int:
    if total <= 0 or limit <= 0:
        return 0
    return (total + limit - 1) // limit


# ---------------------------------------------------------------------------
# GET /api/v1/admin/projects
# ---------------------------------------------------------------------------


@router.get("", response_model=PaginatedEnvelope[AdminProjectListItem])
async def admin_list_projects(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> PaginatedEnvelope[AdminProjectListItem]:
    """List all projects, including drafts. Admin view."""
    total = (await session.execute(select(Project))).scalars().all()
    total_count = len(total)

    rows = (
        await session.execute(
            select(Project)
            .order_by(col(Project.created_at).desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
    ).scalars().all()

    items = [_project_to_list_item(r) for r in rows]
    return PaginatedEnvelope[AdminProjectListItem](
        data=items,
        meta=PageMeta(
            total=total_count, page=page, limit=limit, pages=_pages(total_count, limit)
        ),
    )


# ---------------------------------------------------------------------------
# POST /api/v1/admin/projects
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=Envelope[AdminProjectListItem],
    status_code=status.HTTP_201_CREATED,
)
async def admin_create_project(
    payload: AdminProjectCreateRequest,
    session: AsyncSession = Depends(get_session),
) -> Envelope[AdminProjectListItem]:
    """Create a new project row.

    The `slug` is derived from `payload.title.es` (falling back to
    `payload.title.en`) and deduped against the existing rows.
    `id`, `created_at`, and `updated_at` are server-generated.
    """
    base_slug = slugify(payload.title.es) or slugify(payload.title.en) or "project"
    slug = await _ensure_unique_slug(session, base_slug)

    technologies_json = (
        "[" + ",".join(t.model_dump_json() for t in payload.technologies) + "]"
    )

    now = _utcnow()
    row = Project(
        id=_new_uuid(),
        slug=slug,
        title=_localized_to_json(payload.title),
        description=_localized_to_json(payload.description),
        technologies=technologies_json,
        tags=json.dumps(payload.tags),
        image_url=payload.image_url,
        github_url=payload.github_url,
        demo_url=payload.demo_url,
        is_visible=payload.is_visible,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return Envelope.ok(_project_to_list_item(row))


# ---------------------------------------------------------------------------
# PUT /api/v1/admin/projects/{id}
# ---------------------------------------------------------------------------


@router.put("/{project_id}", response_model=Envelope[AdminProjectListItem])
async def admin_update_project(
    project_id: str,
    payload: AdminProjectUpdateRequest,
    session: AsyncSession = Depends(get_session),
) -> Envelope[AdminProjectListItem]:
    """Replace a project row.

    All editable fields are overwritten. `slug` is preserved (the
    public identifier is not editable in v1). `updated_at` is set
    to now. Returns 404 if the project does not exist.
    """
    row = (
        await session.execute(select(Project).where(col(Project.id) == project_id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="not_found")

    technologies_json = (
        "[" + ",".join(t.model_dump_json() for t in payload.technologies) + "]"
    )
    row.title = _localized_to_json(payload.title)
    row.description = _localized_to_json(payload.description)
    row.technologies = technologies_json
    row.tags = json.dumps(payload.tags)
    row.image_url = payload.image_url
    row.github_url = payload.github_url
    row.demo_url = payload.demo_url
    row.is_visible = payload.is_visible
    row.updated_at = _utcnow()
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return Envelope.ok(_project_to_list_item(row))


# ---------------------------------------------------------------------------
# DELETE /api/v1/admin/projects/{id}
# ---------------------------------------------------------------------------


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_project(
    project_id: str,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Hard-delete a project row. 404 if it does not exist.

    In v1 there is no soft-delete on projects; the `image_url` is
    not auto-orphaned (that's PR #6+ work — see the `image-upload`
    spec for the orphan-mitigation rules).
    """
    row = (
        await session.execute(select(Project).where(col(Project.id) == project_id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="not_found")
    await session.delete(row)
    await session.commit()
