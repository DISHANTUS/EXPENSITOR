"""Budget-session request/response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import BudgetSessionStatus

Money = Annotated[Decimal, Field(gt=0, max_digits=18, decimal_places=4)]


class BudgetSessionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=255)
    budget_amount: Money
    currency: str = Field(min_length=3, max_length=3)

    @field_validator("currency")
    @classmethod
    def _upper(cls, value: str) -> str:
        return value.upper()


class BudgetSessionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=255)
    budget_amount: Money | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)

    @field_validator("currency")
    @classmethod
    def _upper(cls, value: str | None) -> str | None:
        return value.upper() if value is not None else value


class LinkExpenseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expense_id: uuid.UUID


class SessionRead(BaseModel):
    id: uuid.UUID
    title: str
    original_amount: Decimal
    original_currency: str
    exchange_rate: Decimal
    converted_amount: Decimal
    base_currency: str
    started_at: datetime
    ended_at: datetime | None
    status: BudgetSessionStatus
    spent: Decimal
    remaining: Decimal
    saved: Decimal
    utilization_percent: Decimal
    expense_count: int
    category_breakdown: dict[str, Decimal]
    alerted_thresholds: list[int]
    created_at: datetime
    updated_at: datetime
