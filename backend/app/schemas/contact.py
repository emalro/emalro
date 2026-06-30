"""Pydantic schemas for the public contact form and the admin
contact inbox (read+list only in PR #2; full CRUD in PR #6).
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ---------------------------------------------------------------------------
# Public POST /api/v1/contacts
# ---------------------------------------------------------------------------


class ContactCreateRequest(BaseModel):
    """Request body for `POST /api/v1/contacts`.

    `website` is the honeypot field. Real users never fill it (it's
    off-screen + `tabindex=-1` + `aria-hidden`); bots that fill all
    fields trigger the silent 400 reject.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    subject: Optional[str] = Field(default=None, max_length=200)
    message: str = Field(..., min_length=10, max_length=5_000)
    website: Optional[str] = Field(default=None, max_length=200)


class ContactCreateResponse(BaseModel):
    """Response body for the 201 path."""

    id: str
    received_at: datetime


# ---------------------------------------------------------------------------
# Admin read+list (PR #2 scope: no PATCH/DELETE — those land in PR #6)
# ---------------------------------------------------------------------------


class ContactListItem(BaseModel):
    """A row in the admin contacts inbox or trash list.

    `read_at` is null for unread. `deleted_at` is null for inbox
    rows and populated for trash rows. `message` is included for
    the admin; the public POST response intentionally omits it.
    """

    model_config = ConfigDict(extra="ignore")

    id: str
    name: str
    email: str
    subject: Optional[str] = None
    message: str
    read_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
    received_at: datetime
