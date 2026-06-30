"""Pydantic-Settings config for the emalro backend.

Reads all env vars, validates fail-fast invariants, exposes a cached
`get_settings()` for the rest of the app.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All env-driven config for the emalro backend.

    Required vars: DATABASE_URL, SUPABASE_URL, SUPABASE_SERVICE_KEY,
    JWT_SECRET (>= 32 chars).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Required
    DATABASE_URL: str = Field(...)
    SUPABASE_URL: str = Field(...)
    SUPABASE_SERVICE_KEY: str = Field(...)
    JWT_SECRET: str = Field(...)

    # Optional with defaults
    JWT_EXPIRATION_HOURS: int = 8
    ALLOWED_ORIGINS: str = "http://localhost:4321"
    ENV: Literal["dev", "test", "prod"] = "dev"
    CLOUDFLARE_ZONE_ID: str = ""
    CLOUDFLARE_API_TOKEN: str = ""
    PORT: int = 8000
    LOGIN_RATE_LIMIT: str = "5/minute"
    CONTACT_RATE_LIMIT: str = "5/hour"
    IMAGE_MAX_BYTES: int = 5_242_880  # 5 MB

    @field_validator("JWT_SECRET")
    @classmethod
    def _jwt_secret_must_be_long(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError(
                "JWT_SECRET must be at least 32 characters of high-entropy random data"
            )
        return v

    @field_validator("DATABASE_URL")
    @classmethod
    def _pooler_url_in_prod(cls, v: str) -> str:
        # We do not check ENV here because Settings is instantiated before
        # the field is fully validated in some Pydantic v2 paths. The
        # `validate_pooler_for_prod` helper is called explicitly from
        # `validate_settings()` below.
        return v


def validate_settings(settings: Settings) -> None:
    """Cross-field validation. Called once at app startup.

    Fails fast with a clear message if `ENV=prod` and the database URL
    is not the Supabase pooler on port 6543.
    """
    if settings.ENV == "prod":
        if ":6543" not in settings.DATABASE_URL:
            raise RuntimeError(
                "In production, DATABASE_URL must point to the Supabase pooler "
                "on port 6543 (transaction mode). Got: "
                f"{settings.DATABASE_URL!r}"
            )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings instance.

    Tests can clear the cache via `get_settings.cache_clear()` to
    force a re-read after mutating env vars.
    """
    s = Settings()  # type: ignore[call-arg]
    validate_settings(s)
    return s
