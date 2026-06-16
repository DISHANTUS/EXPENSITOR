"""savings_goals (Tier 1: Savings Targets + Recovery)

Revision ID: 0009
Revises: 0008
Create Date: 2026-06-16
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "savings_goals",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("original_amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("original_currency", sa.String(length=3), nullable=False),
        sa.Column("exchange_rate", sa.Numeric(20, 10), nullable=False),
        sa.Column("converted_amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("base_currency", sa.String(length=3), nullable=False),
        sa.Column("target_date", sa.Date(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default=sa.text("'active'"), nullable=False),
        sa.Column("recovery_mode", sa.String(length=20), nullable=True),
        sa.Column("carried_deficit", sa.Numeric(18, 4), server_default=sa.text("0"), nullable=False),
        sa.Column("distribute_months", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_savings_goals_user_id_users", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["original_currency"], ["currencies.code"], name="fk_savings_goals_original_currency_currencies"),
        sa.ForeignKeyConstraint(["base_currency"], ["currencies.code"], name="fk_savings_goals_base_currency_currencies"),
        sa.PrimaryKeyConstraint("id", name="pk_savings_goals"),
    )
    op.create_index("ix_savings_goals_user_id_status", "savings_goals", ["user_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_savings_goals_user_id_status", table_name="savings_goals")
    op.drop_table("savings_goals")
