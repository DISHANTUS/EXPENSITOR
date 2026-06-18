"""financial_profiles table (Budget Intelligence System — profile-first)

Revision ID: 0027
Revises: 0026
Create Date: 2026-06-18
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PGUUID

revision: str = "0027"
down_revision: str | None = "0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "financial_profiles",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE", name=op.f("fk_financial_profiles_user_id_users")),
            nullable=False,
        ),
        sa.Column("life_stage", sa.String(32), nullable=True),
        sa.Column("life_stage_note", sa.String(200), nullable=True),
        sa.Column("current_country", sa.String(2), nullable=True),
        sa.Column("current_city", sa.String(80), nullable=True),
        sa.Column("moving_country", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("future_country", sa.String(2), nullable=True),
        sa.Column("future_move_year", sa.Integer(), nullable=True),
        sa.Column("living_situation", sa.String(32), nullable=True),
        sa.Column("living_note", sa.String(200), nullable=True),
        sa.Column("food_situation", sa.String(32), nullable=True),
        sa.Column("food_monthly", sa.Numeric(18, 4), nullable=True),
        sa.Column("food_daily", sa.Numeric(18, 4), nullable=True),
        sa.Column("transport_mode", sa.String(32), nullable=True),
        sa.Column("transport_monthly", sa.Numeric(18, 4), nullable=True),
        sa.Column("tuition_responsibility", sa.String(32), nullable=True),
        sa.Column("rent_monthly", sa.Numeric(18, 4), nullable=True),
        sa.Column("lifestyle_monthly", sa.Numeric(18, 4), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_financial_profiles")),
        sa.UniqueConstraint("user_id", name="uq_financial_profiles_user_id"),
    )


def downgrade() -> None:
    op.drop_table("financial_profiles")
