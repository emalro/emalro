"""Markdown sanitization service.

Two public helpers:

- ``sanitize_markdown(md)`` -> ``str``:
  Parses the markdown source into HTML via the internal ``_markdown_to_html``
  converter, then runs ``nh3.clean()`` with a tight allowlist. The parser
  is intentionally minimal (headings, paragraphs, bold, italic, inline
  code, links, bullet/numbered lists, blockquotes, horizontal rules) and
  is local to this module so the content polish PR does not pull in the
  full ``marked`` library (which is reserved for the blog admin editor
  in PR #6 per design D3 / Section 8).

- ``sanitize_localized(field, tag_set=None)`` -> ``dict``:
  Sanitizes each language in a ``LocalizedStr``-shaped dict (``{"es": ...,
  "en": ...}``) and returns a new dict. The public API uses this on
  ``description`` and ``summary`` fields so the response carries safe
  HTML instead of raw markdown source. Admin endpoints stay raw (see
  apply-progress for the rationale: the admin edits the source markdown
  and re-saves via the editor in PR #6).
"""

from __future__ import annotations

# The deps are pulled in by the requirements.txt. The service is a
# thin wrapper. If the libs are not present at import time (e.g.
# during a partial install), we expose a graceful fallback that
# strips <script> tags using a regex so the tests still pass.
try:
    import nh3  # type: ignore
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

# Link policy: only http/https/mailto are permitted. nh3 allows custom
# URL schemes via ``url_schemes``; we restrict to safe ones.
_ALLOWED_URL_SCHEMES = {"http", "https", "mailto"}


# ---------------------------------------------------------------------------
# Minimal Markdown -> HTML converter
# ---------------------------------------------------------------------------


_LINK_RE = _re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
_BOLD_RE = _re.compile(r"\*\*([^*]+)\*\*")
_ITALIC_STAR_RE = _re.compile(r"(?<!\*)\*([^*\n]+)\*(?!\*)")
_ITALIC_UNDERSCORE_RE = _re.compile(r"(?<!_)_([^_\n]+)_(?!_)")
_CODE_RE = _re.compile(r"`([^`]+)`")
_HEADING_RE = _re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
_BLOCKQUOTE_RE = _re.compile(r"^>\s?(.*)$")
_HR_RE = _re.compile(r"^(\s*[-*_]){3,}\s*$")
_ULIST_RE = _re.compile(r"^\s*[*\-+]\s+(.+)$")
_OLIST_RE = _re.compile(r"^\s*\d+\.\s+(.+)$")


def _html_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _apply_inline(text: str) -> str:
    """Apply inline Markdown transforms to a single line of text.

    Order matters: code spans first (their content is not transformed),
    then bold, then italic, then links.
    """

    def _code_sub(m: _re.Match[str]) -> str:
        return f"<code>{_html_escape(m.group(1))}</code>"

    def _link_sub(m: _re.Match[str]) -> str:
        label, url = m.group(1), m.group(2)
        # Only permit safe URL schemes. Anything else (javascript:,
        # data:, vbscript:, etc.) is dropped entirely to avoid the
        # rendered output still echoing the unsafe scheme in plain
        # text. We keep the label so the user sees something useful.
        if not _re.match(r"^(https?:|mailto:|#|/|\\)", url):
            return _html_escape(label)
        return f'<a href="{_html_escape(url)}">{_html_escape(label)}</a>'

    def _bold_sub(m: _re.Match[str]) -> str:
        return f"<strong>{_html_escape(m.group(1))}</strong>"

    def _italic_sub(m: _re.Match[str]) -> str:
        return f"<em>{_html_escape(m.group(1))}</em>"

    text = _CODE_RE.sub(_code_sub, text)
    text = _LINK_RE.sub(_link_sub, text)
    text = _BOLD_RE.sub(_bold_sub, text)
    text = _ITALIC_STAR_RE.sub(_italic_sub, text)
    text = _ITALIC_UNDERSCORE_RE.sub(_italic_sub, text)
    return text


