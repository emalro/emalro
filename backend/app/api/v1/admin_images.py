"""Admin image upload + delete + dev static-serve endpoints.

- `POST   /admin/images`         — multipart form with one `file` field.
  Validates the MIME type (image/jpeg, image/png, image/webp,
  image/svg+xml) and the size (`settings.IMAGE_MAX_BYTES`).
  Uploads to Supabase Storage (prod) or `settings.UPLOAD_DIR` (dev).
  Returns 201 with `{"url": ..., "path": ...}`.
- `DELETE /admin/images`         — body `{"path": "..."}`. Removes
  the object from storage. 204 on success.
- `GET    /admin/images/{path:path}` — dev-only static-serve
  endpoint. Reads the file from the local upload dir and streams
  it back. In production this route is registered but never
  called (Supabase Storage serves the URL directly); it's left in
  for symmetry so test fixtures that build the URL can fetch
  it via the same path the FE uses.

The route is gated by `get_current_admin` for write endpoints;
the static-serve endpoint is intentionally NOT gated (it serves
public image bytes, like `/static/foo.png`).
"""

from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_session
from app.core.security import get_current_admin
from app.schemas.admin import (
    AdminImageDeleteRequest,
    AdminImageUploadResponse,
)
from app.schemas.envelope import Envelope
from app.services.storage import (
    Storage,
    build_storage_path,
    get_storage,
)


router = APIRouter(
    prefix="/images",
    dependencies=[Depends(get_current_admin)],
)


# ---------------------------------------------------------------------------
# MIME type + extension map
# ---------------------------------------------------------------------------


# Allowed image types for the upload endpoint (per the image-upload
# spec). SVG is allowed for portability (small icons, logos); the
# admin is the only writer, so XSS risk is operator-side only.
_ALLOWED_MIME_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/svg+xml": "svg",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _storage() -> Storage:
    """Return the storage backend for the current env."""
    return get_storage()


def _safe_path_segment(segment: str) -> str:
    """Sanitize a single path segment (no `..`, no leading `/`).

    Used when reading the dev static-serve endpoint, where the
    URL is operator-controlled but still we want to refuse any
    path-traversal attempt.
    """
    segment = segment.lstrip("/")
    if not segment or ".." in segment.split("/"):
        raise HTTPException(status_code=400, detail="bad_request")
    return segment


# ---------------------------------------------------------------------------
# POST /api/v1/admin/images
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=Envelope[AdminImageUploadResponse],
    status_code=status.HTTP_201_CREATED,
)
async def admin_upload_image(
    file: UploadFile = File(...),
) -> Envelope[AdminImageUploadResponse]:
    """Upload an image to storage.

    Validates the MIME type and the size (using `Content-Length`
    when present; reading the body in full otherwise so the
    in-memory budget is checked too). The path follows the
    `images/{year}/{month}/{uuid}.{ext}` convention.
    """
    settings = get_settings()

    # MIME type — prefer the client-declared content_type, fall
    # back to a sniff of the filename extension.
    mime = (file.content_type or "").lower()
    ext = _ALLOWED_MIME_TYPES.get(mime)
    if ext is None:
        # Try to recover from the filename when the client forgot
        # to set the header. This is a dev convenience; in prod
        # the operator's browser will always send content_type.
        name = (file.filename or "").lower()
        for guess_ext, guess_mime in (
            ("jpg", "image/jpeg"),
            ("jpeg", "image/jpeg"),
            ("png", "image/png"),
            ("webp", "image/webp"),
            ("svg", "image/svg+xml"),
        ):
            if name.endswith(f".{guess_ext}"):
                mime = guess_mime
                ext = guess_ext
                break
    if ext is None:
        raise HTTPException(status_code=415, detail="unsupported_media_type")

    data = await file.read()
    if len(data) > settings.IMAGE_MAX_BYTES:
        raise HTTPException(status_code=413, detail="file_too_large")

    path = build_storage_path(content_type="media", ext=ext)
    storage = _storage()
    url = await storage.save(path=path, data=data, content_type=mime)
    return Envelope.ok(AdminImageUploadResponse(url=url, path=path))


# ---------------------------------------------------------------------------
# DELETE /api/v1/admin/images
# ---------------------------------------------------------------------------


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_image(
    payload: AdminImageDeleteRequest,
) -> None:
    """Delete an image from storage. 404 on missing path is tolerated."""
    storage = _storage()
    await storage.delete(path=payload.path)


# ---------------------------------------------------------------------------
# GET /api/v1/admin/images/{path:path}  (dev-only static serve)
# ---------------------------------------------------------------------------


# This route is registered on a separate router so it can be
# exempt from the `get_current_admin` gate. Public image bytes
# should be served to anonymous clients (the FE renders the
# `image_url` on /projects/<slug> and /blog/<slug>).
public_router = APIRouter(prefix="/images")


@public_router.get("/{file_path:path}")
async def serve_uploaded_image(file_path: str) -> FileResponse:
    """Stream a file from the local upload dir. Dev-only.

    In production (Supabase backend) the URL is a Supabase public
    URL, so this route is never called. We still register it so
    the `LocalStorage.save()` -> `local_url_for()` -> GET round-trip
    works end-to-end in dev and in the test suite.
    """
    safe = _safe_path_segment(file_path)
    settings = get_settings()
    root = Path(settings.UPLOAD_DIR).resolve()
    full = (root / safe).resolve()
    if not str(full).startswith(str(root)):
        raise HTTPException(status_code=400, detail="bad_request")
    if not full.exists() or not full.is_file():
        raise HTTPException(status_code=404, detail="not_found")
    return FileResponse(full)
