"""Pydantic schemas for the admin read+list surface (PR #2) and
the admin write surface (PR #6).

PR #2 ships read+list only. PR #6 adds full CRUD (POST/PUT/DELETE
on projects, blog, resume), PATCH on contacts (trash/restore/read
toggle + permanent delete), image upload + delete, and the
dashboard counts endpoint. The shapes here match what the admin
list views consume; the FE migration is trivial because the list
shape is unchanged and the create/update request bodies are
direct mirrors of the corresponding response shapes.
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


# ---------------------------------------------------------------------------
# Project CRUD (PR #6)
# ---------------------------------------------------------------------------


class AdminProjectCreateRequest(BaseModel):
    """Create body for `POST /admin/projects`.

    `id`, `slug`, `created_at`, `updated_at` are server-generated.
    `slug` is derived from `title.es` (falling back to `title.en`)
    and deduped with a `-2`, `-3`, ... suffix on conflict.
    `technologies` is a list of `LocalizedStr` (mirrors the public
    `ProjectResponse` shape). The server stores the title/description/
    technologies as JSON-encoded strings on the `Project` row.
    """

    model_config = ConfigDict(extra="forbid")

    title: LocalizedStr
    description: LocalizedStr
    technologies: list[LocalizedStr] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    image_url: Optional[str] = Field(default=None, max_length=500)
    github_url: Optional[str] = Field(default=None, max_length=500)
    demo_url: Optional[str] = Field(default=None, max_length=500)
    is_visible: bool = True


class AdminProjectUpdateRequest(BaseModel):
    """Update body for `PUT /admin/projects/{id}`.

    The full set of editable fields is required (PUT = full replace).
    `slug` is not editable in PR #6 (the slug is the public identifier;
    re-slugging is out of scope for the v1 admin).
    """

    model_config = ConfigDict(extra="forbid")

    title: LocalizedStr
    description: LocalizedStr
    technologies: list[LocalizedStr] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    image_url: Optional[str] = Field(default=None, max_length=500)
    github_url: Optional[str] = Field(default=None, max_length=500)
    demo_url: Optional[str] = Field(default=None, max_length=500)
    is_visible: bool = True
