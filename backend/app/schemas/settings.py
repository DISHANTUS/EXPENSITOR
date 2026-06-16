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


class UserSettingsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    base_currency: str
    locale: str | None
    timezone: str
    monthly_threshold: Decimal | None
    monthly_income_estimate: Decimal | None
    starting_balance: Decimal
    preferred_ai_tone: AiTone
    notification_preferences: NotificationPreferences


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
    notification_preferences: NotificationPreferences | None = None

    @field_validator("base_currency")
    @classmethod
    def _normalize_currency(cls, value: str | None) -> str | None:
        return value.upper() if value is not None else value
