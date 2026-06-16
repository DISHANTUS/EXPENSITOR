"""Deterministic entity extractors for the NL Action Layer.

Pure regex/grammar — NO LLM. Returns None when unsure (the caller then asks).
Never infers a money value or date that isn't explicitly present.
"""

from __future__ import annotations

import re
from datetime import date, time
from decimal import Decimal, InvalidOperation

_CUR_SYMBOL = {"₹": "INR", "rs": "INR", "rs.": "INR", "inr": "INR", "$": "USD", "€": "EUR", "£": "GBP", "¥": "JPY"}
_MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"], 1)}
_MONTHS.update({m[:3]: i for m, i in list(_MONTHS.items())})
_WEEKDAYS = {d: i for i, d in enumerate(["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"])}

_CURRENCY_AMT = re.compile(r"(₹|rs\.?|inr|\$|€|£|¥)\s*([\d][\d,]*(?:\.\d+)?)\s*(k|lakh|lakhs)?", re.I)
_KEYWORD_AMT = re.compile(
    r"(?:for|of|spend|spent|save|saving|target|give|gave|send|sent|pay|paid|add|added|costs?|worth)\s+"
    r"(?:₹|rs\.?|inr)?\s*([\d][\d,]*(?:\.\d+)?)\s*(k|lakh|lakhs)?", re.I)
_ORDINAL = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)\b", re.I)


def _to_decimal(num: str, mult: str | None) -> Decimal | None:
    try:
        value = Decimal(num.replace(",", ""))
    except InvalidOperation:
        return None
    if mult:
        value *= Decimal("100000") if mult.lower().startswith("lakh") else Decimal("1000")
    return value


def extract_amount(text: str) -> tuple[Decimal | None, str | None]:
    m = _CURRENCY_AMT.search(text)
    if m:
        return _to_decimal(m.group(2), m.group(3)), _CUR_SYMBOL.get(m.group(1).lower(), "INR")
    # avoid matching an ordinal day ("the 7th") as an amount
    for km in _KEYWORD_AMT.finditer(text):
        span = km.span(1)
        if _ORDINAL.search(text[max(0, span[0] - 2):span[1] + 3]):
            continue
        return _to_decimal(km.group(1), km.group(2)), None
    return None, None


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def extract_date(text: str, today: date) -> date | None:
    t = text.lower()
    if re.search(r"\btoday\b|\btonight\b", t):
        return today
    if re.search(r"\btomorrow\b", t):
        return date.fromordinal(today.toordinal() + 1)
    if re.search(r"\byesterday\b", t):
        return date.fromordinal(today.toordinal() - 1)

    iso = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", t)
    if iso:
        return _safe_date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))

    # month + day  OR  day + month
    md = re.search(r"\b(" + "|".join(_MONTHS) + r")\s+(\d{1,2})(?:st|nd|rd|th)?\b", t)
    dm = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(" + "|".join(_MONTHS) + r")\b", t)
    if md or dm:
        month = _MONTHS[(md.group(1) if md else dm.group(2))]
        day = int((md.group(2) if md else dm.group(1)))
        d = _safe_date(today.year, month, day)
        if d and d < today:
            d = _safe_date(today.year + 1, month, day)
        return d

    nxt = re.search(r"next\s+(" + "|".join(_WEEKDAYS) + r")", t)
    if nxt:
        delta = (_WEEKDAYS[nxt.group(1)] - today.weekday()) % 7 or 7
        return date.fromordinal(today.toordinal() + delta)

    # bare ordinal day-of-month ("the 7th", "on the 20th")
    ordm = re.search(r"\b(?:the\s+)?(\d{1,2})(?:st|nd|rd|th)\b", t)
    if ordm:
        day = int(ordm.group(1))
        d = _safe_date(today.year, today.month, day)
        if d and d < today:
            nm = today.month % 12 + 1
            ny = today.year + (1 if nm == 1 else 0)
            d = _safe_date(ny, nm, day)
        return d
    return None


def _window_for(hour: int) -> str:
    if 5 <= hour <= 11:
        return "morning"
    if 12 <= hour <= 16:
        return "afternoon"
    if 17 <= hour <= 20:
        return "evening"
    return "night"


def extract_time(text: str) -> tuple[str | None, time | None]:
    t = text.lower()
    if "noon" in t:
        return "afternoon", time(12, 0)
    if "midnight" in t:
        return "night", time(0, 0)
    exact = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", t) or re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", t)
    if exact:
        groups = exact.groups()
        hour = int(groups[0])
        minute = int(groups[1]) if groups[1] else 0
        if len(groups) == 3 and groups[2]:  # am/pm form
            if groups[2] == "pm" and hour != 12:
                hour += 12
            elif groups[2] == "am" and hour == 12:
                hour = 0
        if 0 <= hour <= 23:
            return _window_for(hour), time(hour, minute)
    for w in ("morning", "afternoon", "evening", "night"):
        if re.search(rf"\b{w}\b", t):
            return w, None
    return None, None


_CATEGORY_KEYWORDS = {
    "lunch": "Food & Dining", "dinner": "Food & Dining", "breakfast": "Food & Dining", "food": "Food & Dining",
    "restaurant": "Food & Dining", "snack": "Food & Dining", "coffee": "Food & Dining",
    "cab": "Transportation", "uber": "Transportation", "taxi": "Transportation", "fuel": "Transportation",
    "petrol": "Transportation", "bus": "Transportation", "train": "Transportation",
    "rent": "Rent & Housing", "movie": "Entertainment", "game": "Entertainment", "concert": "Entertainment",
    "shopping": "Shopping", "clothes": "Shopping", "grocery": "Groceries", "groceries": "Groceries",
    "medicine": "Health & Medical", "doctor": "Health & Medical", "subscription": "Subscriptions",
}


def extract_category(text: str, valid_names: set[str]) -> str | None:
    t = text.lower()
    for kw, name in _CATEGORY_KEYWORDS.items():
        if re.search(rf"\b{kw}\b", t) and name in valid_names:
            return name
    return None


_RELATIONS = {"father": "family", "dad": "family", "mother": "family", "mom": "family",
              "brother": "family", "sister": "family", "family": "family", "salary": "salary"}


def extract_source(text: str) -> tuple[str | None, str | None]:
    """Return (source_name, source_type) for receivable-style inflows."""
    m = re.search(r"\b(\w+)\s+(?:will\s+)?(?:give|gave|send|sent|pay|paid|transfer|owes?)\b", text, re.I)
    poss = re.search(r"\b(\w+)'s\b", text)
    token = (m.group(1) if m else (poss.group(1) if poss else None))
    if not token:
        return None, None
    low = token.lower()
    if low in _RELATIONS:
        return token.capitalize(), _RELATIONS[low]
    if low in ("salary", "freelance", "refund"):
        return token.capitalize(), low
    return token.capitalize(), "friend"


def extract_reason_context(text: str) -> str | None:
    m = re.search(r"\b(?:because|since|as)\b\s+(.*)$", text, re.I)
    return m.group(1).strip().rstrip(".") if m else None
