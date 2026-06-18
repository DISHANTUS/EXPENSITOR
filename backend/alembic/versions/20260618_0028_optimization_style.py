"""financial_profiles.optimization_style (Budget Intelligence System)

Revision ID: 0028
Revises: 0027
Create Date: 2026-06-18
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0028"
down_revision: str | None = "0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "financial_profiles",
        sa.Column("optimization_style", sa.String(32), nullable=False, server_default=sa.text("'balanced'")),
    )


def downgrade() -> None:
    op.drop_column("financial_profiles", "optimization_style")
