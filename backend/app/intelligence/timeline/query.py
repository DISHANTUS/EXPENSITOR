"""Memory query engine (Sprint 7, pure/deterministic — NO LLM).

One engine that filters timeline entries by person / period / kind / time-frame.
It powers ALL the memory surfaces with no duplicate code:
  * timeline filter chips         -> filter_by_group
  * search box / voice / advisor  -> parse_query -> filter_entries
  * relationship pages            -> QuerySpec(person=...)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from app.intelligence.timeline.builder import FUTURE, Entry

# Filter chips -> the kinds they show (None = everything; "future" handled by when).
FILTER_GROUPS: dict[str, set[str] | None] = {
    "all": None,
    "finance": {"income", "loan", "goal"},
    "goals": {"goal"},
    "relationships": {"loan", "event"},
    "lessons": {"lesson"},
    "achievements": {"achievement"},
    "future": None,
}

_MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"], 1)}
_MONTHS.update({m[:3]: i for m, i in list(_MONTHS.items())})
_MONTH_RE = re.compile(r"\b(" + "|".join(_MONTHS) + r")[a-z]*\.?\s*(\d{4})?\b")
_YEAR_RE = re.compile(r"\b(20\d{2})\b")
_KIND_HINTS = [
    (("achievement", "milestone", "accomplish", "won", "win"), {"achievement"}),
    (("lesson", "learned", "learnt"), {"lesson"}),
    (("loan", "lent", "owe", "borrow"), {"loan"}),
    (("goal", "saving"), {"goal"}),
    (("relationship", "people", "everyone"), {"loan", "event"}),
]


@dataclass(frozen=True)
class QuerySpec:
    person: str | None = None
    year: int | None = None
    month: int | None = None
    kinds: frozenset[str] | None = None
    when: str | None = None        # FUTURE for "upcoming/ahead"
    earliest: bool = False         # "when did I start …" -> just the first hit
    keyword: str | None = None     # free-text title match ("preparing for Japan")


def parse_query(text: str, *, today: date, known_people: set[str]) -> QuerySpec:
    t = text.lower().strip()

    person: str | None = None
    for name in sorted(known_people, key=len, reverse=True):
        if name and re.search(rf"\b{re.escape(name.lower())}\b", t):
            person = name
            break
    if person is None:
        m = re.search(r"\b(?:involving|with|about|regarding)\s+([a-z][a-z]+)", t)
        if m and m.group(1) not in ("my", "the", "everything", "all"):
            person = m.group(1).capitalize()

    year = month = None
    if (mm := _MONTH_RE.search(t)):
        month = _MONTHS[mm.group(1)]
        year = int(mm.group(2)) if mm.group(2) else today.year
    elif (ym := _YEAR_RE.search(t)):
        year = int(ym.group(1))

    kinds: frozenset[str] | None = None
    for words, ks in _KIND_HINTS:
        if any(w in t for w in words):
            kinds = frozenset(ks)
            break

    when = FUTURE if any(w in t for w in ("future", "upcoming", "ahead", "next")) else None
    earliest = bool(re.search(r"when did i (start|begin)", t)) or "start preparing" in t

    keyword: str | None = None
    kw = re.search(r"(?:preparing for|prepare for|saving for|working towards?|towards?)\s+([a-z][a-z]+)", t)
    if kw and (person is None or kw.group(1).lower() != person.lower()):
        keyword = kw.group(1)
    return QuerySpec(person=person, year=year, month=month, kinds=kinds, when=when,
                     earliest=earliest, keyword=keyword)


def _matches(e: Entry, spec: QuerySpec) -> bool:
    if spec.kinds and e.kind not in spec.kinds:
        return False
    if spec.person:
        p = spec.person.lower()
        if (e.person or "").lower() != p and p not in e.title.lower():
            return False
    if spec.when and e.when != spec.when:
        return False
    if spec.year and (e.date is None or e.date.year != spec.year):
        return False
    if spec.month and (e.date is None or e.date.month != spec.month):
        return False
    if spec.keyword and spec.keyword.lower() not in e.title.lower():
        return False
    return True


def filter_entries(entries: list[Entry], spec: QuerySpec) -> list[Entry]:
    out = [e for e in entries if _matches(e, spec)]
    if spec.earliest and out:
        return [min(out, key=lambda x: x.date or date.max)]
    return out


def filter_by_group(entries: list[Entry], group: str) -> list[Entry]:
    if group == "future":
        return [e for e in entries if e.when == FUTURE]
    kinds = FILTER_GROUPS.get(group)
    if kinds is None:
        return list(entries)
    return [e for e in entries if e.kind in kinds]
