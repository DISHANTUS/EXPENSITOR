"""income timing window on receivables + income_sources (Tier 1)

Revision ID: 0010
Revises: 0009
Create Date: 2026-06-16
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("receivables", sa.Column("expected_time_window", sa.String(length=20), nullable=True))
    op.add_column("income_sources", sa.Column("expected_time_window", sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column("income_sources", "expected_time_window")
    op.drop_column("receivables", "expected_time_window")
