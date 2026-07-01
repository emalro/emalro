"""Admin aggregator: thin wrapper that mounts the resource sub-routers.

Each sub-router is mounted at its own prefix and carries the
`get_current_admin` cookie auth dependency:

- `admin_projects.router` — projects CRUD (`/admin/projects`).
- `admin_blog.router`     — blog CRUD (`/admin/blog`).
- `admin_contacts.router` — contacts list/trash/PATCH/DELETE (`/admin/contacts`).
- `admin_resume.router`   — resume CRUD + reorder (`/admin/resume`).

The aggregator also adds a defense-in-depth `get_current_admin`
dependency at its own level so any future sub-router that forgets
to declare it is still gated.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.v1 import (
    admin_blog,
    admin_contacts,
    admin_projects,
    admin_resume,
)
from app.core.security import get_current_admin

router = APIRouter(
    prefix="/admin",
    dependencies=[Depends(get_current_admin)],
)

router.include_router(admin_projects.router)
router.include_router(admin_blog.router)
router.include_router(admin_contacts.router)
router.include_router(admin_resume.router)
