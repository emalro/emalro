"""One-shot admin user provisioning CLI.

Usage:
    python -m app.scripts.create_admin <email> <password>

The script is idempotent: re-running with the same email updates the
existing row's password hash. A password shorter than 8 characters is
rejected with a non-zero exit code.

No business logic lives here — this is a pure operator tool.
"""

from __future__ import annotations

import asyncio
import re
import sys

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.db import get_session_factory
from app.core.security import get_password_hash
from app.models.admin_user import AdminUser

_MIN_PASSWORD_LEN = 8
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _validate_email(email: str) -> None:
    if not _EMAIL_RE.match(email):
        raise ValueError(f"Invalid email: {email!r}")


def _validate_password(password: str) -> None:
    if len(password) < _MIN_PASSWORD_LEN:
        raise ValueError(
            f"Password must be at least {_MIN_PASSWORD_LEN} characters"
        )


async def _upsert_admin(email: str, password: str) -> str:
    """Upsert the admin row. Returns 'created' or 'updated'."""
    from app.core.db import get_engine
    from sqlmodel import SQLModel

    # Defensive: ensure schema exists. In a real deployment the operator
    # has run `alembic upgrade head` first; this branch covers the
    # one-off local setup where someone is bootstrapping from scratch.
    engine = get_engine()
    try:
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)
    except Exception:  # pragma: no cover - non-fatal
        pass

    SessionLocal = get_session_factory()
    async with SessionLocal() as session:  # type: AsyncSession
        result = await session.execute(
            select(AdminUser).where(AdminUser.email == email.lower())
        )
        existing = result.scalar_one_or_none()
        if existing is None:
            admin = AdminUser(
                email=email.lower(),
                password_hash=get_password_hash(password),
                is_active=True,
            )
            session.add(admin)
            await session.commit()
            return "created"
        existing.password_hash = get_password_hash(password)
        existing.is_active = True
        session.add(existing)
        await session.commit()
        return "updated"


async def _run(email: str, password: str) -> int:
    try:
        _validate_email(email)
        _validate_password(password)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    try:
        outcome = await _upsert_admin(email, password)
    except Exception as exc:  # pragma: no cover - operational
        print(f"Database error: {exc}", file=sys.stderr)
        return 1

    verb = "created" if outcome == "created" else "updated"
    print(f"Admin user {email} {verb}")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if len(argv) != 2:
        print(
            "Usage: python -m app.scripts.create_admin <email> <password>",
            file=sys.stderr,
        )
        return 2
    return asyncio.run(_run(argv[0], argv[1]))


if __name__ == "__main__":
    sys.exit(main())
