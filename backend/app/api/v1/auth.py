"""POST /api/v1/auth/login — admin login.

Validates email + password, issues a JWT, sets the `emalro_session`
httpOnly cookie, and returns the JWT in the envelope body. Rate-limited
via slowapi (5/minute per IP by default).

There is intentionally no `/signup` or `/refresh` endpoint
(auth-jwt REQ-auth-jwt-04, ADR-03).
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.config import get_settings
from app.core.db import get_session
from app.core.rate_limit import limiter as _app_limiter
from app.core.security import (
    SESSION_COOKIE_NAME,
    create_access_token,
    get_current_admin,
    verify_password,
)
from app.models.admin_user import AdminUser
from app.schemas.auth import LoginRequest, LoginResponse, MeResponse
from app.schemas.envelope import Envelope

router = APIRouter()


@router.post("/login", response_model=Envelope[LoginResponse])
@_app_limiter.limit(get_settings().LOGIN_RATE_LIMIT)
async def login(
    request: Request,
    payload: LoginRequest,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    """Authenticate an admin and set the httpOnly session cookie."""
    result = await session.execute(
        select(AdminUser).where(AdminUser.email == payload.email.lower())
    )
    admin = result.scalar_one_or_none()
    if admin is None or not admin.is_active:
        # Generic 401 — never reveal which field is wrong
        # (auth-jwt REQ-auth-jwt-01).
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_credentials",
        )
    if not verify_password(payload.password, admin.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_credentials",
        )

    # Update last_login_at (best-effort).
    admin.last_login_at = datetime.now(timezone.utc)
    session.add(admin)
    await session.commit()

    settings = get_settings()
    expires_in = settings.JWT_EXPIRATION_HOURS * 3600
    token = create_access_token({"sub": admin.id, "email": admin.email})

    resp = JSONResponse(
        status_code=200,
        content=Envelope.ok(
            LoginResponse(
                access_token=token,
                token_type="bearer",
                expires_in=expires_in,
            )
        ).model_dump(),
    )

    # Set the httpOnly cookie. `Secure` is added in production (HTTPS only).
    resp.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        path="/",
        max_age=expires_in,
        secure=(settings.ENV == "prod"),
    )
    return resp


@router.post("/logout")
async def logout() -> JSONResponse:
    """Clear the session cookie. No-op if not logged in."""
    resp = JSONResponse(
        status_code=200,
        content=Envelope[dict].ok({"status": "logged_out"}).model_dump(),
    )
    resp.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return resp


# ---------------------------------------------------------------------------
# GET /api/v1/auth/me
# ---------------------------------------------------------------------------


@router.get("/me", response_model=Envelope[MeResponse])
async def me(
    admin: AdminUser = Depends(get_current_admin),
) -> Envelope[MeResponse]:
    """Return the current admin's basic info.

    Used by the admin SPA on app load to verify the `emalro_session`
    cookie is still valid and to fetch the admin's email for the
    dashboard header. The `get_current_admin` dependency reads +
    decodes the cookie and loads the `AdminUser` row from the DB;
    on any auth failure it raises 401 with the `unauthorized` or
    `token_expired` envelope code.
    """
    return Envelope.ok(
        MeResponse(
            id=admin.id,
            email=admin.email,
            is_active=admin.is_active,
        )
    )
