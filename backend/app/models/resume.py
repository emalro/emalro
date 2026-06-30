"""ResumeData SQLModel table.

A single `ResumeData` row represents one entry in the CV. The CV is
composed of multiple rows grouped by `section`:

- `personal` — the personal info block (single row, display_order=0).
- `experience` — work history entries (multiple rows, ordered).
- `education` — education entries (multiple rows, ordered).
- `course` — courses and certifications (multiple rows, ordered).

`title` and `description` are `LocalizedStr` JSONB. `subtitle`
(organization / institution / platform) is a plain string because
proper nouns do not need translation. `start_date` / `end_date` are
`YYYY-MM` strings; `end_date = null` means "current". `tags` is a
`list[str]` for future tag-filter support. `is_visible` lets the
admin hide a specific experience entry without deleting it (per
`drafts-visibility` REQ-06).
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


class ResumeData(SQLModel, table=True):
    __tablename__ = "resume_data"

    id: str = Field(default_factory=_new_uuid, primary_key=True, max_length=36)
    section: str = Field(..., max_length=32, index=True)
    display_order: int = Field(default=0, nullable=False)
    title: str = Field(..., max_length=500)  # JSON: LocalizedStr
    subtitle: Optional[str] = Field(default=None, max_length=200)
    description: Optional[str] = Field(default=None, max_length=10_000)  # JSON: LocalizedStr
    start_date: Optional[str] = Field(default=None, max_length=7)
    end_date: Optional[str] = Field(default=None, max_length=7)
    url: Optional[str] = Field(default=None, max_length=500)
    image_url: Optional[str] = Field(default=None, max_length=500)
    tags: str = Field(default="[]", max_length=10_000)  # JSON: list[str]
    is_visible: bool = Field(default=True, nullable=False, index=True)
    extra: str = Field(default="{}", max_length=10_000)  # JSON: free-form
    created_at: datetime = Field(default_factory=_utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=_utcnow, nullable=False)
