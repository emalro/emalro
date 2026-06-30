"""Request-id middleware: ensure every request has an X-Request-Id.

Generates a UUID4 per request and either:
- echoes the client-provided `X-Request-Id` (if any) so distributed
  traces can be correlated, OR
- generates a fresh UUID4.

The id is attached to the response header so clients (and logs) can
reference it.
"""

from __future__ import annotations

import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

HEADER_NAME = "X-Request-Id"


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        incoming = request.headers.get(HEADER_NAME)
        request_id = incoming if incoming else str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers[HEADER_NAME] = request_id
        return response
