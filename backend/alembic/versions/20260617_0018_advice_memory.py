"""advice_memory (V2 Sprint 4b-5a: core learning loop — tracked advice + follow-ups)

Revision ID: 0018
Revises: 0017
Create Date: 2026-06-17
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "advice_memory",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", PGUUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("importance", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("subject_type", sa.String(length=40), nullable=False),
        sa.Column("subject_id", PGUUID(as_uuid=True), nullable=True),
        sa.Column("subject_label", sa.String(length=120), nullable=True),
        sa.Column("lever_key", sa.String(length=80), nullable=True),
        sa.Column("category_id", PGUUID(as_uuid=True), nullable=True),
        sa.Column("claim", sa.Text(), nullable=False),
        sa.Column("expected_value", sa.Numeric(18, 4), nullable=True),
        sa.Column("expected_date", sa.Date(), nullable=True),
        sa.Column("assumptions", JSONB(), nullable=True),
        sa.Column("follow_up_due", sa.Date(), nullable=True),
        sa.Column("follow_up_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("answer", sa.String(length=20), nullable=True),
        sa.Column("answer_detail", sa.Text(), nullable=True),
        sa.Column("circumstance", sa.String(length=40), nullable=True),
        sa.Column("outcome_id", PGUUID(as_uuid=True), sa.ForeignKey("outcomes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("base_currency", sa.String(length=3), nullable=True),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_advice_memory_user_status_due", "advice_memory", ["user_id", "status", "follow_up_due"])
    op.create_index("ix_advice_memory_user_subject", "advice_memory", ["user_id", "subject_type", "subject_label"])


def downgrade() -> None:
    op.drop_index("ix_advice_memory_user_subject", table_name="advice_memory")
    op.drop_index("ix_advice_memory_user_status_due", table_name="advice_memory")
    op.drop_table("advice_memory")
