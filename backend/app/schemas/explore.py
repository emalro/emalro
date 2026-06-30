"""Pydantic schemas for the `/api/v1/explore` and `/api/v1/tags`
endpoints (per `data-explore-api` spec).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.i18n import LocalizedStr


class ExploreMatch(str, Enum):
    """Query parameter for the `match` filter on `/api/v1/explore`."""

    AND = "and"
    OR = "or"


class ExploreItemType(str, Enum):
    """Discriminator for unified explore results."""

    PROJECT = "project"
    BLOG_POST = "blog_post"


class ExploreItem(BaseModel):
    """A single item in the unified explore result list.

    `title` and `excerpt` are `LocalizedStr`. `date` is the sort key
    (`published_at` for blog posts, `created_at` for projects).
    """

    model_config = ConfigDict(extra="ignore")

    type: ExploreItemType
    id: str
    slug: str
    title: LocalizedStr
    excerpt: Optional[LocalizedStr] = None
    tags: list[str] = Field(default_factory=list)
    date: datetime
    cover_image_url: Optional[str] = None
    image_url: Optional[str] = None


class ExploreQuery(BaseModel):
    """Validated query parameters for `/api/v1/explore`."""

    model_config = ConfigDict(extra="ignore")

    tags: list[str] = Field(default_factory=list)
    match: ExploreMatch = ExploreMatch.AND
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=20, ge=1, le=100)

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, v):  # pragma: no cover - trivial coercion
        if isinstance(v, dict) and "tags" in v:
            raw_tags = v.get("tags")
            if isinstance(raw_tags, str):
                v["tags"] = [t.strip() for t in raw_tags.split(",") if t.strip()]
        return v
