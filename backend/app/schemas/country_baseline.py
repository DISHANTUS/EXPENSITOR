"""Country baseline schema (Budget Intelligence System — Phase 6)."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel


class CountryBaseline(BaseModel):
    country: str | None              # ISO alpha-2 (from the user's profile)
    group: str                       # student | working | default
    currency: str | None             # local currency the figures are in
    food_daily: Decimal | None
    transport_monthly: Decimal | None
    confidence: str                  # high | medium | low
    source: str                      # bundled | refreshed | none
    note: str = (
        "Reference only — your real spending is what counts. I use this to tell you "
        "whether you're below or above the local average for someone like you, never "
        "to tell you to spend more."
    )
