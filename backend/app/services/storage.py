"""Storage abstraction for the image-upload pipeline.

Two backends ship with PR #6 (see `api-admin` REQ-04, REQ-05 and
`image-upload` REQ-01 to -05):

- `SupabaseStorage` — production backend. Uploads to a public
  Supabase Storage bucket named `media` via the REST API
  (`POST /storage/v1/object/media/{path}` and the matching
  `DELETE`).
- `LocalStorage` — local-dev + tests backend. Writes files under
  the directory named by `settings.UPLOAD_DIR` (default `./uploads`)
  and serves them back at `/api/v1/admin/images/{path:path}`
  (a dev-only convenience mounted in `admin_images.py`).

`get_storage()` returns the right backend based on `settings.ENV`:
`SupabaseStorage` when `ENV=prod`, `LocalStorage` otherwise.

The path convention is `images/{year}/{month}/{uuid}.{ext}` (per
`image-upload` REQ-03). The path is returned to the client in
`data.path`; the public URL is `data.url`.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Protocol

import httpx

from app.core.config import get_settings


_SUPABASE_PUBLIC_PREFIX = "/storage/v1/object/public/"
_BUCKET = "media"


# ---------------------------------------------------------------------------
# Path + URL helpers (shared by both backends)
# ---------------------------------------------------------------------------


def build_storage_path(content_type: str, ext: str) -> str:
    """Build a storage path that follows the locked convention.

    `content_type` is one of `projects`, `blog`, `resume` (matches
    the data table the image is associated with). `ext` is the file
    extension WITHOUT the leading dot (e.g., `png`).

    The path is `images/{year}/{month}/{uuid}.{ext}`. The bucket
    name is NOT part of the path — Supabase prefixes it on the
    URL side.
    """
    now = datetime.now(timezone.utc)
    safe_ext = ext.lstrip(".").lower() or "bin"
    safe_type = re.sub(r"[^a-z0-9_-]", "", content_type.lower()) or "misc"
    # `safe_type` is reserved for future use; the convention only
    # uses the year/month/uuid/ext shape today.
    _ = safe_type
    return f"images/{now.year:04d}/{now.month:02d}/{uuid.uuid4().hex}.{safe_ext}"


def supabase_public_url(path: str) -> str:
    """Return the public Supabase Storage URL for a storage path."""
    settings = get_settings()
    base = settings.SUPABASE_URL.rstrip("/")
    return f"{base}{_SUPABASE_PUBLIC_PREFIX}{_BUCKET}/{path.lstrip('/')}"


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
    prefix = f"{base}{_SUPABASE_PUBLIC_PREFIX}{_BUCKET}/"
    if image_url.startswith(prefix):
        return image_url[len(prefix):]
    return None


# ---------------------------------------------------------------------------
# Storage protocol + backends
# ---------------------------------------------------------------------------


class Storage(Protocol):
    """Storage backend contract.

    `save()` writes the raw bytes to the backend under `path` and
    returns the public URL the FE will use as the `image_url`.
    `delete()` removes the object; missing paths are a no-op
    (the orphan-mitigation logic in the PUT handlers tolerates
    a 404 on delete).
    `local_url_for()` returns the dev-only URL when the backend
    is `LocalStorage`; for `SupabaseStorage` it returns `None`
    (Supabase serves the URL itself).
    """

    def save(self, *, path: str, data: bytes, content_type: str) -> str: ...
    def delete(self, *, path: str) -> None: ...
    def local_url_for(self, path: str) -> Optional[str]: ...


class SupabaseStorage:
    """Production backend: stores objects in the Supabase Storage bucket."""

    def __init__(self) -> None:
        settings = get_settings()
        self._base = settings.SUPABASE_URL.rstrip("/")
        self._key = settings.SUPABASE_SERVICE_KEY

    def _object_url(self, path: str) -> str:
        return f"{self._base}/storage/v1/object/{_BUCKET}/{path.lstrip('/')}"

    async def save(self, *, path: str, data: bytes, content_type: str) -> str:
        """Upload to Supabase Storage; return the public URL."""
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.put(
                self._object_url(path),
                content=data,
                headers={
                    "Authorization": f"Bearer {self._key}",
                    "Content-Type": content_type,
                    "x-upsert": "false",
                },
            )
        if resp.status_code not in (200, 201):
            raise RuntimeError(
                f"Supabase upload failed: {resp.status_code} {resp.text}"
            )
        return supabase_public_url(path)

    async def delete(self, *, path: str) -> None:
        """Delete the object; 404 is tolerated (orphan cleanup)."""
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.delete(
                self._object_url(path),
                headers={"Authorization": f"Bearer {self._key}"},
            )
        if resp.status_code not in (200, 204, 404):
            raise RuntimeError(
                f"Supabase delete failed: {resp.status_code} {resp.text}"
            )

    def local_url_for(self, path: str) -> Optional[str]:
        return None  # pragma: no cover - Supabase serves the URL itself


class LocalStorage:
    """Local-dev + tests backend: writes to `settings.UPLOAD_DIR`.

    The public URL for a stored object is `/api/v1/admin/images/{path}`,
    served by the dev-only `GET /api/v1/admin/images/{path:path}`
    route in `admin_images.py`.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._root = Path(settings.UPLOAD_DIR).resolve()

    def _path_for(self, key: str) -> Path:
        # Defensive: reject path traversal (`..` segments).
        candidate = (self._root / key).resolve()
        if not str(candidate).startswith(str(self._root)):
            raise ValueError(f"refusing to escape upload root: {key!r}")
        return candidate

    async def save(self, *, path: str, data: bytes, content_type: str) -> str:
        """Write the file under the upload dir; return the dev URL."""
        # `content_type` is part of the protocol but unused by the
        # local backend (the file is just bytes on disk).
        _ = content_type
        full = self._path_for(path)
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_bytes(data)
        return self.local_url_for(path) or ""

    async def delete(self, *, path: str) -> None:
        """Delete the file; missing files are a no-op."""
        full = self._path_for(path)
        if full.exists():
            full.unlink()

    def local_url_for(self, path: str) -> Optional[str]:
        return f"/api/v1/admin/images/{path.lstrip('/')}"


def get_storage() -> Storage:
    """Return the right `Storage` backend for the current env.

    Production -> Supabase. Anything else (dev / test) -> local.
    The choice is read once at call time so tests can monkey-patch
    `settings.ENV` between cases if needed.
    """
    settings = get_settings()
    if settings.ENV == "prod":
        return SupabaseStorage()
    return LocalStorage()

