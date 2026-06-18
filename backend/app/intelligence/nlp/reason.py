"""Deterministic reason interpreter (NO LLM).

Turns the user's own words into a short label + multi-tags + a confidence,
WITHOUT discarding the original text (the caller stores both). The label is only
an interpretation layer; the user's wording stays the source of truth.
"""

from __future__ import annotations

import re

_TAG_KEYWORDS: dict[str, tuple[str, ...]] = {
    "japan": ("japan", "japanese", "tokyo", "osaka"),
    "jlpt": ("jlpt", "n5", "n4", "n3", "n2", "n1"),
    "education": ("exam", "college", "university", "course", "study", "masters",
                  "degree", "tuition", "scholarship", "school", "semester"),
    "travel": ("trip", "travel", "flight", "ticket", "tickets", "vacation", "journey", "tour"),
    "family": ("dad", "father", "mom", "mother", "amma", "appa", "family", "parents",
               "brother", "sister", "uncle", "aunt"),
    "medical": ("hospital", "doctor", "medicine", "medical", "health", "surgery", "pharmacy"),
    "emergency": ("emergency", "urgent", "urgently"),
    "gift": ("gift", "present", "birthday", "anniversary"),
    "work": ("job", "salary", "work", "office", "freelance", "client", "project"),
    "savings": ("save", "saving", "savings", "fund", "goal"),
    "vehicle": ("bike", "car", "vehicle", "repair", "scooter"),
    "food": ("lunch", "dinner", "food", "restaurant", "groceries"),
    "rent": ("rent", "deposit", "landlord"),
}

# Label priority (first matching tag wins) → human-readable label.
_PRIORITY: tuple[tuple[str, str], ...] = (
    ("jlpt", "JLPT"), ("japan", "Japan plan"), ("education", "Education"),
    ("travel", "Travel"), ("medical", "Medical"), ("emergency", "Emergency"),
    ("family", "Family support"), ("vehicle", "Vehicle"), ("gift", "Gift"),
    ("rent", "Rent"), ("food", "Food"), ("work", "Work income"), ("savings", "Savings"),
)

_VAGUE = {"", "personal", "personal reason", "other", "private", "na", "n/a", "none", "idk"}


def interpret(text: str) -> dict:
    original = (text or "").strip()
    t = original.lower()
    tags = [tag for tag, kws in _TAG_KEYWORDS.items()
            if any(re.search(rf"\b{re.escape(k)}\b", t) for k in kws)]

    label: str | None = None
    for tag, display in _PRIORITY:
        if tag in tags:
            label = display
            break
    if label is None and original:
        label = " ".join(original.split()[:4]).title()
    if not label:
        label = "Note"

    words = original.split()
    needs_more = (t in _VAGUE) or (len(words) < 2 and not tags)
    confidence = 0.9 if tags else (0.5 if len(words) >= 4 else 0.3)

    return {
        "original": original,
        "label": label,
        "tags": tags,
        "confidence": round(confidence, 2),
        "needs_more": needs_more,
    }
