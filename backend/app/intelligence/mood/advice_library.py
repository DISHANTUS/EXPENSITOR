"""Event-specific advice (Sprint 4c-B polish, pure).

Tiny human touches keyed by event type, with optional {person}/{goal}
interpolation. Deterministic; the narration layer may later reword them.
"""

from __future__ import annotations

_ADVICE = {
    # planned-event occasions
    "date": "Enjoy your time{with_person} — try to stay present.",
    "outing": "Enjoy your outing{with_person} — make the most of it.",
    "birthday": "Celebrate a little — you’ve earned it.",
    "anniversary": "Make it a special one.",
    "travel": "Keep a little emergency cash handy.",
    "vacation": "Keep a little emergency cash handy.",
    "festival": "Enjoy the celebrations.",
    "interview": "Good luck — arrive a little early and bring your documents.",
    "exam": "Get a good night’s sleep tonight.",
    "graduation": "Congratulations on the milestone.",
    # money / relationship facts
    "repay_due": "A gentle reminder is fine if it helps.",
    "repay_overdue": "It may be worth a kind follow-up{with_person}.",
    "income_today": "Maybe set some aside toward your {goal}.",
}


def advice_for(event_id: str | None, *, person: str | None = None, goal: str | None = None) -> str | None:
    template = _ADVICE.get(event_id or "")
    if template is None:
        return None
    if "{goal}" in template and not goal:
        return None                                  # income advice only when there's a goal to aim at
    return (template
            .replace("{with_person}", f" with {person}" if person else "")
            .replace("{goal}", goal or ""))
