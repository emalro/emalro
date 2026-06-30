"""Pydantic schemas for the admin read+list surface (PR #2).

PR #2 ships read+list only. Full CRUD (POST/PUT/DELETE) lands in
PR #6. The shapes here match what the admin list views consume
in PR #6: same field set, so the FE migration is trivial.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.i18n import LocalizedStr


# ---------------------------------------------------------------------------
# Admin project list item (mirrors the public shape + is_visible)
# ---------------------------------------------------------------------------


class AdminProjectListItem(BaseModel):
    """A row in the admin projects list (includes drafts)."""

    model_config = ConfigDict(extra="ignore")

    id: str
    slug: str
    title: LocalizedStr
    description: LocalizedStr
    tags: list[str] = Field(default_factory=list)
    image_url: Optional[str] = None
    is_visible: bool
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Admin blog list item
# ---------------------------------------------------------------------------


class AdminBlogListItem(BaseModel):
    """A row in the admin blog list (includes drafts)."""

    model_config = ConfigDict(extra="ignore")

    id: str
    slug: str
    title: LocalizedStr
    cover_image_url: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    is_visible: bool
    published_at: Optional[datetime] = None
    created_at: datetime


# ---------------------------------------------------------------------------
# Admin resume view (full rows, no `is_visible` filter)
# ---------------------------------------------------------------------------


class AdminResumeEntry(BaseModel):
    """Admin view of a single resume row.

    `title` and `description` are `LocalizedStr`. `subtitle` is a
    plain string (proper noun — organization / institution / platform).
    `extra` is the free-form JSON (used by the personal section to
    store the structured `PersonalData`).
    """

    model_config = ConfigDict(extra="ignore")

    id: str
    section: str
    display_order: int
    title: LocalizedStr
    subtitle: Optional[str] = None
    description: Optional[LocalizedStr] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    url: Optional[str] = None
    image_url: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    is_visible: bool
    extra: dict = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
