"""Recurring financial commitments (V2): subscriptions, EMIs, loans, bills,
insurance, borrowed-money repayments. Materialized onto the calendar by
``calendar_service``. Salary/expected income stays in ``income_sources``;
lent money / one-off receivables stay in ``receivables``.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import ImportanceLevel, RecurringRuleType


class RecurringRule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "recurring_rules"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    rule_type: Mapped[RecurringRuleType] = mapped_column(
        SAEnum(RecurringRuleType, name="recurring_rule_type", native_enum=False, create_constraint=False, length=20),
        nullable=False,
    )
    label: Mapped[str] = mapped_column(String(255), nullable=False)

    # --- Multi-currency snapshot ---
    original_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    original_currency: Mapped[str] = mapped_column(String(3), ForeignKey("currencies.code"), nullable=False)
    exchange_rate: Mapped[Decimal] = mapped_column(Numeric(20, 10), nullable=False)
    converted_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    base_currency: Mapped[str] = mapped_column(String(3), ForeignKey("currencies.code"), nullable=False)

    # Monthly cadence in MVP: charged on this day each month (1-31).
    recurrence_day: Mapped[int] = mapped_column(Integer, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)

    category_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("categories.id", ondelete="SET NULL")
    )
    # e.g. who the user borrowed from.
    person_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("persons.id", ondelete="SET NULL")
    )

    reason: Mapped[str | None] = mapped_column(Text)
    importance: Mapped[ImportanceLevel] = mapped_column(
        SAEnum(ImportanceLevel, name="importance_level", native_enum=False, create_constraint=False, length=20),
        default=ImportanceLevel.medium,
        server_default=text("'medium'"),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"), nullable=False)
    ai_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("recurrence_day >= 1 AND recurrence_day <= 31", name="ck_recurring_rules_recurrence_day_range"),
        Index("ix_recurring_rules_user_id_is_active", "user_id", "is_active"),
    )
