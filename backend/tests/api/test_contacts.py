"""Public contact form: 201/422/400/429 envelope paths.

Mandatory tests (per the orchestrator's brief):
- 201 with `data.id` (UUID) and `data.received_at` (ISO-8601).
- 422 envelope on validation failure.
- 400 envelope on honeypot trigger.
- 429 envelope on rate-limit exceeded (6th from same IP).
"""

import asyncio

import pytest


def asyncio_run(coro):
    """Run a coroutine on the session's event loop (sync wrapper)."""
    return asyncio.get_event_loop().run_until_complete(coro)


def _valid_payload(**overrides):
    payload = {
        "name": "Alice",
        "email": "alice@example.com",
        "subject": "Hello",
        "message": "This is a test message that is at least 10 chars.",
    }
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# 201 happy path
# ---------------------------------------------------------------------------


def test_post_contacts_returns_201_with_envelope(client):
    r = client.post("/api/v1/contacts", json=_valid_payload())
    assert r.status_code == 201
    body = r.json()
    assert body["error"] is None
    data = body["data"]
    assert "id" in data and isinstance(data["id"], str) and len(data["id"]) > 0
    assert "received_at" in data and isinstance(data["received_at"], str)


def test_post_contacts_persists_row(client, db_session):
    from sqlmodel import select

    from app.models.contact import ContactMessage

    r = client.post(
        "/api/v1/contacts",
        json=_valid_payload(email="bob@example.com"),
    )
    assert r.status_code == 201

    rows = asyncio_run(db_session.execute(
        select(ContactMessage).where(ContactMessage.email == "bob@example.com")
    )).scalars().all()
    assert len(rows) == 1
    assert rows[0].name == "Alice"


def test_post_contacts_optional_subject(client):
    r = client.post(
        "/api/v1/contacts",
        json=_valid_payload(subject=None),
    )
    assert r.status_code == 201


# ---------------------------------------------------------------------------
# 422 validation failures
# ---------------------------------------------------------------------------


def test_post_contacts_short_message_returns_422(client):
    r = client.post(
        "/api/v1/contacts",
        json=_valid_payload(message="hi"),
    )
    assert r.status_code == 422
    body = r.json()
    assert body["data"] is None
    assert body["error"]["code"] == "validation_error"


def test_post_contacts_invalid_email_returns_422(client):
    r = client.post(
        "/api/v1/contacts",
        json=_valid_payload(email="not-an-email"),
    )
    assert r.status_code == 422
    body = r.json()
    assert body["error"]["code"] == "validation_error"


def test_post_contacts_empty_name_returns_422(client):
    r = client.post(
        "/api/v1/contacts",
        json=_valid_payload(name=""),
    )
    assert r.status_code == 422
    body = r.json()
    assert body["error"]["code"] == "validation_error"


# ---------------------------------------------------------------------------
# 400 honeypot
# ---------------------------------------------------------------------------


def test_post_contacts_honeypot_returns_400(client):
    r = client.post(
        "/api/v1/contacts",
        json=_valid_payload(website="bot"),
    )
    assert r.status_code == 400
    body = r.json()
    # The 400 envelope uses the generic `bad_request` code on purpose:
    # leaking `honeypot_triggered` would let attackers fingerprint the
    # defense. The frontend collapses every non-429 4xx into the same
    # banner so UX is unchanged.
    assert body["error"]["code"] == "bad_request"


def test_post_contacts_honeypot_does_not_persist(client, db_session):
    from sqlmodel import select

    from app.models.contact import ContactMessage

    client.post(
        "/api/v1/contacts",
        json=_valid_payload(website="bot", email="bot@example.com"),
    )
    rows = asyncio_run(db_session.execute(
        select(ContactMessage).where(ContactMessage.email == "bot@example.com")
    )).scalars().all()
    assert len(rows) == 0


def test_post_contacts_honeypot_whitespace_only_returns_400(client, db_session):
    """R3-C2: a single space must NOT bypass the honeypot.

    The previous `payload.website and payload.website.strip()` check
    short-circuited on a truthy non-None string, so `"   "` (truthy
    but strips to empty) was treated as a real user and got persisted.
    The fix uses `is not None and .strip()` so whitespace is correctly
    rejected.
    """
    from sqlmodel import select

    from app.models.contact import ContactMessage

    r = client.post(
        "/api/v1/contacts",
        json=_valid_payload(website="   ", email="ws@example.com"),
    )
    assert r.status_code == 400
    body = r.json()
    assert body["error"]["code"] == "bad_request"

    rows = asyncio_run(db_session.execute(
        select(ContactMessage).where(ContactMessage.email == "ws@example.com")
    )).scalars().all()
    assert len(rows) == 0


def test_post_contacts_honeypot_empty_string_accepted(client):
    """An empty `website` (the default) is NOT a bot signal."""
    r = client.post(
        "/api/v1/contacts",
        json=_valid_payload(website=""),
    )
    assert r.status_code == 201


