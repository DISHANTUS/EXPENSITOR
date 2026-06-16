"""daily_plans table (V2 Sprint 3: per-day budget + overspend reason)

Revision ID: 0015
Revises: 0014
Create Date: 2026-06-17
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PGUUID

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "daily_plans",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE", name=op.f("fk_daily_plans_user_id_users")),
            nullable=False,
        ),
        sa.Column("plan_date", sa.Date(), nullable=False),
        sa.Column("planned_budget", sa.Numeric(18, 4), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "modified_after_start",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("overspend_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_daily_plans")),
        sa.UniqueConstraint("user_id", "plan_date", name="uq_daily_plans_user_id_plan_date"),
    )
    op.create_index("ix_daily_plans_user_id_plan_date", "daily_plans", ["user_id", "plan_date"])


def downgrade() -> None:
    op.drop_index("ix_daily_plans_user_id_plan_date", table_name="daily_plans")
    op.drop_table("daily_plans")
