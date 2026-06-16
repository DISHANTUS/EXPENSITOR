"""Outcome layer — shared constants, circumstance classifier (E7), decay (mod 5),
trust banding (mod 4). Pure + deterministic; no ML."""

from __future__ import annotations

from datetime import date

# kinds
DECISION, RECOMMENDATION, GOAL, PLAN = "decision", "recommendation", "goal", "plan"
# statuses
SUCCESS, PARTIAL, FAILED, ABANDONED = "success", "partial", "failed", "abandoned"
AHEAD, ON_TRACK, BEHIND, MISSED, UNKNOWN = "ahead", "on_track", "behind", "missed", "unknown"
# sources
DERIVED, USER_REPORTED = "derived", "user_reported"

# E7 — circumstance reasons are external interference, NOT lever failure.
CIRCUMSTANCE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "unexpected_expense": ("unexpected expense", "unexpected", "surprise expense"),
    "medical": ("medical", "hospital", "illness", "health emergency", "doctor"),
    "travel": ("travel", "trip", "vacation", "holiday"),
    "family_event": ("family event", "wedding", "funeral", "family emergency"),
    "income_delay": ("income delay", "delayed income", "salary delay", "paid late", "late payment", "income was late"),
    "one_time_emergency": ("emergency", "one-time", "one time", "one-off", "exceptional"),
}


def classify_circumstance(reason: str | None) -> str | None:
    """Map an outcome reason to a circumstance type (or None = genuine to the lever)."""
    if not reason:
        return None
    low = reason.lower()
    for ctype, keywords in CIRCUMSTANCE_KEYWORDS.items():
        if any(kw in low for kw in keywords):
            return ctype
    return None


def age_months(evaluated_on: date, today: date) -> int:
    return max(0, (today.year - evaluated_on.year) * 12 + (today.month - evaluated_on.month))


def decay_weight(months: int) -> float:
    """Deterministic recency weighting — recent outcomes matter more (mod 5)."""
    if months <= 1:
        return 1.0
    if months <= 3:
        return 0.75
    if months <= 6:
        return 0.5
    if months <= 12:
        return 0.35
    return 0.25


def trust_level(evidence_count: int) -> str:
    return "high" if evidence_count >= 8 else "medium" if evidence_count >= 3 else "low"
