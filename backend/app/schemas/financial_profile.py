"""Financial profile schemas (Budget Intelligence System)."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import (
    FoodSituation,
    LifeStage,
    LivingSituation,
    TransportMode,
    TuitionResponsibility,
)

Money = Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=4)]
_Country = Annotated[str, Field(min_length=2, max_length=2)]


class FinancialProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    life_stage: LifeStage | None = None
    life_stage_note: str | None = None
    current_country: str | None = None
    current_city: str | None = None
    moving_country: bool = False
    future_country: str | None = None
    future_move_year: int | None = None
    living_situation: LivingSituation | None = None
    living_note: str | None = None
    food_situation: FoodSituation | None = None
    food_monthly: Decimal | None = None
    food_daily: Decimal | None = None
    transport_mode: TransportMode | None = None
    transport_monthly: Decimal | None = None
    tuition_responsibility: TuitionResponsibility | None = None
    rent_monthly: Decimal | None = None
    lifestyle_monthly: Decimal | None = None


class FinancialProfileUpdate(BaseModel):
    """Partial update — omitted fields are left unchanged. Everything is editable
    anytime (onboarding only seeds the starting profile)."""

    model_config = ConfigDict(extra="forbid")

    life_stage: LifeStage | None = None
    life_stage_note: str | None = Field(default=None, max_length=200)
    current_country: _Country | None = None
    current_city: str | None = Field(default=None, max_length=80)
    moving_country: bool | None = None
    future_country: _Country | None = None
    future_move_year: int | None = Field(default=None, ge=2000, le=2100)
    living_situation: LivingSituation | None = None
    living_note: str | None = Field(default=None, max_length=200)
    food_situation: FoodSituation | None = None
    food_monthly: Money | None = None
    food_daily: Money | None = None
    transport_mode: TransportMode | None = None
    transport_monthly: Money | None = None
    tuition_responsibility: TuitionResponsibility | None = None
    rent_monthly: Money | None = None
    lifestyle_monthly: Money | None = None

    @field_validator("current_country", "future_country")
    @classmethod
    def _upper(cls, v: str | None) -> str | None:
        return v.upper() if v is not None else v
