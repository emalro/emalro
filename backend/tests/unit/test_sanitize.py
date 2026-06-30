"""Sanitization tests.

Covers the ``sanitize_markdown`` and ``sanitize_localized`` helpers in
``app/services/sanitize``. The service converts markdown to HTML via
the local parser and then runs ``nh3.clean()`` with a tight allowlist
(per the design's Markdown XSS mitigation, RNF-02).
"""

from __future__ import annotations

from app.services.sanitize import sanitize_localized, sanitize_markdown


# ---------------------------------------------------------------------------
# sanitize_markdown — Markdown rendering
# ---------------------------------------------------------------------------


def test_renders_bold_to_strong():
    out = sanitize_markdown("**bold** and not bold")
    assert "<strong>bold</strong>" in out
    assert "**" not in out


def test_renders_italic_to_em():
    out = sanitize_markdown("*italic* and _also italic_")
    assert "<em>italic</em>" in out
    assert "<em>also italic</em>" in out


def test_renders_bullet_list_to_ul():
    out = sanitize_markdown("* alpha\n* beta\n* gamma")
    assert out == "<ul><li>alpha</li><li>beta</li><li>gamma</li></ul>"


def test_renders_numbered_list_to_ol():
    out = sanitize_markdown("1. one\n2. two\n3. three")
    assert out == "<ol><li>one</li><li>two</li><li>three</li></ol>"


def test_renders_safe_link_to_anchor():
    out = sanitize_markdown("see [Arbusta](https://arbusta.net/) for context")
    assert 'href="https://arbusta.net/"' in out
    assert ">Arbusta</a>" in out


def test_renders_relative_link():
    out = sanitize_markdown("go [home](/) now")
    assert 'href="/"' in out
    assert ">home</a>" in out


def test_strips_unsafe_link_schemes():
    out = sanitize_markdown("evil [click](javascript:alert(1)) trap")
    # The unsafe URL is dropped; the label survives as plain text.
    assert "javascript:" not in out
    assert "<a " not in out
    assert "click" in out


def test_strips_data_url_schemes():
    out = sanitize_markdown("[pic](data:text/html,<script>alert(1)</script>)")
    assert "data:" not in out
    assert "<script" not in out
    assert "<a " not in out


def test_renders_inline_code():
    out = sanitize_markdown("run `pytest` and watch")
    assert "<code>pytest</code>" in out


def test_renders_paragraphs_separated_by_blank_lines():
    out = sanitize_markdown("first paragraph.\n\nsecond paragraph.")
    assert out == "<p>first paragraph.</p><p>second paragraph.</p>"


def test_renders_heading():
    out = sanitize_markdown("## Section title")
    assert out == "<h2>Section title</h2>"


def test_renders_blockquote():
    out = sanitize_markdown("> quoted text")
    assert out == "<blockquote>quoted text</blockquote>"


def test_renders_horizontal_rule():
    out = sanitize_markdown("---")
    assert "<hr" in out and "</hr>" not in out


# ---------------------------------------------------------------------------
# sanitize_markdown — XSS hardening
# ---------------------------------------------------------------------------


def test_escapes_html_in_source():
    out = sanitize_markdown("5 < 6 and 6 > 5")
    assert "&lt;" in out
    assert "&gt;" in out


def test_strips_script_tags_from_source():
    # Markdown source that mentions <script> is escaped, not executed.
    out = sanitize_markdown("Hello <script>alert(1)</script> world")
    assert "<script" not in out
    # The literal text is preserved (escaped), not the tag.
    assert "&lt;script" in out


def test_strips_inline_event_handlers_from_source():
    # Markdown source with raw HTML containing onclick is escaped.
    out = sanitize_markdown('<a href="x" onclick="evil()">link</a>')
    # No real <a tag survives (the source is escaped as text).
    assert "<a " not in out
    # The literal text is preserved (escaped), not the tag.
    assert "&lt;a " in out


def test_returns_empty_string_for_empty_input():
    assert sanitize_markdown("") == ""


def test_returns_empty_string_for_whitespace():
    assert sanitize_markdown("   \n\n   ") == ""


# ---------------------------------------------------------------------------
# sanitize_localized
# ---------------------------------------------------------------------------


def test_sanitize_localized_sanitizes_each_language():
    field = {
        "es": "**hola** y *adios*",
        "en": "**hello** and *bye*",
    }
    out = sanitize_localized(field)
    assert out["es"] == "<p><strong>hola</strong> y <em>adios</em></p>"
    assert out["en"] == "<p><strong>hello</strong> and <em>bye</em></p>"


def test_sanitize_localized_preserves_keys():
    field = {"es": "* item", "en": "* other item"}
    out = sanitize_localized(field)
    assert set(out.keys()) == {"es", "en"}


def test_sanitize_localized_renders_bullets_to_html():
    field = {
        "es": "* limpiar datos\n* crear dashboards",
        "en": "* clean data\n* build dashboards",
    }
    out = sanitize_localized(field)
    assert out["es"] == "<ul><li>limpiar datos</li><li>crear dashboards</li></ul>"
    assert out["en"] == "<ul><li>clean data</li><li>build dashboards</li></ul>"


def test_sanitize_localized_empty_input_returns_empty_dict():
    out = sanitize_localized(None)
    assert out == {"es": "", "en": ""}


def test_sanitize_localized_empty_dict_returns_empty_dict():
    out = sanitize_localized({})
    assert out == {"es": "", "en": ""}


def test_sanitize_localized_strips_xss_in_either_language():
    field = {
        "es": "**click** [me](javascript:alert(1))",
        "en": "**click** [me](javascript:alert(1))",
    }
    out = sanitize_localized(field)
    assert "javascript:" not in out["es"]
    assert "javascript:" not in out["en"]
