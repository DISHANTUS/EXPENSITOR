"""Expected income (recurring or one-time) that feeds the Projection Engine.

Distinct from ``incomes`` (actual receipts). Each source carries a reliability
weight used by the conservative (worst/expected/best) projection.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import IncomeKind, IncomeSourceType

if TYPE_CHECKING:
    from app.models.user import User


class IncomeSource(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "income_sources"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[IncomeSourceType] = mapped_column(
        SAEnum(
            IncomeSourceType,
            name="income_source_type",
            native_enum=False,
            create_constraint=False,
            length=20,
        ),
        nullable=False,
    )
    kind: Mapped[IncomeKind] = mapped_column(
        SAEnum(
            IncomeKind,
            name="income_kind",
            native_enum=False,
            create_constraint=False,
            length=20,
        ),
        nullable=False,
    )

    # --- Multi-currency snapshot ---
    original_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    original_currency: Mapped[str] = mapped_column(
        String(3), ForeignKey("currencies.code"), nullable=False
    )
    exchange_rate: Mapped[Decimal] = mapped_column(Numeric(20, 10), nullable=False)
    converted_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    base_currency: Mapped[str] = mapped_column(
        String(3), ForeignKey("currencies.code"), nullable=False
    )

    # Recurring -> day of month (1-31). One-time -> expected_date.
    recurrence_day: Mapped[int | None] = mapped_column(Integer)
    expected_date: Mapped[date | None] = mapped_column(Date)

    # 0..1 probability the income arrives (user-set in MVP).
    reliability: Mapped[Decimal] = mapped_column(
        Numeric(4, 3), default=Decimal("0.5"), server_default=text("0.5"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true"), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="income_sources")

    __table_args__ = (
        CheckConstraint(
            "reliability >= 0 AND reliability <= 1",
            name="ck_income_sources_reliability_range",
        ),
        CheckConstraint(
            "recurrence_day IS NULL OR (recurrence_day >= 1 AND recurrence_day <= 31)",
            name="ck_income_sources_recurrence_day_range",
        ),
        Index("ix_income_sources_user_id_is_active", "user_id", "is_active"),
    )
