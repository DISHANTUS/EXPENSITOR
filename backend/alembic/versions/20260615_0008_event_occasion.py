"""planned_expenses.occasion_type (C4: Event Planner)

Revision ID: 0008
Revises: 0007
Create Date: 2026-06-15
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("planned_expenses", sa.Column("occasion_type", sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column("planned_expenses", "occasion_type")
