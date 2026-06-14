"""Expense categories. System categories have ``user_id IS NULL``."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.expense import Expense
    from app.models.planned_expense import PlannedExpense
    from app.models.user import User


class Category(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "categories"

    # NULL user_id => system/default category shared by all users.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    icon: Mapped[str | None] = mapped_column(String(50))
    color: Mapped[str | None] = mapped_column(String(9))
    is_system: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), nullable=False
    )
    # Drives Emergency Mode: essentials (rent/utilities) are not "cuttable".
    is_essential: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), nullable=False
    )

    user: Mapped[User | None] = relationship(back_populates="categories")
    expenses: Mapped[list[Expense]] = relationship(back_populates="category")
    planned_expenses: Mapped[list[PlannedExpense]] = relationship(back_populates="category")

    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_categories_user_id_name"),)
