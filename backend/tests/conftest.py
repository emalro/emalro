"""Shared pytest fixtures.

Tests use an in-process SQLite database (via aiosqlite) so they run
without Docker / Postgres. The async engine is created lazily and
rebuilt per test session to avoid cross-test state leakage.

The `Settings.DATABASE_URL` env var is monkey-patched BEFORE `Settings`
is instantiated; the lru_cache on `get_settings` is cleared on
session start.
"""

from __future__ import annotations

import os
import uuid

# Set DATABASE_URL before importing the app.
os.environ.setdefault(
    "DATABASE_URL", "sqlite+aiosqlite:///./_test_emalro.db"
)
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "test-service-key")
# A 64-char secret (well over the 32-char minimum).
os.environ.setdefault(
    "JWT_SECRET", "x" * 64
)
os.environ.setdefault("ENV", "test")
# High rate limit so tests don't trip slowapi's window.
os.environ.setdefault("LOGIN_RATE_LIMIT", "1000/minute")

import asyncio
import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

from app.core.config import get_settings
from app.core.db import get_session_factory, reset_engine_for_tests
from app.core.security import get_password_hash
from app.main import create_app
from app.models.admin_user import AdminUser


@pytest.fixture(scope="session")
def event_loop():
    """Single asyncio loop for the whole test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
def _configure_test_db():
    """Point the settings at a fresh SQLite file, drop+create schema."""
    # Wipe any stale DB file from a previous run.
    db_path = "./_test_emalro.db"
    if os.path.exists(db_path):
        os.remove(db_path)

    # Force a fresh Settings instance.
    get_settings.cache_clear()
    reset_engine_for_tests()

    yield

    # Tear down
    reset_engine_for_tests()
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest_asyncio.fixture
async def db_engine():
    """Return a fresh async engine for the test (one per test)."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///./_test_emalro.db",
        echo=False,
    )
    async with engine.begin() as conn:
        # Import all models so SQLModel.metadata sees them.
        from app import models  # noqa: F401

        await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine):
    """Yield a fresh AsyncSession bound to the test engine."""
    factory = async_sessionmaker(  # type: ignore[var-annotated]
        bind=db_engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )
    async with factory() as session:
        yield session


@pytest.fixture
def app(db_engine):
    """Build a FastAPI app instance wired to the test DB engine."""
    # Patch the engine reference so `get_session()` uses ours.
    import app.core.db as db_mod

    db_mod._engine = db_engine  # type: ignore[attr-defined]
    db_mod._SessionLocal = async_sessionmaker(  # type: ignore[attr-defined]
        bind=db_engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )
    return create_app()


@pytest.fixture
def client(app):
    """Return a TestClient bound to the test app."""
    return TestClient(app)


@pytest_asyncio.fixture
async def admin_user(db_session) -> AdminUser:
    """Create and return a single admin user for tests."""
    user = AdminUser(
        id=str(uuid.uuid4()),
        email="admin@emalro.com.ar",
        password_hash=get_password_hash("S3cr3t!Pass"),
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user
