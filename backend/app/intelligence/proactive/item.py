"""Proactive Advisor — the single unified item model (Decision 1).

One `ProactiveItem` covers alert / warning / reminder / achievement / opportunity /
review (via `kind`) — same lifecycle, ranking, notification-readiness, and
commentary integration. Every item STANDS ALONE (R1: what happened / why it
matters / what could happen next / most useful number) and exposes the stable
scheduler contract (R5). Deterministic; surfaces existing intelligence only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

ALERT, WARNING, REMINDER, ACHIEVEMENT, OPPORTUNITY, REVIEW = (
    "alert", "warning", "reminder", "achievement", "opportunity", "review"
)


@dataclass(frozen=True)
class ProactiveItem:
    kind: str                       # alert | warning | reminder | achievement | opportunity | review
    category: str                   # dependency | income | stress | goal | health | lifestyle | savings | recommendation | review
    title: str
    # R1 — stands alone without any commentary layer
    what_happened: str
    why_it_matters: str
    what_next: str
    most_useful_number: str | None
    # R5 — stable scheduler contract
    severity: str                   # info | success | warning | alert
    priority: float                 # 0..1
    eligible_for_notification: bool
    expires_at: str | None          # ISO date, or None
    trigger_reason: str
    evidence: dict[str, Any] = field(default_factory=dict)

    def texts(self) -> list[str]:
        return [t for t in (self.title, self.what_happened, self.why_it_matters,
                            self.what_next, self.most_useful_number) if t]

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind, "category": self.category, "title": self.title,
            "what_happened": self.what_happened, "why_it_matters": self.why_it_matters,
            "what_next": self.what_next, "most_useful_number": self.most_useful_number,
            "severity": self.severity, "priority": round(self.priority, 4),
            "eligible_for_notification": self.eligible_for_notification,
            "expires_at": self.expires_at, "trigger_reason": self.trigger_reason,
            "evidence": self.evidence,
        }
