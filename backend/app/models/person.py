"""A Person in the user's financial life (V2 relationship memory).

Receivables, borrowed money, gifts and recurring parental support reference a
Person so the advisor can reason across interactions ("Ravi usually returns
money late", "Dad often helps with large purchases") without duplicate names.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Numeric, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import RelationshipType


class Person(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "persons"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    nickname: Mapped[str | None] = mapped_column(String(100))
    relationship_type: Mapped[RelationshipType] = mapped_column(
        SAEnum(RelationshipType, name="relationship_type", native_enum=False, create_constraint=False, length=20),
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(Text)
    # Derived/maintained reliability (0..1); NULL until enough history.
    reliability_score: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    first_interaction_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_interaction_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    tags: Mapped[list[Any] | None] = mapped_column(JSONB)
    ai_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(
            "reliability_score IS NULL OR (reliability_score >= 0 AND reliability_score <= 1)",
            name="ck_persons_reliability_score_range",
        ),
        Index("ix_persons_user_id_name", "user_id", "name"),
    )
