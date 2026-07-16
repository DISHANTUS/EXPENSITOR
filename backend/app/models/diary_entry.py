"""The user's own notes about their day — the raw material Advary learns from.

Deliberately NOT an expense: a diary entry is what happened ("bought fruits at
the market"), not a transaction. Some entries lead to money facts and some never
do, and forcing them into the ledger would either invent amounts nobody stated
or throw away everything that isn't a purchase.

`details` holds the branching follow-ups as an ordered list of
``{"question": ..., "answer": ...}`` — Advary asking "which fruits?" and the
user answering "apples and mangoes". They live with the entry rather than in
their own table because they are only ever read as part of it, and they're the
entry's own words, not a separate record.

This is the user's private diary. It is used to make THEIR experience better —
patterns surfaced back to them, in their app. It is not training data for a
shared model, and nothing here leaves their account.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Date, DateTime, ForeignKey, Index, Text
from sqlalchemy import text as sa_text  # aliased: this model has a column literally named `text`,
                                        # which would shadow sqlalchemy.text inside the class body
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class DiaryEntry(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "diary_entries"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    entry_date: Mapped[date] = mapped_column(Date, nullable=False)

    # The user's own words, exactly as typed. Never rewritten — an interpretation
    # layer may sit on top, but the source of truth stays verbatim.
    text: Mapped[str] = mapped_column(Text, nullable=False)

    # [{"question": "Which fruits?", "answer": "apples and mangoes"}, ...]
    details: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, default=list, server_default=sa_text("'[]'::jsonb"), nullable=False
    )

    # Set once Advary has stopped asking about this entry — either it ran out of
    # questions or the user waved it off. Stops a note being an interrogation.
    closed: Mapped[bool] = mapped_column(
        nullable=False, default=False, server_default=sa_text("false")
    )

    # Soft delete, like every other user-owned row here: a deleted diary entry
    # must drop out of pattern learning immediately, but "delete" on a personal
    # diary shouldn't be the one irreversible button in the app.
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_diary_entries_user_date", "user_id", "entry_date"),
    )
