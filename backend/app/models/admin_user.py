"""AdminUser SQLModel table.

Single table for the JWT auth flow. `id` is a UUID (string) so we can
embed it in the JWT `sub` claim without a numeric collision.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def _new_uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AdminUser(SQLModel, table=True):
    __tablename__ = "admin_users"

    id: str = Field(default_factory=_new_uuid, primary_key=True, max_length=36)
    email: str = Field(unique=True, index=True, max_length=320)
    password_hash: str = Field(max_length=255)
    is_active: bool = Field(default=True, nullable=False)
    last_login_at: datetime | None = Field(default=None, nullable=True)
    created_at: datetime = Field(default_factory=_utcnow, nullable=False)
