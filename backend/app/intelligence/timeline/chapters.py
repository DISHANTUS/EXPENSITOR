"""Life chapters (Sprint 7, pure/deterministic — NOT AI-generated).

Groups a chronological list of timeline entries into named life chapters using
deterministic anchors (keywords/kinds), so the user gets something emotional to
look back on without any hallucinated stories. Entries flow into the current
chapter until a stronger anchor opens the next one.
"""

from __future__ import annotations

from app.intelligence.timeline.builder import Entry

# Ordered boundary anchors: (title, subtitle, keyword matchers). The first entry
# whose title hits a matcher opens that chapter (once).
_ANCHORS: list[tuple[str, str, tuple[str, ...]]] = [
    ("Japan Preparation", "Saving and planning for Japan", ("japan", "jlpt")),
    ("Moving Abroad", "The big move", ("move to", "moving", "relocat", "move abroad")),
    ("Career Growth", "Building your career", ("job", "career", "promotion", "first role", "full-time", "salary milestone")),
    ("Building Stability", "A safety net and steady savings", ("emergency", "stability", "safety net")),
]
_START_TITLE, _START_SUB = "Starting Out", "Your first steps with money"


def _anchor_for(entry: Entry) -> tuple[str, str] | None:
    t = entry.title.lower()
    for title, sub, kws in _ANCHORS:
        if any(kw in t for kw in kws):
            return title, sub
    return None


def assign(entries_sorted: list[Entry]) -> list[tuple[str, str, list[Entry]]]:
    """Group chronological entries into (title, subtitle, entries) chapters.
    Returns plain tuples so the builder can wrap them without an import cycle."""
    chapters: list[tuple[str, str, list[Entry]]] = []
    used: set[str] = set()
    cur_title, cur_sub, cur_entries = _START_TITLE, _START_SUB, []

    for e in entries_sorted:
        anchor = _anchor_for(e)
        if anchor and anchor[0] != cur_title and anchor[0] not in used:
            if cur_entries:
                chapters.append((cur_title, cur_sub, cur_entries))
                used.add(cur_title)
            cur_title, cur_sub, cur_entries = anchor[0], anchor[1], []
        cur_entries.append(e)

    if cur_entries:
        chapters.append((cur_title, cur_sub, cur_entries))
    return chapters
