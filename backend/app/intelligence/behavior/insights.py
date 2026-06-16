"""Behavioral insight layer (B2) — reusable, deterministic, source-of-truth.

Turns a BehavioralProfile (+ optional goal/dependency context) into ACTIONABLE
insights. Every insight carries finding / impact / reasoning / recommendation /
consequences / confidence_note so Companion, Recommendation, Ollama and Health
Score consume one standard shape. Observations, never commands. No new math —
reads SWOR, metric facts, trends, and advisor_view only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from app.intelligence.advisor import phrasing as ph
from app.intelligence.behavior.profile import BehavioralProfile, SworItem

# kind -> a coarse human label / namespace
STRENGTH, WEAKNESS, OPPORTUNITY, RISK, IMPROVEMENT, ACHIEVEMENT, DEPENDENCY = (
    "strength", "weakness", "opportunity", "risk", "improvement", "achievement", "dependency"
)


@dataclass(frozen=True)
class InsightContext:
    """Real-world context so behavior connects to consequences (assembled by the
    service from existing engines — the insight layer stays pure)."""

    goals: tuple[tuple[str, str], ...] = ()      # (kind, name) of active savings goals
    dependencies: tuple[dict[str, Any], ...] = ()  # Dependency.as_dict() list


@dataclass(frozen=True)
class BehavioralInsight:
    kind: str
    metric_key: str
    dimension: str
    finding: str                 # what changed / happened
    impact: str                  # why it matters
    reasoning: str               # the biggest contributor / why
    recommendation: str          # what the user can do (conditional, never a command)
    consequences: str            # what happens if it continues
    confidence_note: str | None  # honest caveat when data is thin
    score: int
    trend: str
    trend_duration_months: int | None   # carried when available (B1 doesn't compute yet)
    confidence: str
    priority: float
    goal_links: tuple[dict[str, Any], ...] = ()
    facts: dict[str, Any] = field(default_factory=dict)

    def texts(self) -> list[str]:
        return [self.finding, self.impact, self.reasoning, self.recommendation, self.consequences,
                self.confidence_note or ""]

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind, "metric_key": self.metric_key, "dimension": self.dimension,
            "finding": self.finding, "impact": self.impact, "reasoning": self.reasoning,
            "recommendation": self.recommendation, "consequences": self.consequences,
            "confidence_note": self.confidence_note, "score": self.score, "trend": self.trend,
            "trend_duration_months": self.trend_duration_months, "confidence": self.confidence,
            "priority": round(self.priority, 4), "goal_links": list(self.goal_links), "facts": self.facts,
        }


# --------------------------------------------------------------------------- #
def _confidence_note(confidence: str, months: int, trend: str = "") -> str | None:
    if confidence != "normal":
        return "Based on limited history."
    if months <= 1:
        return "Only one month of data available."
    if trend == "unknown":
        return "This pattern is still forming."
    return None


def _top(av: dict, key: str) -> dict | None:
    items = av.get(key, [])
    return items[0] if items else None


def _money(value: Any, currency: str) -> str:
    return ph.money(Decimal(str(value)), currency)


def _goal_links(ctx: InsightContext, money_reducing: bool) -> tuple[dict[str, Any], ...]:
    if not money_reducing:
        return ()
    return tuple({"goal": name, "kind": kind, "effect": "reduces what's available for this goal"}
                 for kind, name in ctx.goals)


# --- per-kind builders ------------------------------------------------------
def _strength(item: SworItem, months: int) -> BehavioralInsight:
    return BehavioralInsight(
        kind=STRENGTH, metric_key=item.metric_key, dimension=item.dimension,
        finding=item.statement, impact="This is helping keep your finances steady.",
        reasoning=f"Scoring {item.score}/100 here.",
        recommendation="Keeping this up protects your goals.",
        consequences="Maintaining it keeps you on track.",
        confidence_note=_confidence_note(item.confidence, months), score=item.score, trend=item.trend,
        trend_duration_months=None, confidence=item.confidence, priority=item.score / 100.0,
        facts={"level": item.level},
    )


def _weakness(item: SworItem, av: dict, ctx: InsightContext, currency: str, months: int) -> BehavioralInsight:
    overspend = _top(av, "overspending_categories")
    cut = _top(av, "best_categories_to_cut")
    if overspend:
        reasoning = f"The biggest contributor is {overspend['category']} (~{_money(overspend['monthly_avg'], currency)}/month)."
    else:
        reasoning = f"Currently scoring {item.score}/100, trend {item.trend}."
    rec = (f"Trimming {cut['category']} would have the largest effect, if saving more matters to you."
           if cut else "Small, steady reductions here would help most, if saving more matters to you.")
    return BehavioralInsight(
        kind=WEAKNESS, metric_key=item.metric_key, dimension=item.dimension,
        finding=item.statement, impact="This is reducing how much you can keep each month.",
        reasoning=reasoning, recommendation=rec,
        consequences="If it continues, less will be available for your goals and plans.",
        confidence_note=_confidence_note(item.confidence, months), score=item.score, trend=item.trend,
        trend_duration_months=None, confidence=item.confidence, priority=(100 - item.score) / 100.0,
        goal_links=_goal_links(ctx, money_reducing=True),
        facts={"level": item.level, "top_contributor": overspend, "suggested_cut": cut},
    )


def _opportunity(item: SworItem, av: dict, currency: str, months: int) -> BehavioralInsight:
    cut = _top(av, "best_categories_to_cut")
    rec = (f"Reducing {cut['category']} (~{_money(cut['monthly_avg'], currency)}/month) would have the largest "
           f"effect, if saving more matters to you." if cut
           else "A small reduction here could free up money, if saving more matters to you.")
    return BehavioralInsight(
        kind=OPPORTUNITY, metric_key=item.metric_key, dimension=item.dimension,
        finding=item.statement, impact="There's realistic room to free up money here.",
        reasoning=f"Scoring {item.score}/100 — improvable.", recommendation=rec,
        consequences="Acting on it could increase what you save each month.",
        confidence_note=_confidence_note(item.confidence, months), score=item.score, trend=item.trend,
        trend_duration_months=None, confidence=item.confidence,
        priority=max(0.0, (70 - item.score)) / 100.0 + 0.3,
        facts={"level": item.level, "suggested_cut": cut},
    )


def _risk(item: SworItem, ctx: InsightContext, months: int) -> BehavioralInsight:
    return BehavioralInsight(
        kind=RISK, metric_key=item.metric_key, dimension=item.dimension,
        finding=item.statement, impact="This behaviour is trending the wrong way.",
        reasoning=f"Trend is {item.trend} (score {item.score}/100).",
        recommendation="Easing off here would steady things, if keeping a buffer matters to you.",
        consequences="If the trend continues it could pressure your budget (a behaviour signal, not insolvency).",
        confidence_note=_confidence_note(item.confidence, months), score=item.score, trend=item.trend,
        trend_duration_months=None, confidence=item.confidence, priority=(100 - item.score) / 100.0 + 0.1,
        goal_links=_goal_links(ctx, money_reducing=True), facts={"level": item.level},
    )


def _improvement(metric, months: int) -> BehavioralInsight:
    title = metric.key.replace("_", " ")
    return BehavioralInsight(
        kind=IMPROVEMENT, metric_key=metric.key, dimension=metric.dimension,
        finding=f"Your {title} is improving.", impact="Recent months look better than before.",
        reasoning="The trend has moved in a healthier direction.",
        recommendation="Keeping this direction up will compound over time.",
        consequences="Continued improvement strengthens your finances.",
        confidence_note=_confidence_note(metric.confidence, months), score=metric.score, trend="improving",
        trend_duration_months=None, confidence=metric.confidence, priority=metric.score / 100.0,
        facts=dict(metric.facts),
    )


_ACHIEVEMENTS = {
    "savings_consistency": ("months_positive", lambda v: v >= 3, "You've saved in {v} straight months."),
    "budget_session_success_rate": ("under_budget", lambda v: v >= 3, "You finished {v} budget sessions under budget."),
}


def _achievements(profile: BehavioralProfile) -> list[BehavioralInsight]:
    out: list[BehavioralInsight] = []
    for key, (fact_key, ok, template) in _ACHIEVEMENTS.items():
        m = profile.metric(key)
        if m is None or m.confidence != "normal":
            continue
        v = m.facts.get(fact_key)
        if v is not None and ok(int(v)):
            out.append(BehavioralInsight(
                kind=ACHIEVEMENT, metric_key=key, dimension=m.dimension,
                finding=template.format(v=v), impact="A solid, factual milestone.",
                reasoning="Drawn directly from your recorded activity.",
                recommendation="Worth keeping up.", consequences="Sustaining it keeps you on track.",
                confidence_note=None, score=m.score, trend=m.trend, trend_duration_months=None,
                confidence=m.confidence, priority=0.5, facts=dict(m.facts),
            ))
    # improving recovery / fewer threshold violations
    for key, label in (("receivable_recovery_rate", "Your recovery of lent money is improving."),
                       ("threshold_violation_frequency", "You're staying under your monthly limit more often.")):
        m = profile.metric(key)
        if m is not None and m.confidence == "normal" and m.trend == "improving":
            out.append(BehavioralInsight(
                kind=ACHIEVEMENT, metric_key=key, dimension=m.dimension, finding=label,
                impact="A genuine improvement.", reasoning="Based on your recent trend.",
                recommendation="Worth keeping up.", consequences="Continuing strengthens your finances.",
                confidence_note=None, score=m.score, trend="improving", trend_duration_months=None,
                confidence=m.confidence, priority=0.55, facts=dict(m.facts),
            ))
    return out


def _dependency(dep: dict, currency: str) -> BehavioralInsight:
    origin = dep.get("income_origin", "")
    src = "expected money" if origin.startswith("receivable") else "your salary" if "salary" in origin else "expected income"
    amount = _money(dep.get("income_amount", 0), currency)
    when = dep.get("income_date")
    window = dep.get("income_time_window")
    when_txt = f"{when}" + (f" ({window})" if window else "")
    return BehavioralInsight(
        kind=DEPENDENCY, metric_key="dependency", dimension="cashflow_health",
        finding=f"Your near-term spending assumes {src} of {amount} arrives on {when_txt}.",
        impact="Your discretionary budget this week leans on that inflow.",
        reasoning=f"Risk if it's late: {dep.get('risk', 'unknown')}.",
        recommendation="Confirming it would remove the uncertainty, if it's important to your plans.",
        consequences="If it arrives late, your discretionary budget becomes tight until it lands.",
        confidence_note=None, score=50, trend="flat", trend_duration_months=None, confidence="normal",
        priority=0.9 if dep.get("risk") == "high" else 0.6, facts=dep,
    )


# --- top-level ---------------------------------------------------------------
def build_behavioral_insights(
    profile: BehavioralProfile, *, context: InsightContext | None = None, max_per_kind: int = 3
) -> list[BehavioralInsight]:
    ctx = context or InsightContext()
    av = profile.advisor or {}
    cur = profile.base_currency
    months = int(profile.window.get("complete_months", 0))

    insights: list[BehavioralInsight] = []
    insights += [_strength(s, months) for s in sorted(profile.strengths, key=lambda s: -s.score)[:max_per_kind]]
    insights += [_weakness(w, av, ctx, cur, months) for w in sorted(profile.weaknesses, key=lambda s: s.score)[:max_per_kind]]
    insights += [_opportunity(o, av, cur, months)
                 for o in sorted(profile.opportunities, key=lambda s: (s.level != "high", s.score))[:max_per_kind]]
    insights += [_risk(r, ctx, months) for r in sorted(profile.risks, key=lambda s: s.score)[:max_per_kind]]

    strong_keys = {s.metric_key for s in profile.strengths}
    improving = [m for m in profile.metrics
                 if m.trend == "improving" and m.confidence == "normal" and m.key not in strong_keys]
    insights += [_improvement(m, months) for m in sorted(improving, key=lambda m: -m.score)[:max_per_kind]]

    insights += _achievements(profile)[:max_per_kind]
    insights += [_dependency(d, cur) for d in ctx.dependencies
                 if d.get("risk") in ("moderate", "high")][:max_per_kind]
    return insights
