"""Money the user OWES someone (borrowed).

Deliberately a separate table from ``Receivable`` (money owed TO the user): a debt
is an obligation, never expected income, so it must never feed the income
projection / feasibility engine. ``overdue`` is derived on read (open + past
``due_date``), never stored.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Date, DateTime, ForeignKey, Index, Numeric, String, Text, text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import ImportanceLevel, PayableStatus, ReturnExpectation


class Payable(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "payables"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # The person you owe (free text always; linked to a Person when known).
    source_name: Mapped[str] = mapped_column(String(200), nullable=False)
    person_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("persons.id", ondelete="SET NULL")
    )

    # --- Multi-currency snapshot (base-currency math) ---
    original_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    original_currency: Mapped[str] = mapped_column(String(3), ForeignKey("currencies.code"), nullable=False)
    exchange_rate: Mapped[Decimal] = mapped_column(Numeric(20, 10), nullable=False)
    converted_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    base_currency: Mapped[str] = mapped_column(String(3), ForeignKey("currencies.code"), nullable=False)

    return_expectation: Mapped[ReturnExpectation] = mapped_column(
        SAEnum(ReturnExpectation, name="return_expectation", native_enum=False, create_constraint=False, length=20),
        default=ReturnExpectation.required,
        server_default=text("'required'"),
        nullable=False,
    )
    due_date: Mapped[date | None] = mapped_column(Date)  # when it should be repaid (if any)
    reason: Mapped[str | None] = mapped_column(Text)

    status: Mapped[PayableStatus] = mapped_column(
        SAEnum(PayableStatus, name="payable_status", native_enum=False, create_constraint=False, length=20),
        default=PayableStatus.open,
        server_default=text("'open'"),
        nullable=False,
    )
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    importance: Mapped[ImportanceLevel] = mapped_column(
        SAEnum(ImportanceLevel, name="importance_level", native_enum=False, create_constraint=False, length=20),
        default=ImportanceLevel.medium,
        server_default=text("'medium'"),
        nullable=False,
    )
    ai_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_payables_user_id_status", "user_id", "status"),
        Index("ix_payables_user_id_due_date", "user_id", "due_date"),
    )
