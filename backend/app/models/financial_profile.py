"""Financial profile (Budget Intelligence System).

Who the user is and how they live — the foundation the realistic budget engine
reasons over (profile-first, not income-first). One row per user. Every field is
nullable and freely editable later (onboarding only seeds the starting profile;
the user can change anything by talking to Advary).
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Enum as SAEnum
from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import (
    FoodSituation,
    LifeStage,
    LivingSituation,
    OptimizationStyle,
    TransportMode,
    TuitionResponsibility,
)

if TYPE_CHECKING:
    from app.models.user import User


def _enum(enum_cls, name: str):
    return SAEnum(enum_cls, name=name, native_enum=False, create_constraint=False, length=32)


class FinancialProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "financial_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False,
    )

    # --- Who & where ---
    life_stage: Mapped[LifeStage | None] = mapped_column(_enum(LifeStage, "life_stage"))
    life_stage_note: Mapped[str | None] = mapped_column(String(200))   # "Other → tell me more"
    current_country: Mapped[str | None] = mapped_column(String(2))     # ISO-3166 alpha-2 (e.g. IN, JP)
    current_city: Mapped[str | None] = mapped_column(String(80))

    # Future move (also feeds Future Me): planning to move countries in ~2 years.
    moving_country: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), nullable=False)
    future_country: Mapped[str | None] = mapped_column(String(2))
    future_move_year: Mapped[int | None] = mapped_column(Integer)

    # --- How they live ---
    living_situation: Mapped[LivingSituation | None] = mapped_column(_enum(LivingSituation, "living_situation"))
    living_note: Mapped[str | None] = mapped_column(String(200))

    food_situation: Mapped[FoodSituation | None] = mapped_column(_enum(FoodSituation, "food_situation"))
    food_monthly: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))   # groceries / month
    food_daily: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))     # eating-out / day

    transport_mode: Mapped[TransportMode | None] = mapped_column(_enum(TransportMode, "transport_mode"))
    transport_monthly: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))

    tuition_responsibility: Mapped[TuitionResponsibility | None] = mapped_column(
        _enum(TuitionResponsibility, "tuition_responsibility"))

    # Rent (housing) and fun/lifestyle — base building blocks for the waterfall.
    rent_monthly: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    lifestyle_monthly: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))

    # What Advary optimizes the plan for (two identical budgets can want different plans).
    optimization_style: Mapped[OptimizationStyle] = mapped_column(
        _enum(OptimizationStyle, "optimization_style"),
        default=OptimizationStyle.balanced,
        server_default=text("'balanced'"),
        nullable=False,
    )

    user: Mapped[User] = relationship(back_populates="financial_profile")
