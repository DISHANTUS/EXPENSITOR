"""Outcome tracking (Phase E) — a single, kind-discriminated record of what
actually happened after a decision/recommendation/goal/plan.

Append-only learning signal. It NEVER modifies any financial fact or entity — it
only feeds ordering / ranking / confidence / annotations / adaptive planning.
Values are base-currency derived analytics (not user-entered money), so no
original-currency FX snapshot. String-backed enums (app-validated) for forward
compatibility.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Outcome(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "outcomes"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False)          # decision|recommendation|goal|plan
    subject_type: Mapped[str] = mapped_column(String(40), nullable=False)
    subject_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    lever_key: Mapped[str | None] = mapped_column(String(80))
    category_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))

    expected_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    actual_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    variance: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    metric: Mapped[str | None] = mapped_column(String(60))

    # success | partial | failed | abandoned | ahead | on_track | behind | missed | unknown
    outcome: Mapped[str] = mapped_column(String(20), nullable=False)
    outcome_reason: Mapped[str | None] = mapped_column(Text)
    circumstance: Mapped[str | None] = mapped_column(String(40))           # E7: classified circumstance (NULL = genuine)
    source: Mapped[str] = mapped_column(String(20), nullable=False)        # derived|user_reported
    base_currency: Mapped[str | None] = mapped_column(String(3))

    period_month: Mapped[date | None] = mapped_column(Date)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_outcomes_user_id_kind_lever_key", "user_id", "kind", "lever_key"),
        Index("ix_outcomes_user_id_kind_subject_id", "user_id", "kind", "subject_id", "period_month"),
    )
