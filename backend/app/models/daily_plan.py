"""Per-day budget plan (V2 calendar foundation).

One row per (user, date). ``planned_budget`` is the user's chosen allowance for
that day; when NULL the calendar falls back to a derived budget. Red/saved/within
classification is DERIVED from budget-vs-actual at read time and never stored,
so it cannot be gamed. ``overspend_reason`` is the user's note on a red day.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Numeric, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class DailyPlan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "daily_plans"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    plan_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Chosen daily allowance in base currency. NULL => use derived default.
    planned_budget: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))

    # Set when the day's budget is locked (first expense of the day recorded).
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # True if the budget was changed after spending began (analysis caveat).
    modified_after_start: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), nullable=False
    )
    overspend_reason: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint("user_id", "plan_date", name="uq_daily_plans_user_id_plan_date"),
        Index("ix_daily_plans_user_id_plan_date", "user_id", "plan_date"),
    )
