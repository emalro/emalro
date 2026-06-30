"""LocalizedStr Pydantic model — the single source of truth for the JSONB
`{"es": str, "en": str}` shape on the backend.

The contract is locked by the `i18n-shape` spec (obs 301). `extra="forbid"`
guarantees the shape stays exactly two keys; `es` is required non-empty
and `en` is allowed to be empty for the silent-fallback rule.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LocalizedStr(BaseModel):
    """The canonical JSONB localizable string shape.

    `es` is required and must be non-empty (after strip).
    `en` may be empty for the silent English fallback.
    `extra="forbid"` rejects any key beyond `es` and `en`.
    """

    model_config = ConfigDict(extra="forbid")

    es: str = Field(..., description="Spanish value (required, non-empty)")
    en: str = Field(default="", description="English value (may be empty for fallback)")

    @field_validator("es")
    @classmethod
    def _es_must_be_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("es must be a non-empty string")
        return v

    @field_validator("en")
    @classmethod
    def _en_must_fit(cls, v: str) -> str:
        if len(v) > 5000:
            raise ValueError("en must be 5000 characters or fewer")
        return v
