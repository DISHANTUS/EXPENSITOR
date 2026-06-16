"""rename starting_savings, add notification_preferences + preferred_ai_tone

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-14

Week 2 Phase A: settings changes supporting Authentication + User Settings.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NOTIFICATION_PREFS_DEFAULT = (
    "'{\"threshold_alerts\": true, \"weekly_summary\": true, "
    "\"planned_expense_reminders\": true, \"monthly_report\": true}'::jsonb"
)


def upgrade() -> None:
    # 1. Rename starting_savings -> starting_balance (preserves data).
    op.alter_column("user_settings", "starting_savings", new_column_name="starting_balance")

    # 2. preferred_ai_tone (enum-as-VARCHAR, default 'balanced').
    op.add_column(
        "user_settings",
        sa.Column(
            "preferred_ai_tone",
            sa.String(length=20),
            server_default=sa.text("'balanced'"),
            nullable=False,
        ),
    )

    # 3. notification_preferences (JSONB, default = all enabled).
    op.add_column(
        "user_settings",
        sa.Column(
            "notification_preferences",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text(_NOTIFICATION_PREFS_DEFAULT),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("user_settings", "notification_preferences")
    op.drop_column("user_settings", "preferred_ai_tone")
    op.alter_column("user_settings", "starting_balance", new_column_name="starting_savings")
