"""Proactive ranking — order by priority so the most important thing is first.

Dedupes to one item per (kind, category), keeping the highest priority, so the
feed surfaces the single most important thing rather than near-duplicates.
"""

from __future__ import annotations

from app.intelligence.proactive.item import ProactiveItem

_SEVERITY = {"alert": 0, "warning": 1, "success": 2, "info": 3}


def rank(items: list[ProactiveItem]) -> list[ProactiveItem]:
    best: dict[tuple[str, str], ProactiveItem] = {}
    for it in items:
        key = (it.kind, it.category)
        if key not in best or it.priority > best[key].priority:
            best[key] = it
    return sorted(best.values(), key=lambda i: (-i.priority, _SEVERITY.get(i.severity, 3)))
