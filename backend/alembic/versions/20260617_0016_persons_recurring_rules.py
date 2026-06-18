"""persons + recurring_rules + relationship/importance/ai_metadata columns

V2 Sprint 4a-1 foundation:
- persons (relationship memory) + recurring_rules (subscriptions/EMI/bills/...)
- receivables.person_id / importance / ai_metadata
- income_sources.reason / ai_metadata
- savings_goals.reason / importance / ai_metadata
- planned_expenses.importance / ai_metadata

Revision ID: 0016
Revises: 0015
Create Date: 2026-06-17
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- persons ---
    op.create_table(
        "persons",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE", name=op.f("fk_persons_user_id_users")),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("nickname", sa.String(100), nullable=True),
        sa.Column("relationship_type", sa.String(20), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("reliability_score", sa.Numeric(4, 3), nullable=True),
        sa.Column("first_interaction_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_interaction_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tags", JSONB(), nullable=True),
        sa.Column("ai_metadata", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_persons")),
        sa.CheckConstraint(
            "reliability_score IS NULL OR (reliability_score >= 0 AND reliability_score <= 1)",
            name="ck_persons_reliability_score_range",
        ),
    )
    op.create_index("ix_persons_user_id_name", "persons", ["user_id", "name"])

    # --- recurring_rules ---
    op.create_table(
        "recurring_rules",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE", name=op.f("fk_recurring_rules_user_id_users")),
            nullable=False,
        ),
        sa.Column("rule_type", sa.String(20), nullable=False),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("original_amount", sa.Numeric(18, 4), nullable=False),
        sa.Column(
            "original_currency",
            sa.String(3),
            sa.ForeignKey("currencies.code", name=op.f("fk_recurring_rules_original_currency_currencies")),
            nullable=False,
        ),
        sa.Column("exchange_rate", sa.Numeric(20, 10), nullable=False),
        sa.Column("converted_amount", sa.Numeric(18, 4), nullable=False),
        sa.Column(
            "base_currency",
            sa.String(3),
            sa.ForeignKey("currencies.code", name=op.f("fk_recurring_rules_base_currency_currencies")),
            nullable=False,
        ),
        sa.Column("recurrence_day", sa.Integer(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column(
            "category_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("categories.id", ondelete="SET NULL", name=op.f("fk_recurring_rules_category_id_categories")),
            nullable=True,
        ),
        sa.Column(
            "person_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("persons.id", ondelete="SET NULL", name=op.f("fk_recurring_rules_person_id_persons")),
            nullable=True,
        ),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("importance", sa.String(20), server_default=sa.text("'medium'"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("ai_metadata", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_recurring_rules")),
        sa.CheckConstraint(
            "recurrence_day >= 1 AND recurrence_day <= 31",
            name="ck_recurring_rules_recurrence_day_range",
        ),
    )
    op.create_index("ix_recurring_rules_user_id_is_active", "recurring_rules", ["user_id", "is_active"])

    # --- receivables: relationship + importance + metadata ---
    op.add_column("receivables", sa.Column("person_id", PGUUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        op.f("fk_receivables_person_id_persons"), "receivables", "persons", ["person_id"], ["id"], ondelete="SET NULL"
    )
    op.add_column("receivables", sa.Column("importance", sa.String(20), server_default=sa.text("'medium'"), nullable=False))
    op.add_column("receivables", sa.Column("ai_metadata", JSONB(), nullable=True))

    # --- income_sources: reason + metadata ---
    op.add_column("income_sources", sa.Column("reason", sa.Text(), nullable=True))
    op.add_column("income_sources", sa.Column("ai_metadata", JSONB(), nullable=True))

    # --- savings_goals: reason + importance + metadata ---
    op.add_column("savings_goals", sa.Column("reason", sa.Text(), nullable=True))
    op.add_column("savings_goals", sa.Column("importance", sa.String(20), server_default=sa.text("'high'"), nullable=False))
    op.add_column("savings_goals", sa.Column("ai_metadata", JSONB(), nullable=True))

    # --- planned_expenses: importance + metadata ---
    op.add_column("planned_expenses", sa.Column("importance", sa.String(20), server_default=sa.text("'medium'"), nullable=False))
    op.add_column("planned_expenses", sa.Column("ai_metadata", JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("planned_expenses", "ai_metadata")
    op.drop_column("planned_expenses", "importance")

    op.drop_column("savings_goals", "ai_metadata")
    op.drop_column("savings_goals", "importance")
    op.drop_column("savings_goals", "reason")

    op.drop_column("income_sources", "ai_metadata")
    op.drop_column("income_sources", "reason")

    op.drop_constraint(op.f("fk_receivables_person_id_persons"), "receivables", type_="foreignkey")
    op.drop_column("receivables", "ai_metadata")
    op.drop_column("receivables", "importance")
    op.drop_column("receivables", "person_id")

    op.drop_index("ix_recurring_rules_user_id_is_active", table_name="recurring_rules")
    op.drop_table("recurring_rules")

    op.drop_index("ix_persons_user_id_name", table_name="persons")
    op.drop_table("persons")
