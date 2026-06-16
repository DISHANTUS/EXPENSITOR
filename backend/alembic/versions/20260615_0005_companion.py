"""companion_events + companion_insights (C1: AI Companion layer)

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-15
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "companion_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=30), nullable=False),
        sa.Column("surface", sa.String(length=100), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=True),
        sa.Column("entity_type", sa.String(length=30), nullable=True),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_companion_events_user_id_users", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_companion_events"),
    )
    op.create_index("ix_companion_events_user_id_occurred_at", "companion_events", ["user_id", "occurred_at"])
    op.create_index("ix_companion_events_user_id_event_type", "companion_events", ["user_id", "event_type"])

    op.create_table(
        "companion_insights",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category", sa.String(length=30), nullable=False),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("surface", sa.String(length=100), nullable=True),
        sa.Column("severity", sa.String(length=20), server_default=sa.text("'info'"), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("facts", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("source", sa.String(length=20), server_default=sa.text("'engine'"), nullable=False),
        sa.Column("related_entity_type", sa.String(length=30), nullable=True),
        sa.Column("related_entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_read", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_companion_insights_user_id_users", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_companion_insights"),
    )
    op.create_index("ix_companion_insights_user_id_created_at", "companion_insights", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_companion_insights_user_id_created_at", table_name="companion_insights")
    op.drop_table("companion_insights")
    op.drop_index("ix_companion_events_user_id_event_type", table_name="companion_events")
    op.drop_index("ix_companion_events_user_id_occurred_at", table_name="companion_events")
    op.drop_table("companion_events")
