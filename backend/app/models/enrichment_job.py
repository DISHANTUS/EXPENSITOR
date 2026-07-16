"""Work parked for the local model to do later.

The app is deliberately rules-first: everything a user does gets a real answer
immediately, from deterministic code, with no model involved. But some things
the rules genuinely can't see — and today, when no model is reachable, that
insight is simply lost forever.

This is the catch-up queue. When the rules come up empty AND no model can be
reached, the item is parked here instead of dropped. When a model IS reachable
the backlog drains and the answers surface the normal way (the user's diary
entry gains its question, the orb lights up). The user never waits on it and
never sees a failure — it either helps later or it doesn't.

Deliberately NOT a general task queue: there's no scheduler in this app and no
worker process. Draining is something that happens when a model is known to be
up — today by the developer flipping their laptop on, later by a hosted model.
The design is identical either way, which is the point.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy import text as sa_text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

# String, not a native enum: new kinds must not need a migration (same call the
# rest of this codebase makes, e.g. AdviceMemory.kind).
KIND_DIARY_FOLLOWUP = "diary_followup"

STATUS_PENDING = "pending"
STATUS_DONE = "done"
STATUS_FAILED = "failed"
STATUS_SKIPPED = "skipped"  # drained fine; the model simply had nothing to add


class EnrichmentJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "enrichment_jobs"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(40), nullable=False)

    # What the job is about — ids and the text needed to run it. Stays on the
    # user's own row, in their own account; nothing here is ever sent anywhere.
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=sa_text("'{}'::jsonb"), nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=STATUS_PENDING, server_default=sa_text("'pending'")
    )
    attempts: Mapped[int] = mapped_column(nullable=False, default=0, server_default=sa_text("0"))
    last_error: Mapped[str | None] = mapped_column(Text)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_enrichment_jobs_status", "status"),
        Index("ix_enrichment_jobs_user", "user_id"),
    )
