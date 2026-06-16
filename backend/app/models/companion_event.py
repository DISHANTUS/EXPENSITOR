"""Append-only log of companion-relevant user interactions.

Future-proof by design: `event_type`/`entity_type` are VARCHAR-backed enums with
reserved future values, and `payload` (JSONB) can carry any future feature data
(session amounts, event budgets, receivable details) with no schema change.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, String, func, text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import CompanionEntityType, CompanionEventType


class CompanionEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "companion_events"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[CompanionEventType] = mapped_column(
        SAEnum(CompanionEventType, name="companion_event_type", native_enum=False, create_constraint=False, length=30),
        nullable=False,
    )
    surface: Mapped[str | None] = mapped_column(String(100))
    action: Mapped[str | None] = mapped_column(String(100))
    entity_type: Mapped[CompanionEntityType | None] = mapped_column(
        SAEnum(CompanionEntityType, name="companion_entity_type", native_enum=False, create_constraint=False, length=30)
    )
    entity_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_companion_events_user_id_occurred_at", "user_id", "occurred_at"),
        Index("ix_companion_events_user_id_event_type", "user_id", "event_type"),
    )
