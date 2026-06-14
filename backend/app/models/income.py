"""Actual received income (historical truth)."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Index, Numeric, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import IncomeSourceType

if TYPE_CHECKING:
    from app.models.user import User


class Income(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "incomes"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
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

    # --- Multi-currency snapshot (all math uses converted_amount in base_currency) ---
    original_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    original_currency: Mapped[str] = mapped_column(
        String(3), ForeignKey("currencies.code"), nullable=False
    )
    exchange_rate: Mapped[Decimal] = mapped_column(Numeric(20, 10), nullable=False)
    converted_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    base_currency: Mapped[str] = mapped_column(
        String(3), ForeignKey("currencies.code"), nullable=False
    )

    description: Mapped[str | None] = mapped_column(String(500))
    received_date: Mapped[date] = mapped_column(Date, nullable=False)

    user: Mapped[User] = relationship(back_populates="incomes")

    __table_args__ = (Index("ix_incomes_user_id_received_date", "user_id", "received_date"),)
