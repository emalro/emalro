"""slowapi Limiter used by auth (and later, contacts)."""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

# Key by client IP. `get_remote_address` reads `request.client.host`
# which Starlette populates from the underlying connection.
limiter = Limiter(key_func=get_remote_address)
