"""Link between a budget session and an ordinary expense (grouping only).

An expense belongs to at most one session (unique expense_id). No accounting
happens here — the expense is already counted in the expenses table.
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class SessionExpense(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "session_expenses"

    session_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("budget_sessions.id", ondelete="CASCADE"), nullable=False
    )
    expense_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("expenses.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    __table_args__ = (Index("ix_session_expenses_session_id", "session_id"),)
