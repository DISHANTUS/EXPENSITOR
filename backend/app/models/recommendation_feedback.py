"""Append-only log of user feedback on recommendations (C7b).

A preference signal only — it never executes the recommendation or changes any
financial fact. `reason_context` (D11) is kept for future explanations, not
decisions; `emotional_importance` (D12) lets the policy protect important events.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import RecommendationAction, RejectionReason


class RecommendationFeedback(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "recommendation_feedback"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    recommendation_id: Mapped[str] = mapped_column(String(120), nullable=False)
    lever_key: Mapped[str] = mapped_column(String(80), nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    action: Mapped[RecommendationAction] = mapped_column(
        SAEnum(RecommendationAction, name="recommendation_action", native_enum=False, create_constraint=False, length=20),
        nullable=False,
    )
    reason: Mapped[RejectionReason | None] = mapped_column(
        SAEnum(RejectionReason, name="rejection_reason", native_enum=False, create_constraint=False, length=20)
    )
    reason_context: Mapped[str | None] = mapped_column(Text)
    emotional_importance: Mapped[str | None] = mapped_column(String(20))
    note: Mapped[str | None] = mapped_column(Text)
    context: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    __table_args__ = (
        Index("ix_recommendation_feedback_user_id_lever_key", "user_id", "lever_key"),
        Index("ix_recommendation_feedback_user_id_created_at", "user_id", "created_at"),
    )
