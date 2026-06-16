"""Daily budget session — a spending session ("money taken outside").

A grouping layer over ordinary expenses (linked via session_expenses). The
session's budget carries an FX snapshot; spend is derived from linked expenses.
`alerted_thresholds` is a JSONB array of % bands already warned (future-proof).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import BudgetSessionStatus


class BudgetSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "budget_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)

    # --- Budget FX snapshot (base-currency math) ---
    original_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    original_currency: Mapped[str] = mapped_column(String(3), ForeignKey("currencies.code"), nullable=False)
    exchange_rate: Mapped[Decimal] = mapped_column(Numeric(20, 10), nullable=False)
    converted_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    base_currency: Mapped[str] = mapped_column(String(3), ForeignKey("currencies.code"), nullable=False)

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[BudgetSessionStatus] = mapped_column(
        SAEnum(BudgetSessionStatus, name="budget_session_status", native_enum=False, create_constraint=False, length=20),
        default=BudgetSessionStatus.active,
        server_default=text("'active'"),
        nullable=False,
    )

    # % bands (50/75/90/100…) already warned — JSONB array so custom bands need no migration.
    alerted_thresholds: Mapped[list[int]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb"), nullable=False
    )

    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("ix_budget_sessions_user_id_status", "user_id", "status"),)
