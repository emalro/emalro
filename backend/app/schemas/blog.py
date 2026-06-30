"""Pydantic response models for the public BlogPosts API.

Two shapes:

- `BlogPostSummary` is the list-item returned by `/api/v1/blog` and
  `/api/v1/explore`. The `excerpt` is computed from the first ~200
  chars of the Spanish `content` (per `data-explore-api` spec).
- `BlogPostDetail` is the full shape returned by `/api/v1/blog/{slug}`.
  It includes the full `content` (markdown, per language).
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.i18n import LocalizedStr


_EXCERPT_MAX = 200


class BlogPostSummary(BaseModel):
    """List-item shape for `/api/v1/blog` and `/api/v1/explore`."""

    model_config = ConfigDict(extra="ignore")

    id: str
    slug: str
    title: LocalizedStr
    excerpt: Optional[LocalizedStr] = None
    cover_image_url: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    is_visible: bool
    published_at: Optional[datetime] = None
    created_at: datetime

    @classmethod
    def from_row(cls, row, *, excerpt_chars: int = _EXCERPT_MAX) -> "BlogPostSummary":
        content = _parse_localized(row.content)
        excerpt = LocalizedStr(
            es=_truncate(content.es, excerpt_chars),
            en=_truncate(content.en, excerpt_chars),
        )
        return cls(
            id=row.id,
            slug=row.slug,
            title=_parse_localized(row.title),
            excerpt=excerpt,
            cover_image_url=row.cover_image_url,
            tags=_parse_list(row.tags),
            is_visible=row.is_visible,
            published_at=row.published_at,
            created_at=row.created_at,
        )


class BlogPostDetail(BaseModel):
    """Full shape for `/api/v1/blog/{slug}`."""

    model_config = ConfigDict(extra="ignore")

    id: str
    slug: str
    title: LocalizedStr
    content: LocalizedStr
    cover_image_url: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    is_visible: bool
    published_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_row(cls, row) -> "BlogPostDetail":
        return cls(
            id=row.id,
            slug=row.slug,
            title=_parse_localized(row.title),
            content=_parse_localized(row.content),
            cover_image_url=row.cover_image_url,
            tags=_parse_list(row.tags),
            is_visible=row.is_visible,
            published_at=row.published_at,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )


# --- helpers (shared with `project.py`) ---


def _parse_localized(raw: str) -> LocalizedStr:
    return LocalizedStr.model_validate(json.loads(raw))


def _parse_list(raw: str) -> list:
    if not raw:
        return []
    parsed = json.loads(raw)
    return parsed if isinstance(parsed, list) else []


def _truncate(s: str, n: int) -> str:
    if not s:
        return ""
    if len(s) <= n:
        return s
    return s[: n - 1].rstrip() + "\u2026"
