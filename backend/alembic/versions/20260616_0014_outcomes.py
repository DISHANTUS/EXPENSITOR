"""outcomes table (Phase E: outcome tracking & adaptive planning)

Revision ID: 0014
Revises: 0013
Create Date: 2026-06-16
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PGUUID

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "outcomes",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", PGUUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("subject_type", sa.String(length=40), nullable=False),
        sa.Column("subject_id", PGUUID(as_uuid=True), nullable=True),
        sa.Column("lever_key", sa.String(length=80), nullable=True),
        sa.Column("category_id", PGUUID(as_uuid=True), nullable=True),
        sa.Column("expected_value", sa.Numeric(18, 4), nullable=True),
        sa.Column("actual_value", sa.Numeric(18, 4), nullable=True),
        sa.Column("variance", sa.Numeric(18, 4), nullable=True),
        sa.Column("metric", sa.String(length=60), nullable=True),
        sa.Column("outcome", sa.String(length=20), nullable=False),
        sa.Column("outcome_reason", sa.Text(), nullable=True),
        sa.Column("circumstance", sa.String(length=40), nullable=True),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("base_currency", sa.String(length=3), nullable=True),
        sa.Column("period_month", sa.Date(), nullable=True),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_outcomes_user_id_kind_lever_key", "outcomes", ["user_id", "kind", "lever_key"])
    op.create_index("ix_outcomes_user_id_kind_subject_id", "outcomes",
                    ["user_id", "kind", "subject_id", "period_month"])


def downgrade() -> None:
    op.drop_index("ix_outcomes_user_id_kind_subject_id", table_name="outcomes")
    op.drop_index("ix_outcomes_user_id_kind_lever_key", table_name="outcomes")
    op.drop_table("outcomes")
