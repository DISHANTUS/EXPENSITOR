"""Forecast accuracy (Sprint 4b-5b, pure).

Judges a stored forecast snapshot against what actually happened, so the
companion knows how reliable its own predictions have been — broken down by
forecast type (req 7), since goal ETAs and life-event calls have different
reliabilities.
"""

from __future__ import annotations

from dataclasses import dataclass

ACCURATE, PARTIAL, INACCURATE, PENDING = "accurate", "partial", "inaccurate", "pending"

# forecast types (stored on the advice snapshot).
GOAL_ETA, SAVINGS, SUBSCRIPTION, LIFE_EVENT, LOAN = (
    "goal_eta", "savings", "subscription", "life_event", "loan")

_ACCURATE_TOL = 0.10
_PARTIAL_TOL = 0.30


def band(expected: float, actual: float, *, elapsed_months: float) -> str:
    """Compare predicted vs actual progress. PENDING until there's enough signal."""
    if elapsed_months < 1 or expected <= 0:
        return PENDING
    deviation = abs(actual - expected) / expected
    if deviation <= _ACCURATE_TOL:
        return ACCURATE
    if deviation <= _PARTIAL_TOL:
        return PARTIAL
    return INACCURATE


@dataclass(frozen=True)
class AccuracySummary:
    tracked: int
    accurate: int
    partial: int
    inaccurate: int
    pending: int
    by_type: dict[str, dict[str, int]]
    note: str

    def as_dict(self) -> dict:
        return {
            "tracked": self.tracked, "accurate": self.accurate, "partial": self.partial,
            "inaccurate": self.inaccurate, "pending": self.pending, "by_type": self.by_type, "note": self.note,
        }


def summarize(items: list[dict]) -> AccuracySummary:
    """items: [{band, forecast_type}]. Pending items count toward `tracked` but
    not toward the judged bands."""
    counts = {ACCURATE: 0, PARTIAL: 0, INACCURATE: 0, PENDING: 0}
    by_type: dict[str, dict[str, int]] = {}
    for it in items:
        b = it.get("band", PENDING)
        ftype = it.get("forecast_type", GOAL_ETA)
        counts[b] = counts.get(b, 0) + 1
        bucket = by_type.setdefault(ftype, {ACCURATE: 0, PARTIAL: 0, INACCURATE: 0, PENDING: 0})
        bucket[b] = bucket.get(b, 0) + 1

    judged = counts[ACCURATE] + counts[PARTIAL] + counts[INACCURATE]
    if judged == 0:
        note = "Not enough resolved forecasts yet to judge my accuracy — still learning."
    else:
        note = (f"Of {judged} resolved forecast(s), {counts[ACCURATE]} were accurate, "
                f"{counts[PARTIAL]} partly, {counts[INACCURATE]} off.")
    return AccuracySummary(
        tracked=len(items), accurate=counts[ACCURATE], partial=counts[PARTIAL],
        inaccurate=counts[INACCURATE], pending=counts[PENDING], by_type=by_type, note=note,
    )
