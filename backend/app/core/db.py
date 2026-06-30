"""Async SQLAlchemy engine + session factory.

The engine points at the Supabase pooler (port 6543) in production or
the local Postgres (port 5432) in development. `pool_pre_ping=True`
guards against stale connections on the pooler.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Optional

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlmodel import SQLModel

from app.core.config import get_settings

_engine: Optional[AsyncEngine] = None
_SessionLocal: Optional[async_sessionmaker[AsyncSession]] = None


def _create_engine() -> AsyncEngine:
    settings = get_settings()
    url = settings.DATABASE_URL
    # SQLite (used in tests) needs `check_same_thread=False`.
    connect_args: dict = {}
    if url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
    return create_async_engine(
        url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        connect_args=connect_args,
        echo=False,
    )


def get_engine() -> AsyncEngine:
    """Return the process-wide async engine (created lazily)."""
    global _engine
    if _engine is None:
        _engine = _create_engine()
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the session factory (created lazily alongside the engine)."""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = async_sessionmaker(
            bind=get_engine(),
            expire_on_commit=False,
            class_=AsyncSession,
        )
    return _SessionLocal


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: yield a session, roll back on exception."""
    SessionLocal = get_session_factory()
    async with SessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


def reset_engine_for_tests() -> None:
    """Drop the cached engine and session factory (test helper)."""
    global _engine, _SessionLocal
    _engine = None
    _SessionLocal = None


# Importing models is what populates SQLModel.metadata for Alembic.
# Keep the import here so `Base.metadata.create_all(...)` and Alembic
# autogenerate see the table definitions.
def _ensure_metadata_populated() -> None:
    # Imported lazily to avoid a circular import at module load.
    from app import models  # noqa: F401

    SQLModel.metadata  # touch to silence linters


_ensure_metadata_populated()
