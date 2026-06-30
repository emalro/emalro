"""FastAPI application entrypoint for the emalro backend.

The application is assembled in `create_app()` so the test suite can
spin up isolated app instances (e.g. with a SQLite database, custom
settings, or a rate-limit-disabled state).

PR #1 scope: scaffold + health endpoint + exception handlers.
Subsequent PRs mount the v1 routers (auth, public, admin, contacts).
"""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1 import auth, health, public
from app.core.config import get_settings
from app.core.rate_limit import limiter
from app.middleware.envelope import EnvelopeMiddleware
from app.middleware.request_id import RequestIdMiddleware
from app.schemas.envelope import Envelope, EnvelopeError

logger = logging.getLogger(__name__)


def _configure_logging() -> None:
    """Configure the root logger (idempotent)."""
    root = logging.getLogger()
    if any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    root.addHandler(handler)
    root.setLevel(logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan: configure logging on startup."""
    _configure_logging()
    settings = get_settings()
    logger.info(
        "emalro backend starting",
        extra={"env": settings.ENV, "port": settings.PORT},
    )
    yield
    logger.info("emalro backend shutting down")


def create_app() -> FastAPI:
    """Build and configure the FastAPI app."""
    settings = get_settings()

    app = FastAPI(
        title="emalro backend",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/api/v1/docs",
        redoc_url=None,
        openapi_url="/api/v1/openapi.json",
    )

    # Rate limiter must be on app.state for slowapi decorators.
    app.state.limiter = limiter

    # CORS — dev + prod. `allow_credentials=True` supports the httpOnly
    # admin cookie. `allow_origins` is a specific list (no `*`).
    origins = [o.strip() for o in settings.ALLOWED_ORIGINS.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-Id"],
        expose_headers=["ETag", "X-Request-Id"],
    )

    # Custom middleware: envelope (last), request-id (first).
    app.add_middleware(EnvelopeMiddleware)
    app.add_middleware(RequestIdMiddleware)

    # Rate-limit exception handler (slowapi). We wrap the response in
    # the standard envelope and add `Retry-After` from the limiter.
    async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
        from starlette.responses import JSONResponse

        resp = Envelope.from_error(
            EnvelopeError(code="rate_limited", message=str(exc.detail)),
            status_code=429,
        )
        # Inject Retry-After header (if available on the limiter).
        try:
            request.state.view_rate_limit  # populated by slowapi when limit hit
            response = app.state.limiter._inject_headers(
                resp, request.state.view_rate_limit
            )
            return response
        except AttributeError:
            return resp

    app.add_exception_handler(RateLimitExceeded, rate_limit_handler)

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request, exc: StarletteHTTPException):
        code = _http_status_to_error_code(exc.status_code, exc.detail)
        return Envelope.from_error(
            EnvelopeError(code=code, message=str(exc.detail)),
            status_code=exc.status_code,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request, exc: RequestValidationError):
        return Envelope.from_error(
            EnvelopeError(code="validation_error", message="Request validation failed"),
            status_code=422,
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request, exc: Exception):
        logger.exception("unhandled exception", extra={"path": str(request.url)})
        return Envelope.from_error(
            EnvelopeError(code="server_error", message="Internal server error"),
            status_code=500,
        )

    # v1 routers (PR #1 scope).
    app.include_router(health.router, prefix="/api/v1", tags=["health"])
    app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
    app.include_router(public.router, prefix="/api/v1", tags=["public"])

    return app


def _http_status_to_error_code(status_code: int, detail: object) -> str:
    """Map an HTTP status to a locked error code."""
    if isinstance(detail, str) and detail in {
        "invalid_credentials",
        "token_expired",
        "unauthorized",
        "forbidden",
        "not_found",
        "validation_error",
        "rate_limited",
        "file_too_large",
        "unsupported_media_type",
        "honeypot_triggered",
        "invalid_parameter",
        "server_error",
    }:
        return detail
    mapping = {
        400: "bad_request",
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        409: "conflict",
        413: "file_too_large",
        415: "unsupported_media_type",
        422: "validation_error",
        429: "rate_limited",
    }
    return mapping.get(status_code, "server_error")


# Module-level app instance for `uvicorn app.main:app`.
app = create_app()
