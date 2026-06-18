"""Mood rotation composer (Sprint 4c-A, pure).

Combines the base mood with active event/relationship/achievement/override moods
into a priority-ordered rotation that always returns to the base — so the face is
never stuck on one emoji, and an emergency override (first salary, goal completed)
dominates instead of a budget frown.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.intelligence.mood.moods import Mood, Priority


@dataclass(frozen=True)
class MoodState:
    base: Mood
    primary: Mood                       # the dominant resting face (override or base)
    rotation: list[Mood] = field(default_factory=list)
    reasons: list[dict[str, str]] = field(default_factory=list)


def _dedup_consecutive(seq: list[Mood]) -> list[Mood]:
    out: list[Mood] = []
    for m in seq:
        if not out or out[-1].id != m.id:
            out.append(m)
    return out


def compose(base: Mood, active: list[Mood], *, base_reasons: list[dict[str, str]] | None = None) -> MoodState:
    base_reasons = base_reasons or []

    # Emergency override = highest-priority CRITICAL override mood, if any.
    overrides = [m for m in active if m.kind == "override" and m.priority == Priority.CRITICAL]
    overrides.sort(key=lambda m: (m.priority, m.id), reverse=True)   # deterministic tie-break
    primary = overrides[0] if overrides else base

    # Everything else, most important first; base woven in between (stable order).
    others = [m for m in active if m.id != primary.id]
    others.sort(key=lambda m: (m.priority, m.id), reverse=True)

    seq: list[Mood] = [primary]
    for m in others:
        seq.append(base)
        seq.append(m)
    seq.append(base)
    rotation = _dedup_consecutive(seq)
    if len(rotation) == 1:                      # only the base — give it a gentle solo
        rotation = [base]

    return MoodState(base=base, primary=primary, rotation=rotation, reasons=base_reasons)
