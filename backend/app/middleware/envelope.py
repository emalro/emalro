"""Envelope enforcement middleware.

Defense in depth: if a route handler returns a raw JSON object that
does NOT have the `{data, error}` shape, this middleware wraps it
in an envelope. The middleware is a safety net; route handlers
should return `Envelope[T]` directly.

Additionally, the middleware computes an `ETag` from the response
body (SHA-256 of canonical JSON) and short-circuits 304 Not Modified
when the client sends a matching `If-None-Match`.

The middleware is registered BEFORE `RequestIdMiddleware` so the
X-Request-Id header is added after the envelope pass completes.
"""

from __future__ import annotations

import hashlib
import json
from typing import Iterable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

# Endpoints that should NOT receive an ETag (always-fresh or
# non-cacheable by design). Auth + admin responses are private.
_NO_CACHE_PATHS = ("/api/v1/auth/", "/api/v1/admin/")


def _compute_etag(body: bytes) -> str:
    """Return a quoted SHA-256 of the canonical JSON body."""
    try:
        parsed = json.loads(body.decode("utf-8"))
        canonical = json.dumps(parsed, sort_keys=True, separators=(",", ":"))
    except (ValueError, UnicodeDecodeError):
        canonical = body.decode("utf-8", errors="ignore")
    return '"' + hashlib.sha256(canonical.encode("utf-8")).hexdigest() + '"'


def _is_already_envelope(payload: dict | list) -> bool:
    if not isinstance(payload, dict):
        return False
    return set(payload.keys()) >= {"data", "error"}


class EnvelopeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # Only process JSON responses; skip 204 / 304 / streaming.
        if response.status_code in (204, 304):
            return response
        content_type = response.headers.get("content-type", "")
        if "application/json" not in content_type:
            return response

        # Skip admin / auth paths (private responses, no ETag).
        path = request.url.path
        if any(path.startswith(p) for p in _NO_CACHE_PATHS):
            return response

        # Drain the response body to inspect / wrap / short-circuit.
        body = b""
        async for chunk in response.body_iterator:
            if isinstance(chunk, str):
                chunk = chunk.encode("utf-8")
            body += chunk

        # Decode JSON
        try:
            payload = json.loads(body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            # Not JSON we can introspect — return as-is.
            new_resp = Response(content=body, status_code=response.status_code, headers=dict(response.headers))
            return new_resp

        # Wrap if the handler returned a raw dict.
        if not _is_already_envelope(payload):
            payload = {"data": payload, "error": None}

        # Re-serialize.
        new_body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

        # ETag handling.
        etag = _compute_etag(new_body)
        inm = request.headers.get("if-none-match")
        if inm and inm == etag:
            headers = _drop_headers(
                response.headers, drop={"content-length", "etag", "content-type"}
            )
            headers["ETag"] = etag
            return Response(status_code=304, headers=headers)

        # Build the final response, preserving any cookies/headers from the
        # original response (e.g. `set_cookie` calls in route handlers).
        new_headers = _drop_headers(
            response.headers, drop={"content-length", "etag"}
        )
        new_headers["ETag"] = etag
        new_headers["content-type"] = "application/json"
        new_resp = Response(
            content=new_body,
            status_code=response.status_code,
            headers=new_headers,
        )
        return new_resp


def _drop_headers(headers: Iterable[tuple[str, str]], drop: set[str]) -> dict:
    """Return a dict of headers with the named keys removed (case-insensitive)."""
    drop_lower = {d.lower() for d in drop}
    out: dict = {}
    items = headers.items() if hasattr(headers, "items") else headers
    for k, v in items:
        if k.lower() in drop_lower:
            continue
        out[k] = v
    return out
