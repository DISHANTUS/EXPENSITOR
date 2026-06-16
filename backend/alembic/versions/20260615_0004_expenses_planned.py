"""expenses.expense_date + planned_expenses title/notes/deleted_at/is_recurring

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-15

Week 3 Phase C: reconcile schema for Expenses + Planned Expenses CRUD.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- expenses: spent_at (timestamptz) -> expense_date (DATE) ---
    op.alter_column(
        "expenses", "spent_at", type_=sa.Date(), postgresql_using="spent_at::date"
    )
    op.alter_column("expenses", "spent_at", new_column_name="expense_date")
    op.execute(
        "ALTER INDEX ix_expenses_user_id_spent_at RENAME TO ix_expenses_user_id_expense_date"
    )

    # --- planned_expenses ---
    # Rename reason -> title (data preserved); backfill NULLs only; enforce NOT NULL.
    op.alter_column("planned_expenses", "reason", new_column_name="title")
    op.execute("UPDATE planned_expenses SET title = 'Untitled' WHERE title IS NULL")
    op.alter_column(
        "planned_expenses", "title", existing_type=sa.String(length=500), nullable=False
    )
    op.add_column("planned_expenses", sa.Column("notes", sa.Text(), nullable=True))
    op.add_column(
        "planned_expenses", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "planned_expenses",
        sa.Column(
            "is_recurring", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
    )
    # New priority default (essential/important/optional -> low/medium/high/critical).
    op.alter_column("planned_expenses", "priority", server_default=sa.text("'medium'"))


def downgrade() -> None:
    op.alter_column("planned_expenses", "priority", server_default=sa.text("'important'"))
    op.drop_column("planned_expenses", "is_recurring")
    op.drop_column("planned_expenses", "deleted_at")
    op.drop_column("planned_expenses", "notes")
    op.alter_column("planned_expenses", "title", nullable=True)
    op.alter_column("planned_expenses", "title", new_column_name="reason")

    op.execute(
        "ALTER INDEX ix_expenses_user_id_expense_date RENAME TO ix_expenses_user_id_spent_at"
    )
    op.alter_column("expenses", "expense_date", new_column_name="spent_at")
    op.alter_column(
        "expenses",
        "spent_at",
        type_=sa.DateTime(timezone=True),
        postgresql_using="spent_at::timestamptz",
    )
