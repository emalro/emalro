"""Public contact form endpoint.

`POST /api/v1/contacts` is the only public mutation in the API.
It is unauthenticated (no JWT) and rate-limited per IP (slowapi,
5/hour by default). The `website` field is the honeypot: real users
never fill it; bots that fill it are silently rejected with a 400
`bad_request` (we deliberately do NOT distinguish the honeypot
path from any other 400 — leaking `honeypot_triggered` would help
attackers fingerprint the defense).

Validation (Pydantic) rejects bad payloads with 422. The success
path returns 201 with the new row's `id` and `received_at`.
"""

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.exc import DisconnectionError, InterfaceError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_session
from app.core.rate_limit import limiter as _app_limiter
from app.models.contact import ContactMessage
from app.schemas.contact import ContactCreateRequest, ContactCreateResponse
from app.schemas.envelope import Envelope

logger = logging.getLogger(__name__)

# Backoff for the single retry of a transient DB commit failure.
# 100 ms is short enough to be invisible to the user (total request
# stays well under the 2 s frontend timeout) and long enough to
# clear a momentary pooler / network blip on a typical cloud DB.
_COMMIT_RETRY_DELAY_S = 0.1

router = APIRouter()


async def _commit_with_retry(
    session: AsyncSession, pending: list
) -> None:
    """Commit once, retry once on a transient DB connection error.

    The contact form is the only public mutation in the API and is
    not idempotent (no client-supplied id we can dedupe on), so we
    accept the small risk of a duplicate on the rare double-success
    case in exchange for resilience to the much more common transient
    failures (pooler reset, network blip, momentary disconnects).

    We catch the full family of transient errors:
    - `OperationalError` (SQLAlchemy 1.x+ catch-all for connection
      issues, deadlocks, lock timeouts).
    - `DisconnectionError` (raised when asyncpg/psycopg detects a
      broken connection mid-statement).
    - `InterfaceError` (raised for DBAPI-level protocol errors).

    All three extend `SQLAlchemyError` directly (not `OperationalError`)
    in SQLAlchemy 2.x, so the original `except OperationalError` only
    missed two of them.

    `pending` is the list of model instances the caller has just
    `add()`-ed. After a failed commit the session is rolled back and
    the instances become detached, so we re-`add()` them before the
    retry — otherwise the second `commit()` would succeed but flush
    nothing.
    """
    transient_errors = (OperationalError, DisconnectionError, InterfaceError)
    try:
        await session.commit()
    except transient_errors as exc:
        logger.warning("DB commit failed, retrying once: %s", exc)
        # Roll back the failed transaction so the retry starts clean.
        await session.rollback()
        for obj in pending:
            session.add(obj)
        await asyncio.sleep(_COMMIT_RETRY_DELAY_S)
        try:
            await session.commit()
        except transient_errors as exc2:
            logger.error("DB commit failed on retry: %s", exc2)
            await session.rollback()
            raise HTTPException(
                status_code=503,
                detail="transient_error",
            ) from exc2


@router.post(
    "/contacts",
    response_model=Envelope[ContactCreateResponse],
    status_code=status.HTTP_201_CREATED,
)
@_app_limiter.limit(get_settings().CONTACT_RATE_LIMIT)
async def create_contact(
    request: Request,
    payload: ContactCreateRequest,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> Envelope[ContactCreateResponse]:
    """Persist a contact message; reject honeypot hits silently."""
    # Honeypot check: any non-empty `website` is a bot. We deliberately
    # do NOT use `and .strip()` here because Python's `and` short-circuits
    # and returns the stripped value (which is empty for `"   "`); the
    # resulting `if ""` is falsy, so whitespace-only would bypass the
    # check. Instead, we test the raw value for emptiness — the frontend
    # always sends `""` for real users, so any other value (including
    # whitespace) is a bot signal.
    if payload.website is not None and payload.website != "":
        logger.info(
            "Honeypot triggered from %s; dropping silently",
            request.client.host if request.client else "unknown",
        )
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
    await _commit_with_retry(session, [row])
    await session.refresh(row)

    return Envelope.ok(
        ContactCreateResponse(id=row.id, received_at=row.received_at)
    )
