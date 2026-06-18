"""user_settings.voice_length (Sprint 5: voice companion — spoken length)

Revision ID: 0021
Revises: 0020
Create Date: 2026-06-17
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("user_settings", sa.Column(
        "voice_length", sa.String(length=10), nullable=False, server_default="normal"))


def downgrade() -> None:
    op.drop_column("user_settings", "voice_length")
