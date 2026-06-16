"""Money the user expects to receive (separate from incomes/income_sources).

Pending receivables feed the projection income stream. `overdue` is derived
(one-time pending past its expected_date), never stored. Recurring receivables
expand monthly like income sources and are never overdue in C2.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    Time,
    text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import ExpectedTimeWindow, ReceivableKind, ReceivableSourceType, ReceivableStatus


class Receivable(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "receivables"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    source_name: Mapped[str] = mapped_column(String(200), nullable=False)
    source_type: Mapped[ReceivableSourceType] = mapped_column(
        SAEnum(ReceivableSourceType, name="receivable_source_type", native_enum=False, create_constraint=False, length=20),
        nullable=False,
    )
    kind: Mapped[ReceivableKind] = mapped_column(
        SAEnum(ReceivableKind, name="receivable_kind", native_enum=False, create_constraint=False, length=20),
        nullable=False,
    )
    # Stored status is pending/received/cancelled; `overdue` is derived on read.
    status: Mapped[ReceivableStatus] = mapped_column(
        SAEnum(ReceivableStatus, name="receivable_status", native_enum=False, create_constraint=False, length=20),
        default=ReceivableStatus.pending,
        server_default=text("'pending'"),
        nullable=False,
    )

    # --- Multi-currency snapshot (base-currency math) ---
    original_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    original_currency: Mapped[str] = mapped_column(String(3), ForeignKey("currencies.code"), nullable=False)
    exchange_rate: Mapped[Decimal] = mapped_column(Numeric(20, 10), nullable=False)
    converted_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    base_currency: Mapped[str] = mapped_column(String(3), ForeignKey("currencies.code"), nullable=False)

    # one_time -> expected_date; recurring -> recurrence_day (1-31).
    expected_date: Mapped[date | None] = mapped_column(Date)
    recurrence_day: Mapped[int | None] = mapped_column(Integer)

    reliability: Mapped[Decimal] = mapped_column(
        Numeric(4, 3), default=Decimal("0.5"), server_default=text("0.5"), nullable=False
    )
    # Income Timing Intelligence: rough arrival window + optional exact time (NULL = unknown).
    expected_time_window: Mapped[ExpectedTimeWindow | None] = mapped_column(
        SAEnum(ExpectedTimeWindow, name="expected_time_window", native_enum=False, create_constraint=False, length=20)
    )
    expected_time: Mapped[time | None] = mapped_column(Time)
    notes: Mapped[str | None] = mapped_column(Text)
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Follow-up tracking (stored only in C2; companion uses it later).
    last_follow_up_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    follow_up_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0"), nullable=False
    )

    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("reliability >= 0 AND reliability <= 1", name="ck_receivables_reliability_range"),
        CheckConstraint(
            "recurrence_day IS NULL OR (recurrence_day >= 1 AND recurrence_day <= 31)",
            name="ck_receivables_recurrence_day_range",
        ),
        Index("ix_receivables_user_id_status", "user_id", "status"),
        Index("ix_receivables_user_id_expected_date", "user_id", "expected_date"),
    )
