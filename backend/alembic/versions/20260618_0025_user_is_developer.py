"""users.is_developer — gate developer-only tools (reset/demo)

Revision ID: 0025
Revises: 0024
Create Date: 2026-06-18
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0025"
down_revision: str | None = "0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column(
        "is_developer", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.execute("UPDATE users SET is_developer = true WHERE lower(email) = 'advary2006@gmail.com'")


def downgrade() -> None:
    op.drop_column("users", "is_developer")
