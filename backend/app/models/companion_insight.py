"""Persisted companion insights — the read/unread feed.

`facts` (JSONB) holds the engine-computed numbers (the companion never computes
them itself); `category` covers all six message categories; `related_entity_*`
can link to any current or future entity. Soft-deletable (dismiss).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import CompanionCategory, CompanionEntityType, CompanionSeverity


class CompanionInsight(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "companion_insights"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    category: Mapped[CompanionCategory] = mapped_column(
        SAEnum(CompanionCategory, name="companion_category", native_enum=False, create_constraint=False, length=30),
        nullable=False,
    )
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    surface: Mapped[str | None] = mapped_column(String(100))
    severity: Mapped[CompanionSeverity] = mapped_column(
        SAEnum(CompanionSeverity, name="companion_severity", native_enum=False, create_constraint=False, length=20),
        default=CompanionSeverity.info,
        server_default=text("'info'"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    facts: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb"), nullable=False
    )
    source: Mapped[str] = mapped_column(
        String(20), default="engine", server_default=text("'engine'"), nullable=False
    )
    related_entity_type: Mapped[CompanionEntityType | None] = mapped_column(
        SAEnum(CompanionEntityType, name="companion_entity_type", native_enum=False, create_constraint=False, length=30)
    )
    related_entity_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))
    is_read: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("ix_companion_insights_user_id_created_at", "user_id", "created_at"),)
