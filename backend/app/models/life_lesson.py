"""Life lessons (Sprint 4b-5b) — things the USER taught the companion about
their own financial life ("I overspent because my laptop broke").

Never inferred by an LLM. Confidence grows with repetition (occurrences); the
lifecycle is active -> confirmed -> archived, and `forgotten` is a reversible
user action (we never auto-delete — people change, and the timeline may still
want to reference an old lesson).

Surfacing is gated on CONFIRMED+ confidence so the companion never overlearns
from a single event. `times_helpful` vs `times_surfaced` lets later sprints rank
which lessons actually earn their place.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class LifeLesson(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "life_lessons"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    lesson: Mapped[str] = mapped_column(Text, nullable=False)          # canonical statement
    category: Mapped[str] = mapped_column(String(40), nullable=False)  # emergency_fund|lending|subscriptions|...
    source: Mapped[str] = mapped_column(String(20), nullable=False)    # user_taught|reflection|derived
    source_text: Mapped[str | None] = mapped_column(Text)             # the user's original wording
    trigger_context: Mapped[str | None] = mapped_column(String(80))  # when to surface (category/keyword/situation)

    occurrences: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    confidence: Mapped[str] = mapped_column(String(10), nullable=False)   # LessonConfidence
    status: Mapped[str] = mapped_column(String(12), nullable=False)       # LessonStatus
    importance: Mapped[str] = mapped_column(String(20), nullable=False)   # ImportanceLevel

    times_surfaced: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    times_helpful: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    first_observed: Mapped[date] = mapped_column(Date, nullable=False)
    last_observed: Mapped[date] = mapped_column(Date, nullable=False)
    last_surfaced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_life_lessons_user_status", "user_id", "status"),
        Index("ix_life_lessons_user_category", "user_id", "category"),
    )
