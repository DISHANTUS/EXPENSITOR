"""Life events (Sprint 6b) — user-entered milestones for the Life Timeline that
aren't expenses: "Move to Japan", "Master's begins", "First full-time role".

These make the timeline a *life* story, not just a finance log. They can be past
or future; future ones become Future-Me milestones alongside forecasts.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class LifeEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "life_events"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    event_date: Mapped[date] = mapped_column(Date, nullable=False)
    kind: Mapped[str] = mapped_column(String(30), default="milestone", nullable=False)  # milestone|move|education|career|custom
    icon: Mapped[str | None] = mapped_column(String(8))
    note: Mapped[str | None] = mapped_column(Text)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
