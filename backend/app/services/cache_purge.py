"""Cloudflare edge-cache purge helper.

Admin mutations call `purge_paths(...)` to invalidate the CDN cache
when content changes. The purge is fire-and-forget per design
decision N4: a failure to reach Cloudflare does NOT fail the
mutation; the edge cache's `s-maxage=3600` is the fallback.

In dev or when Cloudflare env vars are missing, the function is a
no-op (returns immediately). The unit test asserts both the no-op
and the request-payload shape.
"""

from __future__ import annotations

import logging
from typing import Iterable

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

CLOUDFLARE_PURGE_URL = (
    "https://api.cloudflare.com/client/v4/zones/{zone}/purge_cache"
)


async def purge_paths(paths: Iterable[str]) -> None:
    """Best-effort purge of the given paths from the Cloudflare edge.

    The function is a no-op when either `CLOUDFLARE_ZONE_ID` or
    `CLOUDFLARE_API_TOKEN` is unset (dev or first deploy). Otherwise
    it sends a single POST with `{"files": [...paths]}` and logs
    the outcome without raising.
    """
    settings = get_settings()
    if not settings.CLOUDFLARE_ZONE_ID or not settings.CLOUDFLARE_API_TOKEN:
        return  # no-op: cache purge not configured

    path_list = [p for p in paths if p]
    if not path_list:
        return

    url = CLOUDFLARE_PURGE_URL.format(zone=settings.CLOUDFLARE_ZONE_ID)
    headers = {
        "Authorization": f"Bearer {settings.CLOUDFLARE_API_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {"files": path_list}

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            if response.status_code >= 400:
                logger.warning(
                    "Cloudflare purge returned %s for %d path(s)",
                    response.status_code,
                    len(path_list),
                )
            else:
                logger.info(
                    "Cloudflare purge ok: %d path(s) (status=%s)",
                    len(path_list),
                    response.status_code,
                )
    except httpx.HTTPError as exc:
        logger.warning("Cloudflare purge failed: %s", exc)
