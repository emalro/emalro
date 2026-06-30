"""BlogPost SQLModel table.

A `BlogPost` is a blog entry with bilingual title + content (both are
`LocalizedStr` JSONB). The body is markdown, sanitized server-side
before persist (see `app/services/sanitize.py` and `api-admin` REQ-06
in `api-admin` for the full flow; PR #6 wires the admin POST).

`slug` is the public URL identifier. `tags` is `list[str]` and gets a
GIN index for the `/api/v1/explore` tag filter.

`is_visible` is the draft/publish toggle. `published_at` is the sort
key for the public blog list (descending).
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


class BlogPost(SQLModel, table=True):
    __tablename__ = "blog_posts"

    id: str = Field(default_factory=_new_uuid, primary_key=True, max_length=36)
    slug: str = Field(unique=True, index=True, max_length=120)
    title: str = Field(..., max_length=500)  # JSON: LocalizedStr
    content: str = Field(..., max_length=200_000)  # JSON: LocalizedStr
    cover_image_url: Optional[str] = Field(default=None, max_length=500)
    tags: str = Field(default="[]", max_length=10_000)  # JSON: list[str]
    is_visible: bool = Field(default=True, nullable=False, index=True)
    published_at: Optional[datetime] = Field(default=None, nullable=True, index=True)
    created_at: datetime = Field(default_factory=_utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=_utcnow, nullable=False)
