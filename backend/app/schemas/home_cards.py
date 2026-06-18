"""Home preview cards schema (UI-X — Living Quick Cards).

The Home quick-actions row, reimagined as *previews* rather than menu buttons:
each card shows a real glimpse of the user's story / future / people / focus.
"""

from __future__ import annotations

from pydantic import BaseModel


class HomeCard(BaseModel):
    key: str                       # story | future | people | focus
    icon: str                      # leading emoji
    title: str                     # "Your Story"
    headline: str                  # the preview's main line
    subtitle: str | None = None    # a supporting glimpse
    route: str                     # where tapping the card goes


class HomeCards(BaseModel):
    cards: list[HomeCard]
