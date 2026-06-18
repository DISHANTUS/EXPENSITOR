"""Future planned expenses — the hero feature's primary data."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Numeric, String, Text, text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import ImportanceLevel, OccasionType, PlannedExpensePriority, PlannedExpenseStatus

if TYPE_CHECKING:
    from app.models.category import Category
    from app.models.user import User


class PlannedExpense(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "planned_expenses"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("categories.id", ondelete="SET NULL")
    )

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    planned_date: Mapped[date] = mapped_column(Date, nullable=False)
    # Non-null marks this planned expense as a planner Event (C4).
    occasion_type: Mapped[OccasionType | None] = mapped_column(
        SAEnum(OccasionType, name="occasion_type", native_enum=False, create_constraint=False, length=20)
    )

    # --- Multi-currency snapshot (rate captured at planning time) ---
    original_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    original_currency: Mapped[str] = mapped_column(
        String(3), ForeignKey("currencies.code"), nullable=False
    )
    exchange_rate: Mapped[Decimal] = mapped_column(Numeric(20, 10), nullable=False)
    converted_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    base_currency: Mapped[str] = mapped_column(
        String(3), ForeignKey("currencies.code"), nullable=False
    )

    priority: Mapped[PlannedExpensePriority] = mapped_column(
        SAEnum(
            PlannedExpensePriority,
            name="planned_expense_priority",
            native_enum=False,
            create_constraint=False,
            length=20,
        ),
        default=PlannedExpensePriority.medium,
        server_default=text("'medium'"),
        nullable=False,
    )
    status: Mapped[PlannedExpenseStatus] = mapped_column(
        SAEnum(
            PlannedExpenseStatus,
            name="planned_expense_status",
            native_enum=False,
            create_constraint=False,
            length=20,
        ),
        default=PlannedExpenseStatus.planned,
        server_default=text("'planned'"),
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(Text)

    # Stored for future Projection Engine work; no recurrence scheduling yet.
    is_recurring: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), nullable=False
    )

    # Cached most-recent feasibility result (computed on write/read; future).
    last_feasibility: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    # Set when the plan is converted into an actual expense (future).
    converted_expense_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("expenses.id", ondelete="SET NULL")
    )

    # V2: significance (drives timeline/mood priority) + standardized advisor metadata.
    importance: Mapped[ImportanceLevel] = mapped_column(
        SAEnum(ImportanceLevel, name="importance_level", native_enum=False, create_constraint=False, length=20),
        default=ImportanceLevel.medium,
        server_default=text("'medium'"),
        nullable=False,
    )
    ai_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    # Soft delete keeps history intact for future offline sync.
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="planned_expenses")
    category: Mapped[Category | None] = relationship(back_populates="planned_expenses")

    __table_args__ = (
        Index("ix_planned_expenses_user_id_planned_date", "user_id", "planned_date"),
        Index("ix_planned_expenses_user_id_status", "user_id", "status"),
    )
