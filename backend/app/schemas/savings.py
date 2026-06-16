"""Savings-goal schemas (Tier 1)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import RecoveryMode, SavingsGoalKind, SavingsGoalStatus

Money = Annotated[Decimal, Field(gt=0, max_digits=18, decimal_places=4)]


class SavingsGoalCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    kind: SavingsGoalKind
    original_amount: Money
    original_currency: str = Field(min_length=3, max_length=3)
    target_date: date | None = None
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("original_currency")
    @classmethod
    def _upper(cls, value: str) -> str:
        return value.upper()

    @model_validator(mode="after")
    def _validate_kind(self) -> "SavingsGoalCreate":
        if self.kind == SavingsGoalKind.custom_goal and self.target_date is None:
            raise ValueError("target_date is required for a custom goal")
        if self.kind == SavingsGoalKind.monthly_target:
            self.target_date = None
        return self


class SavingsGoalUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=255)
    original_amount: Money | None = None
    original_currency: str | None = Field(default=None, min_length=3, max_length=3)
    target_date: date | None = None
    status: SavingsGoalStatus | None = None
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("original_currency")
    @classmethod
    def _upper(cls, value: str | None) -> str | None:
        return value.upper() if value is not None else value


class RecoveryIn(BaseModel):
    """The user's explicit recovery choice. The system never decides this."""

    model_config = ConfigDict(extra="forbid")

    choice: RecoveryMode
    distribute_months: int | None = Field(default=None, ge=1, le=24)
    # for choice == new_plan:
    new_target_amount: Money | None = None
    new_target_currency: str | None = Field(default=None, min_length=3, max_length=3)
    new_target_date: date | None = None

    @field_validator("new_target_currency")
    @classmethod
    def _upper(cls, value: str | None) -> str | None:
        return value.upper() if value is not None else value


class SavingsGoalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    kind: SavingsGoalKind
    original_amount: Decimal
    original_currency: str
    exchange_rate: Decimal
    converted_amount: Decimal
    base_currency: str
    target_date: date | None
    start_date: date
    status: SavingsGoalStatus
    recovery_mode: RecoveryMode | None
    carried_deficit: Decimal
    distribute_months: int | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
