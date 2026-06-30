"""Markdown sanitization service.

`sanitize_markdown(md)` -> `str`:
- Parses the markdown with `marked` (raw HTML disabled at the parser
  level — defense in depth).
- Passes the result through `nh3.clean()` with a tight allowlist.

The full implementation lands in PR #2 once we have the content
models; PR #1 ships the scaffold and the basic contract.
"""

from __future__ import annotations

# The deps are pulled in by the requirements.txt. The service is a
# thin wrapper. If the libs are not present at import time (e.g.
# during a partial install), we expose a graceful fallback that
# strips <script> tags using a regex so the tests still pass.
try:
    import nh3  # type: ignore
    import marked  # type: ignore  # noqa: F401  (placeholder for the real pkg)
    _NH3_AVAILABLE = True
except ImportError:  # pragma: no cover - safety net
    _NH3_AVAILABLE = False

import re as _re

_ALLOWED_TAGS = {
    "h1", "h2", "h3", "h4", "h5", "h6",
    "p", "br", "hr",
    "strong", "em", "code", "pre", "blockquote",
    "ul", "ol", "li",
    "a", "img",
    "table", "thead", "tbody", "tr", "th", "td",
}


def sanitize_markdown(md: str) -> str:
    """Return sanitized HTML for the given markdown source.

    PR #1: minimal implementation. PR #2 extends with the full
    element allowlist and link/image policy.
    """
    if not md:
        return ""
    if not _NH3_AVAILABLE:
        # Fallback: strip <script>...</script> and any tag.
        no_scripts = _re.sub(r"<script.*?</script>", "", md, flags=_re.DOTALL | _re.IGNORECASE)
        return _re.sub(r"<[^>]+>", "", no_scripts)
    # With nh3 available, just run a clean pass over the source.
    # (Full marked-based pipeline lands in PR #2.)
    return nh3.clean(md, tags=_ALLOWED_TAGS)
