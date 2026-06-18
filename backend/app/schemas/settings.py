"""User-settings schemas with strict validation (Pydantic v2)."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import AiTone

# Money: non-negative NUMERIC(18,4). Up to 14 integer digits + 4 decimal places.
Money = Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=4)]


class NotificationPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")

    threshold_alerts: bool = True
    weekly_summary: bool = True
    planned_expense_reminders: bool = True
    monthly_report: bool = True
    # Voice companion (4c-B polish; consumed by Sprint 5 TTS via greeting.spoken_text)
    speak_greeting_on_open: bool = False
    speak_reminders: bool = False
    speak_celebrations: bool = True
    voice_when_tapped_only: bool = False


class UserSettingsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    base_currency: str
    locale: str | None
    timezone: str
    monthly_threshold: Decimal | None
    monthly_income_estimate: Decimal | None
    starting_balance: Decimal
    preferred_ai_tone: AiTone
    companion_style: str = "balanced"
    voice_length: str = "normal"
    selected_voice: str | None = None
    voice_locale: str | None = None
    companion_name: str | None = None
    display_name: str | None = None
    notification_preferences: NotificationPreferences
    currency_history: list[dict] | None = None


class UserSettingsUpdate(BaseModel):
    """All fields optional (partial update). Omitted fields are left unchanged."""

    model_config = ConfigDict(extra="forbid")

    base_currency: str | None = Field(default=None, min_length=3, max_length=3)
    locale: str | None = Field(default=None, max_length=10)
    timezone: str | None = Field(default=None, min_length=1, max_length=64)
    monthly_threshold: Money | None = None
    monthly_income_estimate: Money | None = None
    starting_balance: Money | None = None
    preferred_ai_tone: AiTone | None = None
    companion_style: str | None = Field(default=None, max_length=20)
    voice_length: str | None = Field(default=None, max_length=10)
    selected_voice: str | None = Field(default=None, max_length=120)
    voice_locale: str | None = Field(default=None, max_length=20)
    companion_name: str | None = Field(default=None, max_length=40)
    display_name: str | None = Field(default=None, max_length=60)
    notification_preferences: NotificationPreferences | None = None

    @field_validator("companion_name", "display_name", "selected_voice")
    @classmethod
    def _clean_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        v = value.strip()
        return v or None        # empty string clears the value

    @field_validator("companion_style")
    @classmethod
    def _validate_style(cls, value: str | None) -> str | None:
        if value is not None and value not in {"balanced", "cheerful", "professional", "anime", "minimal"}:
            raise ValueError("invalid companion_style")
        return value

    @field_validator("voice_length")
    @classmethod
    def _validate_voice_length(cls, value: str | None) -> str | None:
        if value is not None and value not in {"short", "normal", "detailed"}:
            raise ValueError("invalid voice_length")
        return value

    @field_validator("base_currency")
    @classmethod
    def _normalize_currency(cls, value: str | None) -> str | None:
        return value.upper() if value is not None else value
