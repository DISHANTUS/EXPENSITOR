"""Per-user settings: base currency, threshold, starting balance, income
estimate, AI tone, and notification preferences."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime
from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Numeric, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import AiTone

if TYPE_CHECKING:
    from app.models.user import User

# Default notification preferences (used as the Python-side and DB-side default).
DEFAULT_NOTIFICATION_PREFERENCES: dict[str, bool] = {
    "threshold_alerts": True,
    "weekly_summary": True,
    "planned_expense_reminders": True,
    "monthly_report": True,
    "speak_greeting_on_open": False,
    "speak_reminders": False,
    "speak_celebrations": True,
    "voice_when_tapped_only": False,
}
_NOTIFICATION_PREFERENCES_SQL_DEFAULT = (
    "'{\"threshold_alerts\": true, \"weekly_summary\": true, "
    "\"planned_expense_reminders\": true, \"monthly_report\": true}'::jsonb"
)


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

    # --- Money values (NUMERIC, never float) ---
    monthly_threshold: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    monthly_income_estimate: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    # Available money at onboarding (formerly "starting_savings").
    starting_balance: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), default=Decimal("0"), server_default=text("0"), nullable=False
    )

    # --- Co-pilot preferences ---
    preferred_ai_tone: Mapped[AiTone] = mapped_column(
        SAEnum(
            AiTone,
            name="ai_tone",
            native_enum=False,
            create_constraint=False,
            length=20,
        ),
        default=AiTone.balanced,
        server_default=text("'balanced'"),
        nullable=False,
    )
    notification_preferences: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=lambda: dict(DEFAULT_NOTIFICATION_PREFERENCES),
        server_default=text(_NOTIFICATION_PREFERENCES_SQL_DEFAULT),
        nullable=False,
    )
    # Companion personality for greetings/narration (4c-B): balanced | cheerful |
    # professional | anime | minimal. Same facts, different wording.
    companion_style: Mapped[str] = mapped_column(
        String(20), default="balanced", server_default=text("'balanced'"), nullable=False
    )
    # Voice length for spoken greetings (Sprint 5): short | normal | detailed.
    voice_length: Mapped[str] = mapped_column(
        String(10), default="normal", server_default=text("'normal'"), nullable=False
    )
    # Chosen device TTS voice (Voice Studio, UI-X). flutter_tts voice name + locale,
    # both device-specific. None = use the system default. Applied on launch if the
    # voice still exists on the device; harmless if it doesn't.
    selected_voice: Mapped[str | None] = mapped_column(String(120))
    voice_locale: Mapped[str | None] = mapped_column(String(20))
    # The companion's name (Sprint 6c). None = unnamed (stays generic).
    companion_name: Mapped[str | None] = mapped_column(String(40))
    # What the user wants to be called (asked in onboarding). None = use a neutral
    # greeting. The email is never used as a display identity.
    display_name: Mapped[str | None] = mapped_column(String(60))
    # Audit of preferred-currency periods: [{currency, from, to?}, ...]. Enables
    # "show my spending before I moved to Japan".
    currency_history: Mapped[list[Any] | None] = mapped_column(JSONB)
    # When the first-launch guided tour was completed/skipped. NULL = not seen yet
    # → the client launches the tour once. Cleared on full/demo reset so a fresh
    # (or handed-over) account replays it.
    tour_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="settings")
