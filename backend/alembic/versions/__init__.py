"""Alembic migration versions.

PR #1 ships the empty `versions/` directory. PR #2 lands the first
real migration `0001_initial.py` which creates the 5 tables (admin_users,
projects, blog_posts, resume_data, contact_messages) and the GIN
indexes on the `tags` columns.
"""
