"""Pydantic schemas for the public `/api/v1/cv` endpoint and the
shared `ResumeData` row.

The CV has four sections, grouped by the `section` column on
`ResumeData`:

- `personal` — single row; the row's `extra` JSON holds the
  structured `PersonalData` (name, role, summary, avatar, skills).
- `experience` — work history entries.
- `education` — education entries.
- `course` — courses and certifications.

The `/api/v1/cv` response groups these into a `CVResponse`. The
`/api/v1/admin/resume` (admin view) and the seed script consume
the row-level `ResumeEntryResponse` shape.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.i18n import LocalizedStr


# ---------------------------------------------------------------------------
# Personal section (stored in `ResumeData.extra` as JSON)
# ---------------------------------------------------------------------------


class PersonalData(BaseModel):
    """The personal-info block of the CV.

    `name`, `role`, `summary` are `LocalizedStr`. `hardSkills` and
    `softSkills` are `list[LocalizedStr]`. `avatar_url` is a plain
    string (local path or remote URL).
    """

    model_config = ConfigDict(extra="ignore")

    name: LocalizedStr
    role: LocalizedStr
    summary: LocalizedStr
    avatar_url: Optional[str] = None
    hardSkills: list[LocalizedStr] = Field(default_factory=list)
    softSkills: list[LocalizedStr] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Generic resume entry (experience, education, course)
# ---------------------------------------------------------------------------


class ResumeEntryResponse(BaseModel):
    """Row shape for a single resume entry.

    `title` and `description` are `LocalizedStr`. `subtitle` is a
    plain string (organization / institution / platform — proper
    nouns don't need translation). `start_date` / `end_date` are
    `YYYY-MM` strings; `end_date = null` means "current".
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

    @classmethod
    def from_row(cls, row) -> "ResumeEntryResponse":
        description = None
        if row.description:
            description = LocalizedStr.model_validate(json.loads(row.description))
        return cls(
            id=row.id,
            section=row.section,
            display_order=row.display_order,
            title=LocalizedStr.model_validate(json.loads(row.title)),
            subtitle=row.subtitle,
            description=description,
            start_date=row.start_date,
            end_date=row.end_date,
            url=row.url,
            image_url=row.image_url,
            tags=_parse_list(row.tags),
            is_visible=row.is_visible,
        )


# ---------------------------------------------------------------------------
# CV response (composed from rows)
# ---------------------------------------------------------------------------


class CVResponse(BaseModel):
    """The shape returned by `GET /api/v1/cv`.

    `personal` is a structured block (parsed from the `extra` JSON of
    the single `personal` row). The other three sections are lists of
    `ResumeEntryResponse`, sorted by `display_order` ascending.
    """

    model_config = ConfigDict(extra="ignore")

    personal: Optional[PersonalData] = None
    experience: list[ResumeEntryResponse] = Field(default_factory=list)
    education: list[ResumeEntryResponse] = Field(default_factory=list)
    courses: list[ResumeEntryResponse] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _accept_none(cls, v):  # pragma: no cover - trivial
        return v


def _parse_list(raw: str) -> list:
    if not raw:
        return []
    parsed = json.loads(raw)
    return parsed if isinstance(parsed, list) else []
