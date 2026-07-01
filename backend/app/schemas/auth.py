"""Pydantic request/response models for the auth flow."""

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=200)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class MeResponse(BaseModel):
    """The current admin's basic info returned by `GET /api/v1/auth/me`.

    The frontend calls this endpoint on app load to verify the
    `emalro_session` cookie is still valid and to get the admin's
    email for the dashboard. Email is sourced from the DB row
    (already validated at login) so it is typed as plain `str`.
    """

    id: str
    email: str
    is_active: bool
