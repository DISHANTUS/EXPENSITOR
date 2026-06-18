"""financial_profiles.transport_note — free-text when transport_mode == other

Revision ID: 0031
Revises: 0030
Create Date: 2026-06-18
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0031"
down_revision: str | None = "0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("financial_profiles", sa.Column("transport_note", sa.String(120), nullable=True))


def downgrade() -> None:
    op.drop_column("financial_profiles", "transport_note")
