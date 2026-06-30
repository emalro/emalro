"""Helpers for tests/api/* — seed content fixtures.

The fixtures here create one visible project, one visible blog post,
one draft blog post, and a few resume rows (personal, experience,
education, course). Tests use these to assert visibility, envelope,
LocalizedStr, pagination, and tag filtering.

Tests must not rely on the order or presence of other rows; the
``db_engine`` session-scoped fixture drops and recreates the schema
per test, so the seed runs from a clean state every time.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.models.blog import BlogPost
from app.models.contact import ContactMessage
from app.models.project import Project
from app.models.resume import ResumeData
from app.schemas.i18n import LocalizedStr


def _u() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def seed_project(
    session: AsyncSession,
    *,
    slug: str = "apexlogic",
    title: LocalizedStr | None = None,
    description: LocalizedStr | None = None,
    tags: list[str] | None = None,
    is_visible: bool = True,
) -> Project:
    title = title or LocalizedStr(
        es="ApexLogic Retail Warehouse", en="ApexLogic Retail Warehouse"
    )
    description = description or LocalizedStr(es="Descripcion ES", en="Description EN")
    row = Project(
        id=_u(),
        slug=slug,
        title=title.model_dump_json(),
        description=description.model_dump_json(),
        technologies=json.dumps(
            [
                LocalizedStr(es="Excel", en="Excel").model_dump(),
                LocalizedStr(es="PowerBI", en="PowerBI").model_dump(),
            ]
        ),
        tags=json.dumps(tags or ["excel", "powerbi", "dax"]),
        image_url="/img/projects/apexlogic.svg",
        github_url=None,
        demo_url="https://emalro.com.ar/projects/apexlogic",
        is_visible=is_visible,
        created_at=_now(),
        updated_at=_now(),
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def seed_blog_post(
    session: AsyncSession,
    *,
    slug: str = "hello-world",
    title: LocalizedStr | None = None,
    content: LocalizedStr | None = None,
    tags: list[str] | None = None,
    is_visible: bool = True,
    published_at: datetime | None = None,
) -> BlogPost:
    title = title or LocalizedStr(es="Hola mundo", en="Hello world")
    content = content or LocalizedStr(
        es="Este es el contenido en espanol del primer post.",
        en="This is the English content of the first post.",
    )
    row = BlogPost(
        id=_u(),
        slug=slug,
        title=title.model_dump_json(),
        content=content.model_dump_json(),
        cover_image_url=None,
        tags=json.dumps(tags or ["intro", "welcome"]),
        is_visible=is_visible,
        published_at=published_at or _now(),
        created_at=_now(),
        updated_at=_now(),
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def seed_resume_personal(
    session: AsyncSession,
    *,
    extra: dict | None = None,
) -> ResumeData:
    extra = extra or {
        "name": {"es": "Emanuel Romero", "en": "Emanuel Romero"},
        "role": {"es": "Data Analyst", "en": "Data Analyst"},
        "summary": {"es": "Resumen ES", "en": "Summary EN"},
        "avatar_url": "/img/avatar.svg",
        "hardSkills": [{"es": "Python", "en": "Python"}],
        "softSkills": [{"es": "Teamwork", "en": "Teamwork"}],
    }
    row = ResumeData(
        id=_u(),
        section="personal",
        display_order=0,
        title=LocalizedStr(es="Personal", en="Personal").model_dump_json(),
        extra=json.dumps(extra),
        is_visible=True,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def seed_resume_experience(
    session: AsyncSession,
    *,
    organization: str = "Arbusta",
    is_visible: bool = True,
    display_order: int = 0,
) -> ResumeData:
    row = ResumeData(
        id=_u(),
        section="experience",
        display_order=display_order,
        title=LocalizedStr(es="Data Analyst", en="Data Analyst").model_dump_json(),
        subtitle=organization,
        description=LocalizedStr(
            es="Descripcion del trabajo en espanol.",
            en="Job description in English.",
        ).model_dump_json(),
        start_date="2023-05",
        end_date=None,
        is_visible=is_visible,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def seed_resume_education(
    session: AsyncSession,
    *,
    institution: str = "Urquiza",
    is_visible: bool = True,
    display_order: int = 0,
) -> ResumeData:
    row = ResumeData(
        id=_u(),
        section="education",
        display_order=display_order,
        title=LocalizedStr(
            es="Tecnico Superior en Analisis Funcional",
            en="Higher Technician in Functional Analysis",
        ).model_dump_json(),
        subtitle=institution,
        description=LocalizedStr(
            es="Descripcion educacion ES.",
            en="Description education EN.",
        ).model_dump_json(),
        start_date="2026-01",
        end_date=None,
        is_visible=is_visible,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def seed_resume_course(
    session: AsyncSession,
    *,
    platform: str = "Coderhouse",
    name: str = "Data Analytics",
    is_visible: bool = True,
    display_order: int = 0,
) -> ResumeData:
    row = ResumeData(
        id=_u(),
        section="course",
        display_order=display_order,
        title=LocalizedStr(es=name, en=name).model_dump_json(),
        subtitle=platform,
        url="https://example.com/verify",
        description=None,
        is_visible=is_visible,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def seed_contact(
    session: AsyncSession,
    *,
    name: str = "Alice",
    email: str = "alice@example.com",
    subject: str | None = "Hello",
    message: str = "This is a test message that is at least 10 chars.",
    read_at: datetime | None = None,
    deleted_at: datetime | None = None,
) -> ContactMessage:
    row = ContactMessage(
        id=_u(),
        name=name,
        email=email,
        subject=subject,
        message=message,
        ip_address="127.0.0.1",
        user_agent="pytest",
        read_at=read_at,
        deleted_at=deleted_at,
        received_at=_now(),
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row
