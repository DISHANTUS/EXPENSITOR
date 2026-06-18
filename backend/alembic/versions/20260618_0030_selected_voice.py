"""user_settings.selected_voice + voice_locale — chosen device TTS voice (Voice Studio)

Revision ID: 0030
Revises: 0029
Create Date: 2026-06-18
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0030"
down_revision: str | None = "0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("user_settings", sa.Column("selected_voice", sa.String(120), nullable=True))
    op.add_column("user_settings", sa.Column("voice_locale", sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column("user_settings", "voice_locale")
    op.drop_column("user_settings", "selected_voice")
