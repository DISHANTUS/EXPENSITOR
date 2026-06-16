"""Actual-income schemas (historical receipts)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import IncomeSourceType

Money = Annotated[Decimal, Field(gt=0, max_digits=18, decimal_places=4)]


class IncomeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: IncomeSourceType
    original_amount: Money
    original_currency: str = Field(min_length=3, max_length=3)
    received_date: date
    description: str | None = Field(default=None, max_length=500)

    @field_validator("original_currency")
    @classmethod
    def _upper(cls, value: str) -> str:
        return value.upper()


class IncomeUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: IncomeSourceType | None = None
    original_amount: Money | None = None
    original_currency: str | None = Field(default=None, min_length=3, max_length=3)
    received_date: date | None = None
    description: str | None = Field(default=None, max_length=500)

    @field_validator("original_currency")
    @classmethod
    def _upper(cls, value: str | None) -> str | None:
        return value.upper() if value is not None else value


class IncomeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_type: IncomeSourceType
    original_amount: Decimal
    original_currency: str
    exchange_rate: Decimal
    converted_amount: Decimal
    base_currency: str
    description: str | None
    received_date: date
    created_at: datetime
    updated_at: datetime
