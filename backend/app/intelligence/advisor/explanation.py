"""Advisor explanation + action structures (deterministic, Ollama-off).

Every explanation follows the 5 beats:
  1 what happened (headline) · 2 most important impact · 3 why (reason) ·
  4 most useful number (key_number) · 5 action / risk (only if relevant)

Action-oriented: each explanation can carry best_next_action + alternatives with
an explicit priority, so Companion / Recommendations / Ollama consume them later.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Action priority ranks (machine-readable; used for ordering downstream).
PRIMARY = "primary"
SECONDARY = "secondary"
OPTIONAL = "optional"


@dataclass(frozen=True)
class AdvisorAction:
    action: str          # machine key, e.g. "wait_for_income", "reduce_discretionary"
    priority: str        # primary | secondary | optional
    detail: str          # concise, tone-guarded human phrase
    data: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {"action": self.action, "priority": self.priority, "detail": self.detail, "data": self.data}


@dataclass(frozen=True)
class AdvisorExplanation:
    headline: str
    impact: str
    reason: str | None = None
    key_number: str | None = None
    best_next_action: AdvisorAction | None = None
    alternative_actions: tuple[AdvisorAction, ...] = ()
    risk: str | None = None
    severity: str = "info"            # info | success | warning | alert
    facts: dict[str, Any] = field(default_factory=dict)

    def render(self) -> str:
        """Concise multi-line text — omits empty beats. No walls of text."""
        lines = [self.headline, self.impact]
        if self.reason:
            lines.append(self.reason)
        if self.key_number:
            lines.append(self.key_number)
        if self.best_next_action:
            lines.append(self.best_next_action.detail)
        if self.risk:
            lines.append(self.risk)
        return "\n".join(line for line in lines if line)

    def texts(self) -> list[str]:
        """All human strings (for tone-linting)."""
        out = [self.headline, self.impact, self.reason or "", self.key_number or "", self.risk or ""]
        if self.best_next_action:
            out.append(self.best_next_action.detail)
        out.extend(a.detail for a in self.alternative_actions)
        return out

    def as_dict(self) -> dict[str, Any]:
        return {
            "headline": self.headline,
            "impact": self.impact,
            "reason": self.reason,
            "key_number": self.key_number,
            "best_next_action": self.best_next_action.as_dict() if self.best_next_action else None,
            "alternative_actions": [a.as_dict() for a in self.alternative_actions],
            "risk": self.risk,
            "severity": self.severity,
            "facts": self.facts,
        }
