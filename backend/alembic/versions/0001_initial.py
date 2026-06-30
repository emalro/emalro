"""Initial schema: 5 tables + indexes.

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-30 13:30:00.000000

This is the first Alembic migration for the emalro backend. It
creates:

- ``admin_users`` (from PR #1; carried forward for the first
  migration so the schema is complete).
- ``projects`` (PR #2): portfolio entries with bilingual title +
  description, technologies, tags, optional URLs, is_visible.
- ``blog_posts`` (PR #2): blog entries with bilingual title +
  content, cover image, tags, is_visible, published_at.
- ``resume_data`` (PR #2): CV entries grouped by section
  (personal / experience / education / course), each with
  bilingual title + description, optional dates, image, URL, etc.
- ``contact_messages`` (PR #2): contact-form submissions with
  read_at / deleted_at timestamps for the inbox / trash lifecycle.

GIN indexes on ``projects.tags`` and ``blog_posts.tags`` are
required for the ``/api/v1/explore`` tag-filter query. GIN is
Postgres-specific, so the migration checks the dialect and skips
the GIN index on SQLite (used in tests).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # ---------------------------------------------------------------------------
    # admin_users (carried forward from PR #1)
    # ---------------------------------------------------------------------------
    op.create_table(
        "admin_users",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_admin_users_email", "admin_users", ["email"], unique=True)

    # ---------------------------------------------------------------------------
    # projects
    # ---------------------------------------------------------------------------
    op.create_table(
        "projects",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("description", sa.String(length=10_000), nullable=False),
        sa.Column("technologies", sa.String(length=10_000), nullable=False, server_default="[]"),
        sa.Column("tags", sa.String(length=10_000), nullable=False, server_default="[]"),
        sa.Column("image_url", sa.String(length=500), nullable=True),
        sa.Column("github_url", sa.String(length=500), nullable=True),
        sa.Column("demo_url", sa.String(length=500), nullable=True),
        sa.Column("is_visible", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_projects_slug", "projects", ["slug"], unique=True)
    op.create_index("ix_projects_is_visible", "projects", ["is_visible"])
    if is_postgres:
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_projects_tags "
            "ON projects USING gin (tags jsonb_path_ops)"
        )

    # ---------------------------------------------------------------------------
    # blog_posts
    # ---------------------------------------------------------------------------
    op.create_table(
        "blog_posts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("content", sa.String(length=200_000), nullable=False),
        sa.Column("cover_image_url", sa.String(length=500), nullable=True),
        sa.Column("tags", sa.String(length=10_000), nullable=False, server_default="[]"),
        sa.Column("is_visible", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_blog_posts_slug", "blog_posts", ["slug"], unique=True)
    op.create_index("ix_blog_posts_is_visible", "blog_posts", ["is_visible"])
    op.create_index("ix_blog_posts_published_at", "blog_posts", ["published_at"])
    if is_postgres:
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_blog_posts_tags "
            "ON blog_posts USING gin (tags jsonb_path_ops)"
        )

    # ---------------------------------------------------------------------------
    # resume_data
    # ---------------------------------------------------------------------------
    op.create_table(
        "resume_data",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("section", sa.String(length=32), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("subtitle", sa.String(length=200), nullable=True),
        sa.Column("description", sa.String(length=10_000), nullable=True),
        sa.Column("start_date", sa.String(length=7), nullable=True),
        sa.Column("end_date", sa.String(length=7), nullable=True),
        sa.Column("url", sa.String(length=500), nullable=True),
        sa.Column("image_url", sa.String(length=500), nullable=True),
        sa.Column("tags", sa.String(length=10_000), nullable=False, server_default="[]"),
        sa.Column("is_visible", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("extra", sa.String(length=10_000), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_resume_data_section", "resume_data", ["section"])
    op.create_index("ix_resume_data_is_visible", "resume_data", ["is_visible"])

    # ---------------------------------------------------------------------------
    # contact_messages
    # ---------------------------------------------------------------------------
    op.create_table(
        "contact_messages",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("subject", sa.String(length=200), nullable=True),
        sa.Column("message", sa.String(length=5_000), nullable=False),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_contact_messages_email", "contact_messages", ["email"])
    op.create_index("ix_contact_messages_read_at", "contact_messages", ["read_at"])
    op.create_index("ix_contact_messages_deleted_at", "contact_messages", ["deleted_at"])
    op.create_index("ix_contact_messages_received_at", "contact_messages", ["received_at"])


def downgrade() -> None:
    op.drop_index("ix_contact_messages_received_at", table_name="contact_messages")
    op.drop_index("ix_contact_messages_deleted_at", table_name="contact_messages")
    op.drop_index("ix_contact_messages_read_at", table_name="contact_messages")
    op.drop_index("ix_contact_messages_email", table_name="contact_messages")
    op.drop_table("contact_messages")

    op.drop_index("ix_resume_data_is_visible", table_name="resume_data")
    op.drop_index("ix_resume_data_section", table_name="resume_data")
    op.drop_table("resume_data")

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_blog_posts_tags")
        op.execute("DROP INDEX IF EXISTS ix_projects_tags")
    op.drop_index("ix_blog_posts_published_at", table_name="blog_posts")
    op.drop_index("ix_blog_posts_is_visible", table_name="blog_posts")
    op.drop_index("ix_blog_posts_slug", table_name="blog_posts")
    op.drop_table("blog_posts")

    op.drop_index("ix_projects_is_visible", table_name="projects")
    op.drop_index("ix_projects_slug", table_name="projects")
    op.drop_table("projects")

    op.drop_index("ix_admin_users_email", table_name="admin_users")
    op.drop_table("admin_users")
