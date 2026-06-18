"""Migrate the legacy placeholder companion name 'Aoi' -> 'Advary' (Sprint UI-X)

Advary is the canonical default companion identity. Any user still on the old
placeholder 'Aoi' is migrated; users with their own custom name are untouched.

Revision ID: 0024
Revises: 0023
Create Date: 2026-06-17
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0024"
down_revision: str | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("UPDATE user_settings SET companion_name = 'Advary' WHERE companion_name = 'Aoi'")


def downgrade() -> None:
    # One-way data repair; nothing to undo (we can't tell which were originally 'Aoi').
    pass
