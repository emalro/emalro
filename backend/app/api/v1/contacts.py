"""Public contact form endpoint.

`POST /api/v1/contacts` is the only public mutation in the API.
It is unauthenticated (no JWT) and rate-limited per IP (slowapi,
5/hour by default). The `website` field is the honeypot: real users
never fill it; bots that fill it are silently rejected with a 400
+ `honeypot_triggered` code.

Validation (Pydantic) rejects bad payloads with 422. The success
path returns 201 with the new row's `id` and `received_at`.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_session
from app.core.rate_limit import limiter as _app_limiter
from app.models.contact import ContactMessage
from app.schemas.contact import ContactCreateRequest, ContactCreateResponse
from app.schemas.envelope import Envelope

logger = logging.getLogger(__name__)

router = APIRouter()


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
    # Honeypot check: any non-empty `website` is a bot.
    if payload.website and payload.website.strip():
        logger.info(
            "Honeypot triggered from %s; dropping silently",
            request.client.host if request.client else "unknown",
        )
        raise HTTPException(status_code=400, detail="honeypot_triggered")

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