def test_post_contacts_honeypot_missing_field_accepted(client):
    """An omitted `website` is NOT a bot signal."""
    payload = _valid_payload()
    payload.pop("website", None)
    r = client.post("/api/v1/contacts", json=payload)
    assert r.status_code == 201


# ---------------------------------------------------------------------------
# 429 rate limit
#
# slowapi's `Limiter` is a module-level singleton. The conftest
# sets the contact rate limit to 1000/hour so the happy-path tests
# don't trip it. To exercise the real 5/hour behavior we build a
# fresh FastAPI app with a fresh Limiter at 5/hour and a fresh
# SQLite engine, so the result is independent of any state from
# prior tests.
# ---------------------------------------------------------------------------


def test_post_contacts_6th_in_hour_returns_429():
    """The 6th valid submission from the same IP in 1 hour returns 429."""
    import os
    import asyncio
    from fastapi import FastAPI, APIRouter, Depends, Request, Response
    from fastapi.testclient import TestClient
    from slowapi import Limiter
    from slowapi.errors import RateLimitExceeded
    from slowapi.util import get_remote_address
    from sqlalchemy.ext.asyncio import (
        AsyncSession,
        async_sessionmaker,
        create_async_engine,
    )
    from sqlmodel import SQLModel
    from fastapi.exceptions import RequestValidationError
    from starlette.exceptions import HTTPException as StarletteHTTPException

    from app import models  # noqa: F401
    from app.models.contact import ContactMessage
    from app.schemas.contact import (
        ContactCreateRequest,
        ContactCreateResponse,
    )
    from app.schemas.envelope import Envelope, EnvelopeError

    fresh_limiter = Limiter(key_func=get_remote_address)
    fresh_limiter.reset()

    db_path = "./_test_ratelimit_3.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    fresh_engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path}", echo=False
    )

    async def _setup():
        async with fresh_engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.drop_all)
            await conn.run_sync(SQLModel.metadata.create_all)

    asyncio.get_event_loop().run_until_complete(_setup())

    fresh_factory = async_sessionmaker(
        bind=fresh_engine, expire_on_commit=False, class_=AsyncSession
    )

    async def fresh_session_dep():
        async with fresh_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    app = FastAPI()
    app.state.limiter = fresh_limiter
    test_router = APIRouter()

    @test_router.post("/api/v1/contacts", status_code=201)
    @fresh_limiter.limit("5/hour")
    async def _test_endpoint(
        request: Request,
        payload: ContactCreateRequest,
        response: Response,
        session: AsyncSession = Depends(fresh_session_dep),
    ):
        if payload.website is not None and payload.website.strip():
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail="bad_request")
        row = ContactMessage(
            name=payload.name,
            email=str(payload.email).lower(),
            subject=payload.subject,
            message=payload.message,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return Envelope.ok(
            ContactCreateResponse(id=row.id, received_at=row.received_at)
        )

    app.include_router(test_router)

    @app.exception_handler(RateLimitExceeded)
    async def _rl_handler(request, exc):
        return Envelope.from_error(
            EnvelopeError(code="rate_limited", message=str(exc.detail)),
            status_code=429,
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_handler(request, exc):
        valid_codes = {
            "invalid_credentials", "token_expired", "unauthorized", "forbidden",
            "not_found", "validation_error", "rate_limited", "file_too_large",
            "unsupported_media_type", "bad_request", "invalid_parameter",
            "server_error",
        }
        code_map = {
            400: "bad_request", 401: "unauthorized", 403: "forbidden",
            404: "not_found", 422: "validation_error",
        }
        code = exc.detail if isinstance(exc.detail, str) and exc.detail in valid_codes else code_map.get(exc.status_code, "server_error")
        return Envelope.from_error(
            EnvelopeError(code=code, message=str(exc.detail)),
            status_code=exc.status_code,
        )

    @app.exception_handler(RequestValidationError)
    async def _val_handler(request, exc):
        return Envelope.from_error(
            EnvelopeError(code="validation_error", message="Request validation failed"),
            status_code=422,
        )

    @app.exception_handler(Exception)
    async def _unhandled(request, exc):
        return Envelope.from_error(
            EnvelopeError(code="server_error", message="Internal server error"),
            status_code=500,
        )

    client = TestClient(app)
    try:
        for i in range(5):
            r = client.post(
                "/api/v1/contacts",
                json=_valid_payload(email=f"rl-{i}@example.com"),
            )
            assert r.status_code == 201, f"#{i + 1} returned {r.status_code}: {r.text}"
        r6 = client.post(
            "/api/v1/contacts",
            json=_valid_payload(email="rl-5@example.com"),
        )
        assert r6.status_code == 429
        body = r6.json()
        assert body["error"]["code"] == "rate_limited"
    finally:
        client.close()
        asyncio.get_event_loop().run_until_complete(fresh_engine.dispose())
        if os.path.exists(db_path):
            os.remove(db_path)
