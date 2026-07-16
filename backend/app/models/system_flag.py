"""A tiny key/value store for facts about the deployment itself.

Exists for one honest reason: there is no scheduler here, and some things must
happen at most once per day (the developer digest). "When did I last send it?"
has to survive a restart — and Render's free tier spins the service down when
idle, so an in-process variable would reset constantly and the rate limit would
mean nothing.

Not user data. Nothing here is per-account.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import String
from sqlalchemy import text as sa_text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class SystemFlag(TimestampMixin, Base):
    __tablename__ = "system_flags"

    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=sa_text("'{}'::jsonb"), nullable=False
    )
