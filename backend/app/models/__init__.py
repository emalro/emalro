"""SQLModel ORM models.

Importing this package populates `SQLModel.metadata` for Alembic
autogenerate and for the runtime `Base.metadata.create_all` path.
"""

from app.models.admin_user import AdminUser
from app.models.blog import BlogPost
from app.models.contact import ContactMessage, ContactStatus
from app.models.project import Project
from app.models.resume import ResumeData

__all__ = [
    "AdminUser",
    "BlogPost",
    "ContactMessage",
    "ContactStatus",
    "Project",
    "ResumeData",
]
