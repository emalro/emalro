"""URL-friendly slug generator.

Strategy: NFD normalize -> strip diacritics -> lowercase -> replace
non-alphanumeric runs with hyphens -> trim hyphens -> cap length.

Used by the admin blog editor (PR #6) for auto-suggest; the user
can always override. Slugs are always English, even when the source
title is Spanish.
"""

from __future__ import annotations

import re
import unicodedata


def slugify(title_es: str, max_length: int = 80) -> str:
    """Return a kebab-case ASCII slug for the given source text."""
    if not title_es:
        return ""
    normalized = unicodedata.normalize("NFD", title_es)
    ascii_str = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_str.lower())
    return slug.strip("-")[:max_length]
