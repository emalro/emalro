"""ContactMessage SQLModel table.

A `ContactMessage` is a single submission from the public contact
form. The `website` honeypot field is intentionally NOT stored (it's
rejected server-side; we drop the row silently on the bot's side).

`read_at IS NULL` means unread; `deleted_at IS NOT NULL` means the
admin moved it to trash. The admin inbox (`/api/v1/admin/contacts`)
returns rows where `deleted_at IS NULL`; the trash endpoint returns
rows where `deleted_at IS NOT NULL` (both per `contact-inbox` spec).

A simple `ContactStatus` Python enum is exposed for callers that
prefer constants over string comparison (per the design: no Postgres
ENUM, the DB stores the timestamp and the Python enum maps to the
status transitions).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel


def _new_uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ContactStatus(str, Enum):
    """Convenience constants for the read/trash lifecycle.

    The DB does NOT store a status column; the timestamps (`read_at`
    and `deleted_at`) are the source of truth. This enum is for
    callers (admin services, tests) that want named constants.
    """

    UNREAD = "unread"
    READ = "read"
    TRASHED = "trashed"


class ContactMessage(SQLModel, table=True):
    __tablename__ = "contact_messages"

    id: str = Field(default_factory=_new_uuid, primary_key=True, max_length=36)
    name: str = Field(..., max_length=100)
    email: str = Field(..., max_length=320, index=True)
    subject: Optional[str] = Field(default=None, max_length=200)
    message: str = Field(..., max_length=5_000)
    ip_address: Optional[str] = Field(default=None, max_length=64)
    user_agent: Optional[str] = Field(default=None, max_length=500)
    read_at: Optional[datetime] = Field(default=None, nullable=True, index=True)
    deleted_at: Optional[datetime] = Field(default=None, nullable=True, index=True)
    received_at: datetime = Field(
        default_factory=_utcnow, nullable=False, index=True
    )
