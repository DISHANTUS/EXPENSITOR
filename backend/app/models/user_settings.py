"""Per-user settings: base currency, threshold, income estimate, savings."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Numeric, String, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.user import User


class UserSettings(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_settings"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    base_currency: Mapped[str] = mapped_column(
        String(3),
        ForeignKey("currencies.code"),
        default="INR",
        server_default=text("'INR'"),
        nullable=False,
    )
    locale: Mapped[str | None] = mapped_column(String(10))
    timezone: Mapped[str] = mapped_column(
        String(64), default="UTC", server_default=text("'UTC'"), nullable=False
    )
    monthly_threshold: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    monthly_income_estimate: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    starting_savings: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), default=Decimal("0"), server_default=text("0"), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="settings")