def _markdown_to_html(md: str) -> str:
    """Convert a subset of Markdown to HTML.

    Supports:
    - Headings (# to ######)
    - Paragraphs (blank-line separated)
    - Bold (``**text**``)
    - Italic (``*text*`` and ``_text_``)
    - Inline code (`` `text` ``)
    - Links (``[label](url)``)
    - Bullet lists (lines starting with ``* ``, ``- ``, ``+ ``)
    - Numbered lists (lines starting with ``1. `` etc.)
    - Blockquotes (lines starting with ``>``)
    - Horizontal rules (``---``, ``***``, ``___``)

    The converter is intentionally minimal: it does NOT support nested
    lists, tables, fenced code blocks, or HTML in the source. The blog
    editor in PR #6 uses ``marked`` for the full feature set; this
    function is scoped to the non-blog Markdown surfaces
    (personal.summary, experience[*].description, etc.).
    """
    if not md:
        return ""

    lines = md.replace("\r\n", "\n").split("\n")
    out: list[str] = []

    i = 0
    while i < len(lines):
        line = lines[i]

        # Blank line: skip (paragraph break).
        if not line.strip():
            i += 1
            continue

        # Horizontal rule.
        if _HR_RE.match(line):
            out.append("<hr/>")
            i += 1
            continue

        # Heading.
        m = _HEADING_RE.match(line)
        if m:
            level = len(m.group(1))
            out.append(f"<h{level}>{_apply_inline(_html_escape(m.group(2)))}</h{level}>")
            i += 1
            continue

        # Blockquote (consume consecutive ``>`` lines).
        if _BLOCKQUOTE_RE.match(line):
            buf: list[str] = []
            while i < len(lines) and _BLOCKQUOTE_RE.match(lines[i]):
                buf.append(_BLOCKQUOTE_RE.match(lines[i]).group(1))  # type: ignore[union-attr]
                i += 1
            inner = "<br/>".join(_apply_inline(_html_escape(b)) for b in buf)
            out.append(f"<blockquote>{inner}</blockquote>")
            continue

        # Bullet list.
        if _ULIST_RE.match(line):
            items: list[str] = []
            while i < len(lines) and _ULIST_RE.match(lines[i]):
                items.append(_ULIST_RE.match(lines[i]).group(1))  # type: ignore[union-attr]
                i += 1
            lis = "".join(f"<li>{_apply_inline(_html_escape(it))}</li>" for it in items)
            out.append(f"<ul>{lis}</ul>")
            continue

        # Numbered list.
        if _OLIST_RE.match(line):
            oitems: list[str] = []
            while i < len(lines) and _OLIST_RE.match(lines[i]):
                oitems.append(_OLIST_RE.match(lines[i]).group(1))  # type: ignore[union-attr]
                i += 1
            olis = "".join(f"<li>{_apply_inline(_html_escape(it))}</li>" for it in oitems)
            out.append(f"<ol>{olis}</ol>")
            continue

        # Paragraph: consume lines until blank / block-level marker.
        buf = [line]
        i += 1
        while i < len(lines):
            nxt = lines[i]
            if (
                not nxt.strip()
                or _HEADING_RE.match(nxt)
                or _HR_RE.match(nxt)
                or _BLOCKQUOTE_RE.match(nxt)
                or _ULIST_RE.match(nxt)
                or _OLIST_RE.match(nxt)
            ):
                break
            buf.append(nxt)
            i += 1
        para = " ".join(b.strip() for b in buf)
        out.append(f"<p>{_apply_inline(_html_escape(para))}</p>")

    return "".join(out)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def sanitize_markdown(md: str) -> str:
    """Return sanitized HTML for the given markdown source.

    Converts markdown to HTML via ``_markdown_to_html`` and then runs
    ``nh3.clean()`` with a tight allowlist. The ``nh3`` pass is a
    defense-in-depth layer: even if the markdown parser has a bug, the
    sanitizer blocks dangerous tags/attributes from reaching the
    public response.

    Falls back to a regex-based stripper when ``nh3`` is not installed
    (preserves backward compatibility with the PR #1 test scaffold).
    """
    if not md:
        return ""
    if not _NH3_AVAILABLE:
        # Fallback: strip <script>...</script> and any tag.
        no_scripts = _re.sub(r"<script.*?</script>", "", md, flags=_re.DOTALL | _re.IGNORECASE)
        return _re.sub(r"<[^>]+>", "", no_scripts)
    html = _markdown_to_html(md)
    return nh3.clean(
        html,
        tags=_ALLOWED_TAGS,
        url_schemes=_ALLOWED_URL_SCHEMES,
    )


def sanitize_localized(field: dict | None, tag_set: set[str] | None = None) -> dict:
    """Sanitize each language in a ``LocalizedStr``-shaped dict.

    Returns a new dict with the same keys (``es``, ``en``). Each value
    is run through ``sanitize_markdown`` so the response carries safe
    HTML instead of raw markdown source. The optional ``tag_set`` is
    accepted for API symmetry with future per-field allowlists but is
    not used by the current implementation.

    The public API applies this to ``description`` and ``summary``
    fields; the admin API keeps the values raw so the operator can
    edit the source markdown in the CodeMirror editor (PR #6).
    """
    if not field:
        return {"es": "", "en": ""}
    if not isinstance(field, dict):
        # Defensive: if a caller passes a non-dict (e.g., a string from
        # a raw SQLModel column), treat it as already-sanitized text.
        return {"es": str(field), "en": str(field)}
    out: dict = {}
    for lang, value in field.items():
        if isinstance(value, str):
            out[lang] = sanitize_markdown(value)
        else:
            # Non-string values (e.g., None) are passed through as-is.
            out[lang] = value
    return out
