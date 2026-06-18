"""user_settings.display_name — what the user wants to be called

Revision ID: 0029
Revises: 0028
Create Date: 2026-06-18
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0029"
down_revision: str | None = "0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("user_settings", sa.Column("display_name", sa.String(60), nullable=True))


def downgrade() -> None:
    op.drop_column("user_settings", "display_name")
