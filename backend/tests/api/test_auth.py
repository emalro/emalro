"""POST /api/v1/auth/login and provisioning CLI behavior."""

from __future__ import annotations

import asyncio
import time

import pytest

from app.scripts.create_admin import _upsert_admin, _validate_email, _validate_password
from app.core.security import SESSION_COOKIE_NAME, create_access_token, decode_jwt


# ---------------------------------------------------------------------------
# /auth/login
# ---------------------------------------------------------------------------


def test_login_success_returns_jwt_and_cookie(client, admin_user):
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@emalro.com.ar", "password": "S3cr3t!Pass"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["error"] is None
    data = body["data"]
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == 8 * 3600
    assert isinstance(data["access_token"], str) and len(data["access_token"]) > 0

    # The cookie is set.
    set_cookie = r.headers.get("set-cookie", "")
    assert SESSION_COOKIE_NAME in set_cookie
    assert "HttpOnly" in set_cookie
    assert "SameSite=Lax" in set_cookie or "samesite=lax" in set_cookie.lower()


def test_login_invalid_password_returns_401(client, admin_user):
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@emalro.com.ar", "password": "wrong"},
    )
    assert r.status_code == 401
    body = r.json()
    assert body["data"] is None
    assert body["error"]["code"] == "invalid_credentials"


def test_login_unknown_email_returns_401(client):
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@emalro.com.ar", "password": "anything"},
    )
    assert r.status_code == 401
    body = r.json()
    assert body["error"]["code"] == "invalid_credentials"


@pytest.mark.asyncio
async def test_login_inactive_user_returns_401(db_session, client):
    """Inactive admin: login must return 401 invalid_credentials."""
    from uuid import uuid4

    from app.core.security import get_password_hash
    from app.models.admin_user import AdminUser

    user = AdminUser(
        id=str(uuid4()),
        email="inactive@emalro.com.ar",
        password_hash=get_password_hash("S3cr3t!Pass"),
        is_active=False,
    )
    db_session.add(user)
    await db_session.commit()

    r = client.post(
        "/api/v1/auth/login",
        json={"email": "inactive@emalro.com.ar", "password": "S3cr3t!Pass"},
    )
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "invalid_credentials"


def test_no_signup_endpoint(client):
    r = client.post("/api/v1/auth/signup", json={"email": "x@x.com", "password": "12345678"})
    assert r.status_code == 404
    body = r.json()
    assert body["data"] is None
    assert body["error"]["code"] == "not_found"


def test_no_refresh_endpoint(client):
    r = client.post("/api/v1/auth/refresh", json={})
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


def test_logout_clears_cookie(client, admin_user):
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@emalro.com.ar", "password": "S3cr3t!Pass"},
    )
    assert SESSION_COOKIE_NAME in r.headers.get("set-cookie", "")

    r2 = client.post("/api/v1/auth/logout")
    assert r2.status_code == 200
    deleted = r2.headers.get("set-cookie", "")
    assert SESSION_COOKIE_NAME in deleted
    # Max-Age=0 (or expired) → cookie cleared.
    assert "Max-Age=0" in deleted or "max-age=0" in deleted.lower() or "1970" in deleted


# ---------------------------------------------------------------------------
# JWT shape
# ---------------------------------------------------------------------------


def test_jwt_can_be_decoded_with_settings_secret(admin_user):
    token = create_access_token({"sub": admin_user.id, "email": admin_user.email})
    payload = decode_jwt(token)
    assert payload["sub"] == admin_user.id
    assert payload["email"] == admin_user.email
    # exp must be in the future
    assert payload["exp"] > int(time.time())


# ---------------------------------------------------------------------------
# Provisioning CLI
# ---------------------------------------------------------------------------


def test_validate_email_rejects_invalid():
    with pytest.raises(ValueError):
        _validate_email("not-an-email")
    with pytest.raises(ValueError):
        _validate_email("missing-at.com")


def test_validate_email_accepts_valid():
    _validate_email("admin@emalro.com.ar")


def test_validate_password_rejects_short():
    with pytest.raises(ValueError):
        _validate_password("short")


def test_validate_password_accepts_8_chars():
    _validate_password("12345678")


@pytest.mark.asyncio
async def test_upsert_admin_creates_then_updates(db_session):
    from uuid import uuid4

    # Make sure no admin with this email exists.
    email = "upsert@emalro.com.ar"
    from sqlmodel import select

    from app.models.admin_user import AdminUser

    result = await db_session.execute(
        select(AdminUser).where(AdminUser.email == email)
    )
    for row in result.scalars():
        await db_session.delete(row)
    await db_session.commit()

    outcome1 = await _upsert_admin(email, "FirstPass!1")
    assert outcome1 == "created"

    result = await db_session.execute(
        select(AdminUser).where(AdminUser.email == email)
    )
    row = result.scalar_one()
    first_hash = row.password_hash
    assert first_hash.startswith("$2b$") or first_hash.startswith("$2a$")

    outcome2 = await _upsert_admin(email, "SecondPass!1")
    assert outcome2 == "updated"

    await db_session.refresh(row)
    assert row.password_hash != first_hash
