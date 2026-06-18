"""Life-lesson intelligence (Sprint 4b-5b, pure/deterministic).

Categorises a USER-TAUGHT lesson, grows confidence with repetition, advances the
lifecycle, and matches stored lessons to the user's current context. No LLM — the
category comes from a keyword map, never an inference.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

# category -> trigger keywords (extends the Phase-E circumstance vocabulary).
LESSON_CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "emergency_fund": ("laptop", "broke", "broken", "repair", "emergency", "unexpected", "surprise",
                       "medical", "hospital", "sudden", "accident", "phone died", "device"),
    "lending": ("lent", "loan", "borrow", "repay", "owe", "friend paid", "didn't pay back", "didn’t pay back"),
    "subscriptions": ("subscription", "netflix", "spotify", "renew", "auto-renew", "membership"),
    "food": ("food", "eating out", "restaurant", "takeout", "delivery", "ordered in"),
    "travel": ("travel", "trip", "vacation", "flight", "holiday"),
    "impulse": ("impulse", "sale", "offer", "discount", "deal", "bought on a whim"),
    "income_timing": ("salary delay", "paid late", "income was late", "delayed income"),
}
_DEFAULT_CATEGORY = "general"

_HIGH_CATEGORIES = {"emergency_fund", "lending", "income_timing"}
_MEDIUM_CATEGORIES = {"subscriptions", "food", "travel", "impulse"}

ARCHIVE_AFTER_DAYS = 540   # ~18 months without recurrence -> archived (never deleted)

# statuses + confidence mirror the enums (kept as strings to stay import-light).
ACTIVE, CONFIRMED, ARCHIVED, FORGOTTEN = "active", "confirmed", "archived", "forgotten"
LOW, MEDIUM, HIGH = "low", "medium", "high"


@dataclass(frozen=True)
class LessonDraft:
    category: str
    importance: str
    canonical: str       # a normalised, surfacing-friendly statement


def classify_category(text: str) -> str:
    low = (text or "").lower()
    for category, keywords in LESSON_CATEGORY_KEYWORDS.items():
        if any(kw in low for kw in keywords):
            return category
    return _DEFAULT_CATEGORY


def importance_for(category: str) -> str:
    if category in _HIGH_CATEGORIES:
        return "high"
    if category in _MEDIUM_CATEGORIES:
        return "medium"
    return "medium"


_CANONICAL = {
    "emergency_fund": "Unexpected expenses have disrupted your plans before — an emergency buffer may help.",
    "lending": "Money you’ve lent out has affected your plans before — settle dues before lending again.",
    "subscriptions": "Subscriptions have crept up on you before — worth reviewing them periodically.",
    "food": "Food spending has pushed you over before — worth watching around busy weeks.",
    "travel": "Travel has strained your budget before — worth planning a buffer ahead of trips.",
    "impulse": "Offers and sales have tempted you before — a pause before buying tends to help.",
    "income_timing": "Late income has thrown off your plans before — a small buffer smooths it out.",
}


def canonical_lesson(category: str, source_text: str) -> str:
    return _CANONICAL.get(category, source_text.strip())


def make_draft(source_text: str) -> LessonDraft:
    category = classify_category(source_text)
    return LessonDraft(category=category, importance=importance_for(category),
                       canonical=canonical_lesson(category, source_text))


def confidence_for(occurrences: int) -> str:
    if occurrences >= 5:
        return HIGH
    if occurrences >= 2:
        return MEDIUM
    return LOW


def status_for(occurrences: int, last_observed: date, today: date, *, current: str) -> str:
    """Compute the lifecycle state. `forgotten` is sticky (user-controlled)."""
    if current == FORGOTTEN:
        return FORGOTTEN
    if (today - last_observed).days > ARCHIVE_AFTER_DAYS:
        return ARCHIVED
    return CONFIRMED if occurrences >= 2 else ACTIVE


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower().strip())


def surfaceable(status: str, confidence: str) -> bool:
    """Only CONFIRMED (>=2 occurrences) lessons are volunteered proactively —
    so the companion never overlearns from a single event."""
    return status == CONFIRMED and confidence in (MEDIUM, HIGH)


def context_terms(*parts: str) -> set[str]:
    terms: set[str] = set()
    for p in parts:
        terms |= set(re.findall(r"[a-z]+", (p or "").lower()))
    return terms


def matches_context(category: str, trigger_context: str | None, terms: set[str]) -> bool:
    if category in terms:
        return True
    kws = LESSON_CATEGORY_KEYWORDS.get(category, ())
    if any(any(w in t for t in terms) for w in (kw.split()[0] for kw in kws)):
        return True
    if trigger_context and trigger_context.lower() in terms:
        return True
    return False
