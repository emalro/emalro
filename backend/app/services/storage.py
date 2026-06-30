"""Supabase Storage helpers for the image-upload pipeline.

The full image upload + PUT-time orphan mitigation lands in PR #6
(see `api-admin` REQ-04, REQ-05, and `image-upload` REQ-01 to -05).
PR #2 ships only the path convention and the `parse_storage_path`
helper that the PUT handlers in PR #6 will use to decide whether
to call `delete()`.

Path convention (per `image-upload` REQ-03):
    images/{year}/{month}/{uuid}.{ext}

The path is returned by the upload endpoint in `data.path`. The
public URL is derived from `SUPABASE_URL` + `/storage/v1/object/public/media/` + path.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from app.core.config import get_settings


_SUPABASE_PUBLIC_PREFIX = "/storage/v1/object/public/"


def build_storage_path(content_type: str, ext: str) -> str:
    """Build a storage path that follows the locked convention.

    `content_type` is one of `projects`, `blog`, `resume` (matches
    the data table the image is associated with). `ext` is the file
    extension WITHOUT the leading dot (e.g., `png`).

    The path is `images/{year}/{month}/{uuid}.{ext}`. The bucket
    name (`media`) is NOT part of the path — Supabase prefixes it
    on the URL side.
    """
    now = datetime.now(timezone.utc)
    safe_ext = ext.lstrip(".").lower() or "bin"
    safe_type = re.sub(r"[^a-z0-9_-]", "", content_type.lower()) or "misc"
    # The convention is `images/{year}/{month}/{uuid}.{ext}`; the
    # `content_type` is informational only (used by the operator to
    # find the file later, not encoded in the path).
    _ = safe_type
    return f"images/{now.year:04d}/{now.month:02d}/{uuid.uuid4().hex}.{safe_ext}"


def public_url_for(path: str) -> str:
    """Return the public Supabase Storage URL for a storage path."""
    settings = get_settings()
    base = settings.SUPABASE_URL.rstrip("/")
    return f"{base}{_SUPABASE_PUBLIC_PREFIX}media/{path.lstrip('/')}"


def parse_storage_path(image_url: Optional[str]) -> Optional[str]:
    """Extract the storage path from a Supabase public URL.

    Returns `None` if `image_url` is not a Supabase URL (e.g., a
    local path like `/img/projects/monogram.png`). The PUT handler
    uses this to decide whether to call `delete()` on the old image.
    """
    if not image_url:
        return None
    settings = get_settings()
    base = settings.SUPABASE_URL.rstrip("/")
    prefix = f"{base}{_SUPABASE_PUBLIC_PREFIX}media/"
    if image_url.startswith(prefix):
        return image_url[len(prefix):]
    return None
