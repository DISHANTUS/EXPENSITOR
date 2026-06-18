"""Fun-facts schemas (companion fallback / orb / Home card)."""

from __future__ import annotations

from pydantic import BaseModel


class FactOut(BaseModel):
    text: str
    category: str        # slug, e.g. "money"
    category_label: str  # display, e.g. "Money"
    emoji: str


class FactCategoryOut(BaseModel):
    key: str
    label: str
    emoji: str
    count: int


class FactPackOut(BaseModel):
    """A whole category's facts — the client caches this for offline use."""
    category: str
    category_label: str
    emoji: str
    facts: list[str]
