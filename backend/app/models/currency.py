"""Reference table of supported currencies."""

from __future__ import annotations

from sqlalchemy import Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class Currency(TimestampMixin, Base):
    __tablename__ = "currencies"

    # ISO 4217 code, e.g. "INR". Natural primary key.
    code: Mapped[str] = mapped_column(String(3), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    symbol: Mapped[str] = mapped_column(String(8), nullable=False)
    # Minor-unit digits used for rounding/display (e.g. JPY = 0, INR = 2).
    decimal_digits: Mapped[int] = mapped_column(
        Integer, default=2, server_default=text("2"), nullable=False
    )
