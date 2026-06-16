"""budget_sessions + session_expenses (C3: Daily Budget Sessions)

Revision ID: 0007
Revises: 0006
Create Date: 2026-06-15
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "budget_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("original_amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("original_currency", sa.String(length=3), nullable=False),
        sa.Column("exchange_rate", sa.Numeric(20, 10), nullable=False),
        sa.Column("converted_amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("base_currency", sa.String(length=3), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=20), server_default=sa.text("'active'"), nullable=False),
        sa.Column("alerted_thresholds", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_budget_sessions_user_id_users", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["original_currency"], ["currencies.code"], name="fk_budget_sessions_original_currency_currencies"),
        sa.ForeignKeyConstraint(["base_currency"], ["currencies.code"], name="fk_budget_sessions_base_currency_currencies"),
        sa.PrimaryKeyConstraint("id", name="pk_budget_sessions"),
    )
    op.create_index("ix_budget_sessions_user_id_status", "budget_sessions", ["user_id", "status"])

    op.create_table(
        "session_expenses",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("expense_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["budget_sessions.id"], name="fk_session_expenses_session_id_budget_sessions", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["expense_id"], ["expenses.id"], name="fk_session_expenses_expense_id_expenses", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_session_expenses"),
        sa.UniqueConstraint("expense_id", name="uq_session_expenses_expense_id"),
    )
    op.create_index("ix_session_expenses_session_id", "session_expenses", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_session_expenses_session_id", table_name="session_expenses")
    op.drop_table("session_expenses")
    op.drop_index("ix_budget_sessions_user_id_status", table_name="budget_sessions")
    op.drop_table("budget_sessions")
