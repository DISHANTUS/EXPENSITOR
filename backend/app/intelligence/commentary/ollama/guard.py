"""Grounding guard (C5 Phase 3b) — aggressive, bidirectional, domain-agnostic.

Validates that a narrated rephrase introduced NOTHING new and dropped NO required
fact, across: numbers, money, percentages, dates, times, entity names, paragraph
count, ordered-list order+count, severity wording, and confidence wording.

If anything fails the deterministic text is authoritative and the caller must fall
back. The guard is pure and language-token based (multilingual markers are isolated
in `markers`-style constants so other languages can be added later without redesign).
The narrator passes a `GroundingSpec`; the guard never sees raw DB data.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.intelligence.advisor import tone

# --- token extraction -------------------------------------------------------
_MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
_MONTHS_FULL = ["january", "february", "march", "april", "may", "june", "july", "august",
                "september", "october", "november", "december"]
_MONTH_NUM = {m: i for i, m in enumerate(_MONTHS, start=1)}
_MONTH_NUM.update({m: i for i, m in enumerate(_MONTHS_FULL, start=1)})

_MONEY_RE = re.compile(r"(?:₹|\$|€|£|¥|Kč)\s?([\d,]+(?:\.\d+)?)")
_CUR_RE = re.compile(r"\b([A-Z]{3})\s([\d,]+(?:\.\d+)?)\b")
_PERCENT_RE = re.compile(r"(\d+(?:\.\d+)?)\s?%")
_ISO_RE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_MONTHDAY_RE = re.compile(r"\b([A-Za-z]{3,9})\s+(\d{1,2})(?:st|nd|rd|th)?\b")
_TIME12_RE = re.compile(r"\b(\d{1,2})(?::(\d{2}))?\s?([AaPp][Mm])\b")
_TIME24_RE = re.compile(r"\b(\d{1,2}):(\d{2})\b")
_NOON_RE = re.compile(r"\b(noon|midnight)\b", re.IGNORECASE)
_NUMBER_RE = re.compile(r"\b(\d[\d,]*(?:\.\d+)?)\b")
_CAP_RE = re.compile(r"\b([A-Z][A-Za-z&]+)\b")

# Capitalised words that are NOT entities (sentence starts / common words / months).
_CAP_ALLOWLIST = {
    "i", "you", "your", "youre", "it", "its", "this", "that", "the", "a", "an", "and", "but", "if",
    "so", "to", "for", "of", "on", "in", "with", "without", "small", "steady", "about", "heads", "up",
    "unchanged", "based", "because", "here", "your", "there", "no", "yes", "keep", "keeping", "trim",
    "trimming", "expected", "next", "amount", "done", "moving", "move", "add", "set", "track", "mark",
    "watch", "consider", "only", "still", "now", "soon", "today", "tomorrow", "yesterday", "week",
    "month", "monthly", "daily", "weekly", "left", "spend", "spending", "income", "savings", "goal",
    "plan", "plans", "budget", "risk", "read", "reaching", "reduce", "reductions", "money", "evening",
    "morning", "afternoon", "night", "salary", "father", "mother", "am", "pm", "first", "then", "finally",
}
_CAP_ALLOWLIST |= set(_MONTHS) | set(_MONTHS_FULL)

# Wording markers (English; isolated for future multilingual swap).
_HEDGE_RE = re.compile(
    r"limited history|enough history|still forming|based on limited|one month of data",
    re.IGNORECASE,
)
_ESCALATION_MARKERS = (
    "critical", "urgent", "emergency", "crisis", "danger", "overdrawn", "insolvent",
    "shortfall", "overdue", "at risk", "alarm", "severe",
)

_CATEGORIES = ("money", "percent", "date", "time", "number")


def extract_facts(text: str) -> dict[str, set]:
    """Pull every fact-bearing token from free text, normalised for comparison."""
    text = text or ""
    money: set[str] = {_norm_amt(m.group(1)) for m in _MONEY_RE.finditer(text)}
    money |= {_norm_amt(m.group(2)) for m in _CUR_RE.finditer(text)}
    percent = {_norm_amt(m.group(1)) for m in _PERCENT_RE.finditer(text)}
    dates: set[tuple[int, int]] = {(int(m.group(2)), int(m.group(3))) for m in _ISO_RE.finditer(text)}
    for m in _MONTHDAY_RE.finditer(text):
        mo = _MONTH_NUM.get(m.group(1).lower())
        if mo:
            dates.add((mo, int(m.group(2))))
    times: set[str] = set()
    for m in _TIME12_RE.finditer(text):
        hour = int(m.group(1)) % 12 + (12 if m.group(3).lower() == "pm" else 0)
        times.add(f"{hour:02d}:{int(m.group(2) or 0):02d}")
    for m in _TIME24_RE.finditer(text):
        times.add(f"{int(m.group(1)):02d}:{int(m.group(2)):02d}")
    for m in _NOON_RE.finditer(text):
        times.add("12:00" if m.group(1).lower() == "noon" else "00:00")
    # numbers: strip the spans already classified, so dates/money/times don't leak in
    work = text
    for rx in (_MONEY_RE, _CUR_RE, _PERCENT_RE, _ISO_RE, _TIME12_RE, _TIME24_RE):
        work = rx.sub(" ", work)
    # Only strip REAL month-day spans ("Jun 7"); keep "Your 12-day" so its number
    # ("12") stays grounded — otherwise a streak/count could be altered undetected.
    work = _MONTHDAY_RE.sub(lambda m: " " if _MONTH_NUM.get(m.group(1).lower()) else m.group(0), work)
    numbers = {_norm_amt(m.group(1)) for m in _NUMBER_RE.finditer(work)}
    caps = {m.group(1) for m in _CAP_RE.finditer(text)}
    return {"money": money, "percent": percent, "date": dates, "time": times,
            "number": numbers, "caps": caps}


def _norm_amt(raw: str) -> str:
    value = raw.replace(",", "")
    try:
        dec = float(value)
        return str(int(dec)) if dec == int(dec) else str(dec)
    except ValueError:
        return value


def escalation_markers(text: str) -> set[str]:
    low = (text or "").lower()
    return {m for m in _ESCALATION_MARKERS if m in low}


# --- spec + result ----------------------------------------------------------
@dataclass(frozen=True)
class GroundingSpec:
    """Everything the guard needs — domain-agnostic, so reminders / alerts /
    notifications can reuse it without commentary-specific assumptions."""

    allowed: dict[str, set] = field(default_factory=dict)        # facts the narration MAY contain
    required: dict[str, set] = field(default_factory=dict)       # facts the narration MUST keep
    grounding_tokens: tuple[str, ...] = ()
    escalation_markers: set[str] = field(default_factory=set)
    confidence_hedged: bool = False
    paragraph_count: int = 1
    ordered_items: tuple[str, ...] = ()                          # list items that must keep order+count
    severity: str = "info"
    version: str = "1.0"
    # Greetings (4c-B2) are casual prose: allow new non-fact words ("Hey", "Nice")
    # while money/number/date/percent/time stay strictly grounded both ways.
    allow_new_entities: bool = False
    # Greetings span several short sentences; the model may re-flow line breaks.
    # Facts still matter, paragraph structure doesn't — so allow opting out.
    enforce_paragraph_count: bool = True


@dataclass(frozen=True)
class GuardResult:
    ok: bool
    reason: str = ""
    offending_tokens: tuple[str, ...] = ()


def _split_paragraphs(text: str) -> list[str]:
    return [p for p in re.split(r"\n\s*\n", (text or "").strip()) if p.strip()]


def _ordered_ok(text: str, items: tuple[str, ...]) -> bool:
    """Each item must appear, in order, exactly once (case-insensitive)."""
    low = (text or "").lower()
    cursor = 0
    for item in items:
        idx = low.find(item.lower(), cursor)
        if idx < 0:
            return False
        if low.count(item.lower()) != 1:
            return False
        cursor = idx + len(item)
    return True


def validate(narrated_text: str, spec: GroundingSpec) -> GuardResult:
    """Aggressive bidirectional check. Any mismatch -> not ok (caller falls back)."""
    text = (narrated_text or "").strip()
    if not text:
        return GuardResult(False, "empty")

    paras = _split_paragraphs(text)
    if spec.enforce_paragraph_count and len(paras) != spec.paragraph_count:
        return GuardResult(False, "paragraph_count", (f"{len(paras)}!={spec.paragraph_count}",))

    nf = extract_facts(text)

    # (a) no additions
    for cat in _CATEGORIES:
        extra = nf[cat] - spec.allowed.get(cat, set())
        if extra:
            return GuardResult(False, f"added_{cat}", tuple(sorted(str(x) for x in extra)))
    if not spec.allow_new_entities:
        extra_caps = {c for c in nf["caps"] if c.lower() not in _CAP_ALLOWLIST} - spec.allowed.get("caps", set())
        if extra_caps:
            return GuardResult(False, "added_entity", tuple(sorted(extra_caps)))

    # (b) no removals of required facts (warnings / risk figures / key numbers)
    for cat in _CATEGORIES:
        missing = spec.required.get(cat, set()) - nf[cat]
        if missing:
            return GuardResult(False, f"dropped_{cat}", tuple(sorted(str(x) for x in missing)))

    # (c) confidence wording preserved exactly (can't add OR remove a hedge)
    if bool(_HEDGE_RE.search(text)) != spec.confidence_hedged:
        return GuardResult(False, "confidence_mismatch",
                           ("hedge_added" if not spec.confidence_hedged else "hedge_removed",))

    # (d) severity wording: no invented alarm
    new_alarm = escalation_markers(text) - spec.escalation_markers
    if new_alarm:
        return GuardResult(False, "severity_escalation", tuple(sorted(new_alarm)))

    # (e) ordered list (generic; () for commentary) — order + count preserved
    if spec.ordered_items and not _ordered_ok(text, spec.ordered_items):
        return GuardResult(False, "ordering", spec.ordered_items)

    # (f) tone net
    banned = tone.lint(text)
    if banned:
        return GuardResult(False, "tone", tuple(banned))

    return GuardResult(True)


def paragraphs_of(text: str) -> tuple[str, ...]:
    return tuple(_split_paragraphs(text))
