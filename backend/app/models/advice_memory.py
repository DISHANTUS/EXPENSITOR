"""Advice memory (Sprint 4b-5a) — what the companion told the user, so it can
come back later and ask "what happened?".

This is the QUESTION/PROMISE tracker that sits ABOVE the Phase-E ``outcomes``
ledger: when a follow-up is answered, an ``Outcome`` row is recorded (the
evidence) and this row is marked answered. It NEVER modifies any financial fact;
it only schedules questions and stores what we said + what the user replied.

Importance gating (see ``intelligence/learning/importance.py``) decides whether —
and how often — a row gets a ``follow_up_due``.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AdviceMemory(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "advice_memory"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False)          # AdviceKind
    importance: Mapped[str] = mapped_column(String(20), nullable=False)    # low|medium|high
    status: Mapped[str] = mapped_column(String(20), nullable=False)        # AdviceStatus

    # What/who the advice is about (for recall + dedup).
    subject_type: Mapped[str] = mapped_column(String(40), nullable=False)  # goal|person|category|subscription|budget
    subject_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    subject_label: Mapped[str | None] = mapped_column(String(120))         # e.g. "Ravi", "Food & Dining"
    lever_key: Mapped[str | None] = mapped_column(String(80))
    category_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))

    claim: Mapped[str] = mapped_column(Text, nullable=False)               # what we actually said
    # Forecast snapshot (for 4b-5b prediction accuracy); harmless to store now.
    expected_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    expected_date: Mapped[date | None] = mapped_column(Date)               # e.g. forecast ETA
    assumptions: Mapped[dict | None] = mapped_column(JSONB)                # savings rate / progress at the time

    # The follow-up.
    follow_up_due: Mapped[date | None] = mapped_column(Date)               # None => never follow up (low importance)
    follow_up_count: Mapped[int] = mapped_column(default=0, nullable=False)
    answer: Mapped[str | None] = mapped_column(String(20))                 # yes|partial|no (or outcome status)
    answer_detail: Mapped[str | None] = mapped_column(Text)               # the free-text "tell me more"
    circumstance: Mapped[str | None] = mapped_column(String(40))          # E7 classified (NULL = genuine)
    outcome_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("outcomes.id", ondelete="SET NULL")
    )

    base_currency: Mapped[str | None] = mapped_column(String(3))
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_advice_memory_user_status_due", "user_id", "status", "follow_up_due"),
        Index("ix_advice_memory_user_subject", "user_id", "subject_type", "subject_label"),
    )
