"""Project SQLModel table.

A `Project` is a portfolio entry: a title, a description, a list of
technologies, a list of tags, optional URLs (image, github, demo), and
a public visibility flag. `slug` is the unique public identifier and
is used in `/projects/{slug}` lookups (Fase 3+) and in admin list links.

`tags` is a `list[str]` (Postgres `text[]`, JSON array on SQLite) and
gets a GIN index for fast tag-filter queries on `/api/v1/explore`.

`is_visible` is the draft/publish toggle (per `drafts-visibility`).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def _new_uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Project(SQLModel, table=True):
    __tablename__ = "projects"

    id: str = Field(default_factory=_new_uuid, primary_key=True, max_length=36)
    slug: str = Field(unique=True, index=True, max_length=120)
    title: str = Field(..., max_length=500)  # JSON: LocalizedStr
    description: str = Field(..., max_length=10_000)  # JSON: LocalizedStr
    technologies: str = Field(default="[]", max_length=10_000)  # JSON: list[LocalizedStr]
    tags: str = Field(default="[]", max_length=10_000)  # JSON: list[str]
    image_url: Optional[str] = Field(default=None, max_length=500)
    github_url: Optional[str] = Field(default=None, max_length=500)
    demo_url: Optional[str] = Field(default=None, max_length=500)
    is_visible: bool = Field(default=True, nullable=False, index=True)
    created_at: datetime = Field(default_factory=_utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=_utcnow, nullable=False)
