"""JSONB contract test — `LocalizedStr` shape on every localizable field.

This is the single most important contract test in the project
(per design-appendices A2). PR #1 covers the model-level invariants;
PR #2 extends the matrix to walk every public endpoint.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas.i18n import LocalizedStr

FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "i18n_shape.json"


def test_localized_str_accepts_valid_shape():
    ls = LocalizedStr(es="Hola", en="Hello")
    assert ls.es == "Hola"
    assert ls.en == "Hello"


def test_localized_str_rejects_flat_string():
    with pytest.raises(ValidationError):
        LocalizedStr.model_validate("just a string")  # type: ignore[arg-type]


def test_localized_str_rejects_extra_keys():
    with pytest.raises(ValidationError):
        LocalizedStr.model_validate({"es": "X", "en": "Y", "pt": "Z"})


def test_localized_str_rejects_empty_es():
    with pytest.raises(ValidationError):
        LocalizedStr.model_validate({"es": "", "en": "X"})


def test_localized_str_rejects_whitespace_only_es():
    with pytest.raises(ValidationError):
        LocalizedStr.model_validate({"es": "   ", "en": "X"})


def test_localized_str_allows_empty_en_for_fallback():
    ls = LocalizedStr.model_validate({"es": "Solo espanol", "en": ""})
    assert ls.en == ""


def test_localized_str_rejects_overlong_en():
    with pytest.raises(ValidationError):
        LocalizedStr.model_validate({"es": "X", "en": "y" * 5001})


def test_fixture_file_matches_contract():
    """The shared `i18n_shape.json` fixture validates the same way."""
    raw = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    # LocalizedStr is valid.
    LocalizedStr.model_validate(raw["LocalizedStr"])

    # Extra key is rejected.
    with pytest.raises(ValidationError):
        LocalizedStr.model_validate(raw["InvalidExtra"])

    # Empty es is rejected.
    with pytest.raises(ValidationError):
        LocalizedStr.model_validate(raw["EmptyEs"])

    # Empty en is allowed (silent fallback).
    LocalizedStr.model_validate(raw["EmptyEnFallback"])
