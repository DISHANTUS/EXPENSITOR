"""user_settings.currency_history (V2 Sprint 4a-3: preferred-currency audit)

Revision ID: 0017
Revises: 0016
Create Date: 2026-06-17
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("user_settings", sa.Column("currency_history", JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("user_settings", "currency_history")
