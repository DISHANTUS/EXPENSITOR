"""Per-user adaptive policy (C7b) — derived from feedback + explicit edits.

Affects recommendation RANKING only (exclude / soft-downrank / boost). It must
NEVER change financial facts (affordability, risk, dependencies, balances,
savings) — facts stay facts. One row per user.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import ForeignKey, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class UserPolicy(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_policy"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    # { lever_stats: {lever: {accepted,rejected,deferred,emotional_rejects}},
    #   explicit_excluded: [lever], explicit_preferred: [lever],
    #   flags: {protect_emotional_critical, ...}, provenance: {lever: {reason, reason_context, since}} }
    policy: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb"), nullable=False
    )
