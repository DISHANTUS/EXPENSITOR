"""User account model (tenant root)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.category import Category
    from app.models.expense import Expense
    from app.models.income import Income
    from app.models.income_source import IncomeSource
    from app.models.planned_expense import PlannedExpense
    from app.models.refresh_token import RefreshToken
    from app.models.user_settings import UserSettings


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    # Stored lower-cased by the service layer; uniqueness is case-insensitive.
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true"), nullable=False
    )

    settings: Mapped[UserSettings] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    refresh_tokens: Mapped[list[RefreshToken]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    categories: Mapped[list[Category]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    incomes: Mapped[list[Income]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    income_sources: Mapped[list[IncomeSource]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    expenses: Mapped[list[Expense]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    planned_expenses: Mapped[list[PlannedExpense]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
