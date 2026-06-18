"""Conversational life-change parser (Budget Intelligence System — Phase 5A).

Turns "I moved to Tokyo and now pay ¥80,000 rent" into structured profile/income
changes. Deterministic (no LLM). Distinguishes "I moved" (now) from "I'm moving …
next year" (future). The caller previews these before applying — nothing changes
without confirmation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal


@dataclass
class Change:
    target: str            # "profile" | "income_add" | "income_remove" | "future_move"
    field: str             # profile field, or income source_type
    value: object          # value to set (str/Decimal/int/None)
    label: str             # human-readable: "Country → Japan"
    extra: dict = field(default_factory=dict)


_CITY = {
    "tokyo": ("JP", "Tokyo"), "osaka": ("JP", "Osaka"), "kyoto": ("JP", "Kyoto"),
    "chennai": ("IN", "Chennai"), "mumbai": ("IN", "Mumbai"), "delhi": ("IN", "Delhi"),
    "bangalore": ("IN", "Bangalore"), "bengaluru": ("IN", "Bengaluru"), "pune": ("IN", "Pune"),
    "london": ("GB", "London"), "new york": ("US", "New York"),
}
_COUNTRY = {
    "japan": "JP", "india": "IN", "uk": "GB", "united kingdom": "GB", "britain": "GB",
    "usa": "US", "us": "US", "united states": "US", "america": "US",
}
_COUNTRY_NAME = {"JP": "Japan", "IN": "India", "GB": "the UK", "US": "the US"}


def _amount(segment: str) -> Decimal | None:
    m = re.search(r"(?:¥|₹|rs\.?|inr|jpy|usd|gbp|\$|£)?\s*([\d][\d,]*(?:\.\d+)?)\s*(k|thousand|lakh)?", segment, re.I)
    if not m:
        return None
    val = Decimal(m.group(1).replace(",", ""))
    suffix = (m.group(2) or "").lower()
    if suffix in ("k", "thousand"):
        val *= 1000
    elif suffix == "lakh":
        val *= 100000
    return val


def _resolve_place(name: str) -> tuple[str | None, str | None]:
    n = name.strip().lower().strip(".")
    if n in _CITY:
        return _CITY[n]
    if n in _COUNTRY:
        return _COUNTRY[n], None
    # "tokyo, japan" → take the city.
    for city, (cc, label) in _CITY.items():
        if city in n:
            return cc, label
    for country, cc in _COUNTRY.items():
        if country in n:
            return cc, None
    return None, None


def parse(text: str, today: date) -> list[Change]:
    t = " " + text.lower().strip() + " "
    changes: list[Change] = []

    # --- Moves (now vs future) ---
    move = re.search(r"\b(?:move[d]? to|moving to|relocat(?:ed|ing) to|now (?:in|living in)|i'?m (?:in|living in))\s+([a-z][a-z .]+?)(?=\s+(?:next|in 20|by|now|and|,|\.| this | last )|\s*$)", t)
    if move:
        cc, city = _resolve_place(move.group(1))
        if cc:
            is_future = bool(re.search(r"\b(will move|moving to|plan(?:ning)? to move|next year|next month|going to move)", t)) and "moved to" not in t
            if is_future:
                year = None
                ym = re.search(r"\b(20\d{2})\b", t)
                if ym:
                    year = int(ym.group(1))
                elif "next year" in t:
                    year = today.year + 1
                changes.append(Change("future_move", "future_country", cc,
                                      f"Future move → {_COUNTRY_NAME.get(cc, cc)}" + (f" in {year}" if year else ""),
                                      extra={"year": year}))
            else:
                changes.append(Change("profile", "current_country", cc, f"Country → {_COUNTRY_NAME.get(cc, cc)}"))
                if city:
                    changes.append(Change("profile", "current_city", city, f"City → {city}"))

    # --- Rent ---
    rent = re.search(r"rent(?:\s+\w+){0,3}?\s+(?:to|of|is now|now)\s+([¥₹$£]?\s*[\d][\d,]*\s*k?)", t) \
        or re.search(r"(?:pay|paying)\s+([¥₹$£]?\s*[\d][\d,]*\s*k?)\s+(?:in |for )?rent", t)
    if rent:
        amt = _amount(rent.group(1))
        if amt is not None:
            changes.append(Change("profile", "rent_monthly", amt, f"Rent → {amt:,.0f}/month"))

    # --- Living situation ---
    if re.search(r"\b(?:girlfriend|boyfriend|partner|gf|bf|spouse|wife|husband)\b", t):
        changes.append(Change("profile", "living_situation", "with_partner", "Living with → partner"))
    elif re.search(r"\b(?:living alone|on my own|by myself)\b", t):
        changes.append(Change("profile", "living_situation", "alone", "Living → alone"))
    elif re.search(r"\b(?:with (?:my )?parents|back home|with family)\b", t):
        changes.append(Change("profile", "living_situation", "with_parents", "Living with → parents"))
    elif re.search(r"\b(?:with (?:my )?friends|roommate|flatmate|shared apartment)\b", t):
        changes.append(Change("profile", "living_situation", "with_friends", "Living with → friends"))
    elif re.search(r"\b(?:dorm|dormitory|hostel)\b", t):
        changes.append(Change("profile", "living_situation", "dormitory", "Living in → dorm"))

    # --- Food situation ---
    if re.search(r"\b(?:cook(?:ing)? at home|started cooking|home ?cooked|cook my own)\b", t):
        changes.append(Change("profile", "food_situation", "home_cooked", "Food → home cooked"))
    elif re.search(r"\b(?:eating out(?:side)? more|eat out more|mostly outside|order(?:ing)? (?:food|out) more)\b", t):
        changes.append(Change("profile", "food_situation", "mostly_outside", "Food → mostly outside"))

    # --- Income changes ---
    if re.search(r"\b(?:part[- ]?time|started working|got a job)\b", t):
        amt = None
        m = re.search(r"(?:earning|earn|makes?|making|paying|of|for)\s+([¥₹$£]?\s*[\d][\d,]*\s*k?)", t)
        if m:
            amt = _amount(m.group(1))
        changes.append(Change("income_add", "part_time", amt,
                              "Add income: part-time" + (f" ({amt:,.0f}/month)" if amt else " (amount?)")))
    if re.search(r"\b(?:mext|scholarship|stipend)\b", t) and "lost" not in t and "stopped" not in t:
        amt = None
        m = re.search(r"(?:of|earning|worth|gives?|is)\s+([¥₹$£]?\s*[\d][\d,]*\s*k?)", t)
        if m:
            amt = _amount(m.group(1))
        changes.append(Change("income_add", "scholarship", amt,
                              "Add income: scholarship" + (f" ({amt:,.0f}/month)" if amt else " (amount?)")))
    if re.search(r"\b(?:father|dad|family|parents?|mom|mother)\b.*\b(?:stopped|no longer|stop)\b", t) \
            or re.search(r"\bstopped sending (?:me )?money\b", t):
        changes.append(Change("income_remove", "family_support", None, "Remove income: family support"))

    return changes
