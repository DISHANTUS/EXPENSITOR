"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-06-14

Creates the 10 MVP tables, their constraints/indexes, and the pg_trgm extension
(used by upcoming full-text-ish expense search).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> tuple[sa.Column, sa.Column]:
    return (
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # --- currencies (referenced by FK from money tables) ---
    op.create_table(
        "currencies",
        sa.Column("code", sa.String(length=3), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("symbol", sa.String(length=8), nullable=False),
        sa.Column("decimal_digits", sa.Integer(), server_default=sa.text("2"), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("code", name=op.f("pk_currencies")),
    )

    # --- users (tenant root) ---
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )

    # --- user_settings (1-1 with users) ---
    op.create_table(
        "user_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "base_currency", sa.String(length=3), server_default=sa.text("'INR'"), nullable=False
        ),
        sa.Column("locale", sa.String(length=10), nullable=True),
        sa.Column(
            "timezone", sa.String(length=64), server_default=sa.text("'UTC'"), nullable=False
        ),
        sa.Column("monthly_threshold", sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column("monthly_income_estimate", sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column(
            "starting_savings",
            sa.Numeric(precision=18, scale=4),
            server_default=sa.text("0"),
            nullable=False,
        ),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_settings_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["base_currency"],
            ["currencies.code"],
            name=op.f("fk_user_settings_base_currency_currencies"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_settings")),
        sa.UniqueConstraint("user_id", name=op.f("uq_user_settings_user_id")),
    )

    # --- refresh_tokens ---
    op.create_table(
        "refresh_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_refresh_tokens_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_refresh_tokens")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_refresh_tokens_token_hash")),
    )
    op.create_index(op.f("ix_refresh_tokens_user_id"), "refresh_tokens", ["user_id"])

    # --- categories ---
    op.create_table(
        "categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("icon", sa.String(length=50), nullable=True),
        sa.Column("color", sa.String(length=9), nullable=True),
        sa.Column("is_system", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_essential", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_categories_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_categories")),
        sa.UniqueConstraint("user_id", "name", name="uq_categories_user_id_name"),
    )
    op.create_index(op.f("ix_categories_user_id"), "categories", ["user_id"])

    # --- exchange_rates ---
    op.create_table(
        "exchange_rates",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("base_currency", sa.String(length=3), nullable=False),
        sa.Column("quote_currency", sa.String(length=3), nullable=False),
        sa.Column("rate", sa.Numeric(precision=20, scale=10), nullable=False),
        sa.Column("rate_date", sa.Date(), nullable=False),
        sa.Column(
            "source", sa.String(length=50), server_default=sa.text("'frankfurter'"), nullable=False
        ),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["base_currency"],
            ["currencies.code"],
            name=op.f("fk_exchange_rates_base_currency_currencies"),
        ),
        sa.ForeignKeyConstraint(
            ["quote_currency"],
            ["currencies.code"],
            name=op.f("fk_exchange_rates_quote_currency_currencies"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_exchange_rates")),
        sa.UniqueConstraint(
            "base_currency", "quote_currency", "rate_date", name="uq_exchange_rates_pair_date"
        ),
    )

    # --- incomes (actual receipts) ---
    op.create_table(
        "incomes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_type", sa.String(length=20), nullable=False),
        sa.Column("original_amount", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("original_currency", sa.String(length=3), nullable=False),
        sa.Column("exchange_rate", sa.Numeric(precision=20, scale=10), nullable=False),
        sa.Column("converted_amount", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("base_currency", sa.String(length=3), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("received_date", sa.Date(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_incomes_user_id_users"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["original_currency"],
            ["currencies.code"],
            name=op.f("fk_incomes_original_currency_currencies"),
        ),
        sa.ForeignKeyConstraint(
            ["base_currency"],
            ["currencies.code"],
            name=op.f("fk_incomes_base_currency_currencies"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_incomes")),
    )
    op.create_index(
        "ix_incomes_user_id_received_date", "incomes", ["user_id", "received_date"]
    )

    # --- income_sources (expected income feeding the projection) ---
    op.create_table(
        "income_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("source_type", sa.String(length=20), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("original_amount", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("original_currency", sa.String(length=3), nullable=False),
        sa.Column("exchange_rate", sa.Numeric(precision=20, scale=10), nullable=False),
        sa.Column("converted_amount", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("base_currency", sa.String(length=3), nullable=False),
        sa.Column("recurrence_day", sa.Integer(), nullable=True),
        sa.Column("expected_date", sa.Date(), nullable=True),
        sa.Column(
            "reliability",
            sa.Numeric(precision=4, scale=3),
            server_default=sa.text("0.5"),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_income_sources_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["original_currency"],
            ["currencies.code"],
            name=op.f("fk_income_sources_original_currency_currencies"),
        ),
        sa.ForeignKeyConstraint(
            ["base_currency"],
            ["currencies.code"],
            name=op.f("fk_income_sources_base_currency_currencies"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_income_sources")),
        sa.CheckConstraint(
            "reliability >= 0 AND reliability <= 1",
            name="ck_income_sources_reliability_range",
        ),
        sa.CheckConstraint(
            "recurrence_day IS NULL OR (recurrence_day >= 1 AND recurrence_day <= 31)",
            name="ck_income_sources_recurrence_day_range",
        ),
    )
    op.create_index(
        "ix_income_sources_user_id_is_active", "income_sources", ["user_id", "is_active"]
    )

    # --- expenses ---
    op.create_table(
        "expenses",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("original_amount", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("original_currency", sa.String(length=3), nullable=False),
        sa.Column("exchange_rate", sa.Numeric(precision=20, scale=10), nullable=False),
        sa.Column("converted_amount", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("base_currency", sa.String(length=3), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("merchant_name", sa.String(length=255), nullable=True),
        sa.Column("payment_method", sa.String(length=50), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("spent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("category_source", sa.String(length=20), nullable=True),
        sa.Column("category_confidence", sa.Numeric(precision=4, scale=3), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_expenses_user_id_users"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            name=op.f("fk_expenses_category_id_categories"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["original_currency"],
            ["currencies.code"],
            name=op.f("fk_expenses_original_currency_currencies"),
        ),
        sa.ForeignKeyConstraint(
            ["base_currency"],
            ["currencies.code"],
            name=op.f("fk_expenses_base_currency_currencies"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_expenses")),
        sa.CheckConstraint(
            "category_confidence IS NULL OR "
            "(category_confidence >= 0 AND category_confidence <= 1)",
            name="ck_expenses_category_confidence_range",
        ),
    )
    op.create_index("ix_expenses_user_id_spent_at", "expenses", ["user_id", "spent_at"])
    op.create_index("ix_expenses_user_id_category_id", "expenses", ["user_id", "category_id"])

    # --- planned_expenses ---
    op.create_table(
        "planned_expenses",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("original_amount", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("original_currency", sa.String(length=3), nullable=False),
        sa.Column("exchange_rate", sa.Numeric(precision=20, scale=10), nullable=False),
        sa.Column("converted_amount", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("base_currency", sa.String(length=3), nullable=False),
        sa.Column("planned_date", sa.Date(), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column(
            "priority", sa.String(length=20), server_default=sa.text("'important'"), nullable=False
        ),
        sa.Column(
            "status", sa.String(length=20), server_default=sa.text("'planned'"), nullable=False
        ),
        sa.Column("last_feasibility", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("converted_expense_id", postgresql.UUID(as_uuid=True), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_planned_expenses_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            name=op.f("fk_planned_expenses_category_id_categories"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["original_currency"],
            ["currencies.code"],
            name=op.f("fk_planned_expenses_original_currency_currencies"),
        ),
        sa.ForeignKeyConstraint(
            ["base_currency"],
            ["currencies.code"],
            name=op.f("fk_planned_expenses_base_currency_currencies"),
        ),
        sa.ForeignKeyConstraint(
            ["converted_expense_id"],
            ["expenses.id"],
            name=op.f("fk_planned_expenses_converted_expense_id_expenses"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_planned_expenses")),
    )
    op.create_index(
        "ix_planned_expenses_user_id_planned_date", "planned_expenses", ["user_id", "planned_date"]
    )
    op.create_index(
        "ix_planned_expenses_user_id_status", "planned_expenses", ["user_id", "status"]
    )


def downgrade() -> None:
    op.drop_table("planned_expenses")
    op.drop_table("expenses")
    op.drop_table("income_sources")
    op.drop_table("incomes")
    op.drop_table("exchange_rates")
    op.drop_table("categories")
    op.drop_table("refresh_tokens")
    op.drop_table("user_settings")
    op.drop_table("users")
    op.drop_table("currencies")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
