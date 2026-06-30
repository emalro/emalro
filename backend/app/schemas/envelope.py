"""Response envelope: `Envelope[T]` and `EnvelopeError`.

Every endpoint in the API returns either:

    {"data": <payload>, "error": null}
    {"data": null, "error": {"code": "...", "message": "..."}}

The error codes follow the locked vocabulary from the design
(obs 306, section 6).
"""

from __future__ import annotations

from typing import Generic, Optional, TypeVar

from fastapi import Response
from pydantic import BaseModel, Field

T = TypeVar("T")


class EnvelopeError(BaseModel):
    """Error payload: a stable code + a developer-facing message."""

    code: str = Field(..., description="Locked error code, see design section 6")
    message: str = Field(..., description="Developer-facing English message")


class Envelope(BaseModel, Generic[T]):
    """Standard success/error envelope.

    On success: `data=<T>`, `error=None`.
    On failure: `data=None`, `error=EnvelopeError(...)`.
    """

    data: Optional[T] = None
    error: Optional[EnvelopeError] = None

    @classmethod
    def ok(cls, data: T) -> "Envelope[T]":
        return cls(data=data, error=None)

    @classmethod
    def fail(cls, code: str, message: str) -> "Envelope[None]":
        return cls(data=None, error=EnvelopeError(code=code, message=message))

    @classmethod
    def from_error(
        cls,
        error: EnvelopeError,
        status_code: int = 500,
    ) -> Response:
        """Build a FastAPI Response for the error path.

        This is the preferred way to return an envelope from a route
        that needs a non-200 status code.
        """
        from fastapi.encoders import jsonable_encoder
        from starlette.responses import JSONResponse

        body = cls[None](data=None, error=error)
        return JSONResponse(
            status_code=status_code,
            content=jsonable_encoder(body),
        )


class PageMeta(BaseModel):
    """Pagination metadata for `PaginatedEnvelope`."""

    total: int
    page: int
    limit: int
    pages: int


class PaginatedEnvelope(BaseModel, Generic[T]):
    """Envelope for paginated list responses."""

    data: list[T]
    meta: PageMeta
    error: None = None
