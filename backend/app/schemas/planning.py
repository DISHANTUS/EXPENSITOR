"""Planning-intent schemas (free-text -> the fields the Planning flow needs)."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class PlanningInterpretIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=500)


class PlanningInterpretOut(BaseModel):
    """Every field is optional on purpose: this is a head start for the flow, not
    a verdict. Whatever comes back null just gets asked for as usual."""

    kind: str                    # buy | subscription | save | other
    item: str | None = None      # what they named, if they named it
    amount: float | None = None  # only ever a number the user actually wrote
    target_date: date | None = None
    missing: list[str] = []      # what the flow still needs to ask for
    source: str = "rules"        # rules | model — which layer filled the gaps
