"""Life Timeline builder (Sprint 6a, pure/deterministic).

Folds already-gathered life events (achievements, goals, loans, occasions,
lessons, forecasts) into ONE chronological story: deduped, sorted, split into
past / present / future, and grouped into chapters by year. No DB, no LLM —
the service hands it structured entries; this just arranges them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

PAST, PRESENT, FUTURE = "past", "present", "future"
_RANK = {"life_milestone": 3, "high": 2, "medium": 1, "low": 0}


@dataclass
class Entry:
    date: date | None
    title: str
    detail: str = ""
    kind: str = "event"            # achievement | goal | loan | event | lesson | income | life_event | forecast
    importance: str = "medium"     # life_milestone | high | medium | low
    when: str = PAST               # past | present | future
    icon: str = "•"
    person: str | None = None      # who this involves (7: relationships + search)


@dataclass
class Chapter:
    label: str                     # chapter title (e.g. "Japan Preparation") or year
    entries: list[Entry] = field(default_factory=list)
    subtitle: str = ""


@dataclass
class Timeline:
    chapters: list[Chapter]
    past_count: int
    present_count: int
    future_count: int
    headline: str


def _eff(e: Entry, today: date) -> date:
    return e.date or today


def prepare(entries: list[Entry], *, today: date) -> list[Entry]:
    """Sort chronologically + dedup (same milestone from two sources → once)."""
    ordered = sorted(entries, key=lambda e: (_eff(e, today), -_RANK.get(e.importance, 1)))
    seen: set[tuple[str, int]] = set()
    uniq: list[Entry] = []
    for e in ordered:
        key = (e.title.strip().lower(), _eff(e, today).year)
        if key in seen:
            continue
        seen.add(key)
        uniq.append(e)
    return uniq


def build(entries: list[Entry], *, today: date, grouper=None) -> Timeline:
    """Group into chapters. `grouper(uniq) -> [(title, subtitle, entries)]` (e.g.
    deterministic life chapters); falls back to year grouping when not given."""
    uniq = prepare(entries, today=today)

    chapters: list[Chapter] = []
    if grouper is not None:
        for title, subtitle, es in grouper(uniq):
            chapters.append(Chapter(label=title, subtitle=subtitle, entries=es))
    else:
        for e in uniq:
            yr = str(_eff(e, today).year)
            if not chapters or chapters[-1].label != yr:
                chapters.append(Chapter(label=yr))
            chapters[-1].entries.append(e)

    past = sum(1 for e in uniq if e.when == PAST)
    present = sum(1 for e in uniq if e.when == PRESENT)
    future = sum(1 for e in uniq if e.when == FUTURE)

    if not uniq:
        headline = "Your story starts here — add income, goals and events and I’ll remember them."
    else:
        tail = f", {future} ahead." if future else "."
        chap = "chapter" if past == 1 else "chapters"
        headline = f"Here’s your story so far — {past} {chap} behind you{tail}"
    return Timeline(chapters, past, present, future, headline)
