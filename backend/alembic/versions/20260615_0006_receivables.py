"""receivables (C2: Receivables System)

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-15
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "receivables",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("source_name", sa.String(length=200), nullable=False),
        sa.Column("source_type", sa.String(length=20), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("original_amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("original_currency", sa.String(length=3), nullable=False),
        sa.Column("exchange_rate", sa.Numeric(20, 10), nullable=False),
        sa.Column("converted_amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("base_currency", sa.String(length=3), nullable=False),
        sa.Column("expected_date", sa.Date(), nullable=True),
        sa.Column("recurrence_day", sa.Integer(), nullable=True),
        sa.Column("reliability", sa.Numeric(4, 3), server_default=sa.text("0.5"), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_follow_up_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("follow_up_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_receivables_user_id_users", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["original_currency"], ["currencies.code"], name="fk_receivables_original_currency_currencies"),
        sa.ForeignKeyConstraint(["base_currency"], ["currencies.code"], name="fk_receivables_base_currency_currencies"),
        sa.CheckConstraint("reliability >= 0 AND reliability <= 1", name="ck_receivables_reliability_range"),
        sa.CheckConstraint(
            "recurrence_day IS NULL OR (recurrence_day >= 1 AND recurrence_day <= 31)",
            name="ck_receivables_recurrence_day_range",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_receivables"),
    )
    op.create_index("ix_receivables_user_id_status", "receivables", ["user_id", "status"])
    op.create_index("ix_receivables_user_id_expected_date", "receivables", ["user_id", "expected_date"])


def downgrade() -> None:
    op.drop_index("ix_receivables_user_id_expected_date", table_name="receivables")
    op.drop_index("ix_receivables_user_id_status", table_name="receivables")
    op.drop_table("receivables")
