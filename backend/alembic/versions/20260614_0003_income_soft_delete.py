"""add deleted_at to income_sources and incomes (soft delete)

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-14

Week 2 Phase B: soft-delete support for income sources and actual income.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "income_sources",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "incomes",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("incomes", "deleted_at")
    op.drop_column("income_sources", "deleted_at")
