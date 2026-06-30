"""Sanitization tests.

PR #1 ships the service scaffold (`app/services/sanitize.py`) and the
basic contract: `sanitize_markdown` strips `<script>` tags. The full
test matrix (per-element allowlist, GFM features, custom tag handling)
lands in PR #2 alongside the blog admin editor.
"""

from __future__ import annotations

from app.services.sanitize import sanitize_markdown


def test_strips_script_tags():
    out = sanitize_markdown("Hello <script>alert(1)</script> world")
    assert "<script>" not in out
    assert "alert" not in out


def test_strips_inline_event_handlers():
    out = sanitize_markdown('<a href="x" onclick="evil()">link</a>')
    assert "onclick" not in out


def test_preserves_safe_markdown():
    out = sanitize_markdown("**bold** and _italic_ and `code`")
    # PR #1's scaffold runs nh3.clean over the raw markdown source.
    # Full marked → nh3 pipeline lands in PR #2. The contract for PR #1
    # is: nothing dangerous survives. Markdown syntax is preserved as
    # text (it is rendered on the frontend).
    assert "**bold**" in out
    assert "_italic_" in out
    assert "code" in out


def test_returns_empty_string_for_empty_input():
    assert sanitize_markdown("") == ""
