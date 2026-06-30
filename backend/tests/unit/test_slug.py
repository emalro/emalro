"""Slug generation tests.

PR #1 ships a basic slugify implementation (NFD + ASCII + kebab + cap).
The full slugify behavior (collision, manual override) lands in PR #2.
"""

from __future__ import annotations

from app.services.slug import slugify


def test_slugify_lowercases_and_hyphenates():
    assert slugify("Hello World") == "hello-world"


def test_slugify_transliterates_accents():
    assert slugify("Cómo configurar") == "como-configurar"


def test_slugify_strips_punctuation():
    assert slugify("What? Really!") == "what-really"


def test_slugify_uses_questions_to_empty():
    assert slugify("¿Qué es un ORM?") == "que-es-un-orm"


def test_slugify_caps_at_max_length():
    long = "a" * 200
    out = slugify(long, max_length=80)
    assert len(out) == 80
