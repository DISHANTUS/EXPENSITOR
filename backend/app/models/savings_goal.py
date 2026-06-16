"""Savings goals: a recurring monthly target OR a custom goal (target + date).

Goals are DERIVED feasibility trackers, not ledgers — no money moves and
current_balance is untouched. Progress / on-track / projected-completion are
computed on read. The system never mutates a target: ``recovery_mode`` +
``carried_deficit`` record the user's explicit, reversible recovery choice.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import RecoveryMode, SavingsGoalKind, SavingsGoalStatus


class SavingsGoal(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "savings_goals"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[SavingsGoalKind] = mapped_column(
        SAEnum(SavingsGoalKind, name="savings_goal_kind", native_enum=False, create_constraint=False, length=20),
        nullable=False,
    )

    # --- Target amount FX snapshot (per-month for monthly_target; total for custom_goal) ---
    original_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    original_currency: Mapped[str] = mapped_column(String(3), ForeignKey("currencies.code"), nullable=False)
    exchange_rate: Mapped[Decimal] = mapped_column(Numeric(20, 10), nullable=False)
    converted_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    base_currency: Mapped[str] = mapped_column(String(3), ForeignKey("currencies.code"), nullable=False)

    # custom_goal -> target_date required; monthly_target -> NULL.
    target_date: Mapped[date | None] = mapped_column(Date)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)

    status: Mapped[SavingsGoalStatus] = mapped_column(
        SAEnum(SavingsGoalStatus, name="savings_goal_status", native_enum=False, create_constraint=False, length=20),
        default=SavingsGoalStatus.active,
        server_default=text("'active'"),
        nullable=False,
    )

    # Recovery: set ONLY by an explicit user choice (never automatically).
    recovery_mode: Mapped[RecoveryMode | None] = mapped_column(
        SAEnum(RecoveryMode, name="recovery_mode", native_enum=False, create_constraint=False, length=20)
    )
    carried_deficit: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), default=Decimal("0"), server_default=text("0"), nullable=False
    )
    distribute_months: Mapped[int | None] = mapped_column(Integer)

    notes: Mapped[str | None] = mapped_column(Text)

    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_savings_goals_user_id_status", "user_id", "status"),
    )
