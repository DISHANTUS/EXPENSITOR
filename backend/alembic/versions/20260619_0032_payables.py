"""payables (borrowed money the user owes — AI intervention foundation)

Revision ID: 0032
Revises: 0031
Create Date: 2026-06-19
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0032"
down_revision: str | None = "0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "payables",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_name", sa.String(length=200), nullable=False),
        sa.Column("person_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("original_amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("original_currency", sa.String(length=3), nullable=False),
        sa.Column("exchange_rate", sa.Numeric(20, 10), nullable=False),
        sa.Column("converted_amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("base_currency", sa.String(length=3), nullable=False),
        sa.Column("return_expectation", sa.String(length=20), server_default=sa.text("'required'"), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), server_default=sa.text("'open'"), nullable=False),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("importance", sa.String(length=20), server_default=sa.text("'medium'"), nullable=False),
        sa.Column("ai_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_payables_user_id_users", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["person_id"], ["persons.id"], name="fk_payables_person_id_persons", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["original_currency"], ["currencies.code"], name="fk_payables_original_currency_currencies"),
        sa.ForeignKeyConstraint(["base_currency"], ["currencies.code"], name="fk_payables_base_currency_currencies"),
        sa.PrimaryKeyConstraint("id", name="pk_payables"),
    )
    op.create_index("ix_payables_user_id_status", "payables", ["user_id", "status"])
    op.create_index("ix_payables_user_id_due_date", "payables", ["user_id", "due_date"])


def downgrade() -> None:
    op.drop_index("ix_payables_user_id_due_date", table_name="payables")
    op.drop_index("ix_payables_user_id_status", table_name="payables")
    op.drop_table("payables")
