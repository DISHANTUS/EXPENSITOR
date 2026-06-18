"""life_lessons (V2 Sprint 4b-5b: companion intelligence — user-taught lessons)

Revision ID: 0019
Revises: 0018
Create Date: 2026-06-17
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PGUUID

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "life_lessons",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", PGUUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lesson", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("source_text", sa.Text(), nullable=True),
        sa.Column("trigger_context", sa.String(length=80), nullable=True),
        sa.Column("occurrences", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("confidence", sa.String(length=10), nullable=False),
        sa.Column("status", sa.String(length=12), nullable=False),
        sa.Column("importance", sa.String(length=20), nullable=False),
        sa.Column("times_surfaced", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("times_helpful", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("first_observed", sa.Date(), nullable=False),
        sa.Column("last_observed", sa.Date(), nullable=False),
        sa.Column("last_surfaced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_life_lessons_user_status", "life_lessons", ["user_id", "status"])
    op.create_index("ix_life_lessons_user_category", "life_lessons", ["user_id", "category"])


def downgrade() -> None:
    op.drop_index("ix_life_lessons_user_category", table_name="life_lessons")
    op.drop_index("ix_life_lessons_user_status", table_name="life_lessons")
    op.drop_table("life_lessons")
