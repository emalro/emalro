"""GET /api/v1/health — process-alive check.

Returns `{"data": {"status": "ok"}, "error": null}`. Does not touch
the database (per cold-start-ping REQ-cold-start-ping-01). Mounted
BEFORE slowapi and outside any auth path.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.schemas.envelope import Envelope

router = APIRouter()


@router.get("/health", response_model=Envelope[dict])
async def health() -> Envelope[dict]:
    return Envelope.ok({"status": "ok"})
