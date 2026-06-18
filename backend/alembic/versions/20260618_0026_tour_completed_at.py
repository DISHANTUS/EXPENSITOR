"""user_settings.tour_completed_at — first-launch guided tour state

Revision ID: 0026
Revises: 0025
Create Date: 2026-06-18
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0026"
down_revision: str | None = "0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # NULL for every existing row → all current users see the tour once on next login.
    op.add_column(
        "user_settings",
        sa.Column("tour_completed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user_settings", "tour_completed_at")
