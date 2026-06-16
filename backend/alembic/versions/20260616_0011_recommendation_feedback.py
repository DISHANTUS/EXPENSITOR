"""recommendation_feedback (C7b: Preference Memory)

Revision ID: 0011
Revises: 0010
Create Date: 2026-06-16
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "recommendation_feedback",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recommendation_id", sa.String(length=120), nullable=False),
        sa.Column("lever_key", sa.String(length=80), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("reason", sa.String(length=20), nullable=True),
        sa.Column("reason_context", sa.Text(), nullable=True),
        sa.Column("emotional_importance", sa.String(length=20), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("context", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_recommendation_feedback_user_id_users", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_recommendation_feedback"),
    )
    op.create_index("ix_recommendation_feedback_user_id_lever_key", "recommendation_feedback", ["user_id", "lever_key"])
    op.create_index("ix_recommendation_feedback_user_id_created_at", "recommendation_feedback", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_recommendation_feedback_user_id_created_at", table_name="recommendation_feedback")
    op.drop_index("ix_recommendation_feedback_user_id_lever_key", table_name="recommendation_feedback")
    op.drop_table("recommendation_feedback")
