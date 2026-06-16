"""Advisor tone guard.

The advisor is a coach, never a judge. This lints generated strings for
judgmental language. Used in tests and as a render-time safety net; it will also
constrain future Ollama narration (which may only rephrase, never re-judge).
"""

from __future__ import annotations

import re

# Phrases the advisor must never emit. Trade-offs/consequences are stated neutrally.
BANNED_TERMS: tuple[str, ...] = (
    "bad decision", "bad idea", "wasteful", "waste of", "you wasted", "stupid",
    "unnecessary", "too expensive", "overpriced", "cheaper", "don't buy",
    "do not buy", "shouldn't buy", "should not buy", "wrong decision", "irresponsible",
    "reckless", "foolish",
)

_PATTERN = re.compile("|".join(re.escape(term) for term in BANNED_TERMS), re.IGNORECASE)


def lint(text: str) -> list[str]:
    """Return the banned phrases found in ``text`` (empty list = clean)."""
    return [m.group(0).lower() for m in _PATTERN.finditer(text or "")]


def is_clean(*texts: str | None) -> bool:
    return all(not lint(t or "") for t in texts)
