"""Pydantic response/request models for the public Projects API.

`ProjectResponse` is the canonical shape returned by every endpoint
that exposes a project: `/api/v1/projects` list, `/api/v1/explore`,
and (in PR #6) the admin list. The `tags` field is a plain list of
strings; the `title` and `description` are `LocalizedStr`; the
`technologies` field is a list of `LocalizedStr`.

The model decouples the SQLModel `Project` table (which stores JSONB
as raw strings) from the wire shape (which uses Pydantic `LocalizedStr`
and proper `list[str]`). A small adapter (`from_row`) in the router
layer converts row -> response.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.i18n import LocalizedStr


class ProjectResponse(BaseModel):
    """The public-facing shape of a project row."""

    model_config = ConfigDict(extra="ignore")

    id: str
    slug: str
    title: LocalizedStr
    description: LocalizedStr
    technologies: list[LocalizedStr] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    image_url: Optional[str] = None
    github_url: Optional[str] = None
    demo_url: Optional[str] = None
    is_visible: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_row(cls, row) -> "ProjectResponse":
        """Build a response from a SQLModel `Project` row.

        The row stores `title`, `description`, `technologies`, and
        `tags` as JSON-encoded strings; this helper parses them.
        """
        return cls(
            id=row.id,
            slug=row.slug,
            title=_parse_localized(row.title),
            description=_parse_localized(row.description),
            technologies=[LocalizedStr.model_validate(t) for t in _parse_list(row.technologies)],
            tags=_parse_list(row.tags),
            image_url=row.image_url,
            github_url=row.github_url,
            demo_url=row.demo_url,
            is_visible=row.is_visible,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )


def _parse_localized(raw: str) -> LocalizedStr:
    return LocalizedStr.model_validate(json.loads(raw))


def _parse_list(raw: str) -> list:
    if not raw:
        return []
    parsed = json.loads(raw)
    return parsed if isinstance(parsed, list) else []
