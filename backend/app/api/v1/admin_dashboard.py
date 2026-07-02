"""Admin dashboard counts endpoint.

`GET /api/v1/admin/dashboard/counts` — single endpoint that returns
all the card counts the admin dashboard renders in one round-trip.

Response shape (Envelope[AdminDashboardCounts]):

    {
      "data": {
        "projects": { "published": 4, "drafts": 1 },
        "blog":     { "published": 8, "drafts": 2 },
        "contacts": { "total": 25, "unread": 3, "trashed": 0 },
        "resume":   { "total": 12 }
      },
      "error": null
    }

This endpoint replaces the four `useQuery` calls the PR #5b
`Dashboard.tsx` makes on initial render. The PR #5b FE ships first
(so the SPA shell can be reviewed without the backend), and the
PR #6b FE migration swaps the four queries for this single call.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col, select

from app.core.db import get_session
from app.core.security import get_current_admin
from app.models.blog import BlogPost
from app.models.contact import ContactMessage
from app.models.project import Project
from app.models.resume import ResumeData
from app.schemas.admin import (
    AdminDashboardCounts,
    BlogCounts,
    ContactsCounts,
    ProjectsCounts,
    ResumeCounts,
)
from app.schemas.envelope import Envelope


router = APIRouter(
    prefix="/dashboard",
    dependencies=[Depends(get_current_admin)],
)


async def _count(session: AsyncSession, stmt) -> int:
    """Run a `select(func.count(...))` and return the scalar int."""
    result = await session.execute(stmt)
    return int(result.scalar() or 0)


@router.get("/counts", response_model=Envelope[AdminDashboardCounts])
async def admin_dashboard_counts(
    session: AsyncSession = Depends(get_session),
) -> Envelope[AdminDashboardCounts]:
    """Return the dashboard card counts in one round-trip.

    Four SQL count queries, one per resource. Cheap on the
    Supabase pooler (each is a covering index scan) and a single
    Pydantic serialization on the way out.
    """
    # Projects: published = is_visible, drafts = not is_visible.
    projects_published = await _count(
        session,
        select(func.count(col(Project.id))).where(col(Project.is_visible).is_(True)),
    )
    projects_drafts = await _count(
        session,
        select(func.count(col(Project.id))).where(col(Project.is_visible).is_(False)),
    )

    # Blog: same split. Drafts are is_visible=False regardless of
    # `published_at` (a published post is_visible=True stays in
    # the published bucket; a draft may have a published_at set
    # already, in which case it's still a draft by `is_visible`).
    blog_published = await _count(
        session,
        select(func.count(col(BlogPost.id))).where(col(BlogPost.is_visible).is_(True)),
    )
    blog_drafts = await _count(
        session,
        select(func.count(col(BlogPost.id))).where(col(BlogPost.is_visible).is_(False)),
    )

    # Contacts: total = inbox, unread = inbox AND read_at IS NULL,
    # trashed = deleted_at IS NOT NULL.
    contacts_total = await _count(
        session,
        select(func.count(col(ContactMessage.id))).where(
            col(ContactMessage.deleted_at).is_(None)
        ),
    )
    contacts_unread = await _count(
        session,
        select(func.count(col(ContactMessage.id))).where(
            col(ContactMessage.deleted_at).is_(None),
            col(ContactMessage.read_at).is_(None),
        ),
    )
    contacts_trashed = await _count(
        session,
        select(func.count(col(ContactMessage.id))).where(
            col(ContactMessage.deleted_at).is_not(None)
        ),
    )

    # Resume: single total (no draft / published split today; the
    # CV is rendered as one block on the public site).
    resume_total = await _count(
        session,
        select(func.count(col(ResumeData.id))),
    )

    return Envelope.ok(
        AdminDashboardCounts(
            projects=ProjectsCounts(
                published=projects_published, drafts=projects_drafts
            ),
            blog=BlogCounts(published=blog_published, drafts=blog_drafts),
            contacts=ContactsCounts(
                total=contacts_total,
                unread=contacts_unread,
                trashed=contacts_trashed,
            ),
            resume=ResumeCounts(total=resume_total),
        )
    )
