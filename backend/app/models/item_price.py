"""What the user has paid for a named thing, over time.

Every confirmed receipt line — "Milk 1L … 58.00" — is one observation here.
Enough of them and the app can say "milk usually costs you ₹58", flag when a
shop charged more, and eventually spot which shop is dearer.

Strictly the user's OWN observations. A regional/shared view (a neighbourhood
price, anonymised) is a deliberate later layer on top of this, gated on an
explicit privacy decision — this table never mixes one person's prices into
another's.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Index, Numeric, String
from sqlalchemy import text as sa_text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ItemPrice(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "item_prices"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # The user's own wording, kept verbatim for display.
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # Folded key ("milk 1l") so "Milk 1L" and "milk 1l" are the same item.
    name_key: Mapped[str] = mapped_column(String(200), nullable=False)

    price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)

    # The receipt's date, not when it was entered — a price is about when it was
    # paid, and the app may record an old receipt today.
    observed_on: Mapped[date] = mapped_column(Date, nullable=False)

    # Where it was bought, when known — the seed of "which shop is dearer".
    merchant: Mapped[str | None] = mapped_column(String(200))

    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_item_prices_user_key", "user_id", "name_key"),
    )
