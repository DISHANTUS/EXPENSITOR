"""expected_time on receivables + income_sources (NL layer: exact arrival times)

Revision ID: 0013
Revises: 0012
Create Date: 2026-06-16
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("receivables", sa.Column("expected_time", sa.Time(), nullable=True))
    op.add_column("income_sources", sa.Column("expected_time", sa.Time(), nullable=True))


def downgrade() -> None:
    op.drop_column("income_sources", "expected_time")
    op.drop_column("receivables", "expected_time")
