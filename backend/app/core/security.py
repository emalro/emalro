"""JWT + bcrypt helpers and the `get_current_admin` FastAPI dependency."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from fastapi import Depends, HTTPException, Request, status
from jose import ExpiredSignatureError, JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.config import get_settings
from app.core.db import get_session


# ---------------------------------------------------------------------------
# Password hashing (bcrypt cost 12, per auth-jwt REQ-auth-jwt-03)
# ---------------------------------------------------------------------------

_BCRYPT_ROUNDS = 12


def get_password_hash(password: str) -> str:
    """Return a bcrypt hash of the plaintext password."""
    salt = bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Constant-time bcrypt verification."""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------

ALGORITHM = "HS256"


def create_access_token(
    payload: dict,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Sign a JWT with the configured secret.

    Default expiration: `JWT_EXPIRATION_HOURS` from settings.
    """
    settings = get_settings()
    to_encode = dict(payload)
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(hours=settings.JWT_EXPIRATION_HOURS)
    )
    to_encode["exp"] = expire
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=ALGORITHM)


def decode_jwt(token: str) -> dict:
    """Decode and verify a JWT. Raises ExpiredSignatureError or JWTError."""
    settings = get_settings()
    return jwt.decode(token, settings.JWT_SECRET, algorithms=[ALGORITHM])


# ---------------------------------------------------------------------------
# FastAPI dependency: extract the admin from the httpOnly cookie.
# ---------------------------------------------------------------------------

SESSION_COOKIE_NAME = "emalro_session"


async def get_current_admin(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> "object":
    """Read `emalro_session`, decode the JWT, load the AdminUser.

    Raises 401 with `unauthorized` / `token_expired` envelope codes.
    """
    # Imported lazily to dodge a circular import.
    from app.models.admin_user import AdminUser

    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="unauthorized",
        )

    try:
        payload = decode_jwt(token)
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="token_expired",
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="unauthorized",
        )

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="unauthorized",
        )

    # SQLModel/Pydantic UUID columns may serialize as strings.
    try:
        admin_id = sub if isinstance(sub, type(sub)) else str(sub)
    except Exception:  # pragma: no cover - defensive
        admin_id = str(sub)

    result = await session.execute(
        select(AdminUser).where(AdminUser.id == admin_id)  # type: ignore[arg-type]
    )
    admin = result.scalar_one_or_none()
    if admin is None or not admin.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="unauthorized",
        )
    return admin
