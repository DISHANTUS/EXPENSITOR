"""user_settings.companion_name (Sprint 6c: the companion's name)

Revision ID: 0022
Revises: 0021
Create Date: 2026-06-17
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("user_settings", sa.Column("companion_name", sa.String(length=40), nullable=True))


def downgrade() -> None:
    op.drop_column("user_settings", "companion_name")
