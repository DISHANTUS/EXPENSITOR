"""Per-engine advisor explainers (pure, deterministic).

Each consumes ONE structured engine result and emits an AdvisorExplanation
following the 5 beats. Reasoning is sourced from structured fields
(signals/factors/assumptions) — nothing is invented.
"""

from __future__ import annotations

from decimal import Decimal

from app.intelligence.advisor import phrasing as ph
from app.intelligence.advisor.explanation import (
    OPTIONAL,
    PRIMARY,
    SECONDARY,
    AdvisorAction,
    AdvisorExplanation,
)
from app.intelligence.behavior.profile import BehavioralProfile
from app.intelligence.decision.result import DecisionResult, DecisionStrategy
from app.intelligence.projection.affordability import AffordabilityResult
from app.intelligence.projection.budget_session_state import ActiveSession
from app.intelligence.projection.consequence import ConsequenceResult
from app.intelligence.projection.goal_feasibility import GoalFeasibilityResult
from app.intelligence.projection.dependency import Dependency
from app.intelligence.projection.guidance import GuidanceResult
from app.intelligence.projection.reschedule import RescheduleResult
from app.intelligence.projection.risk import RiskAssessment
from app.intelligence.savings.state import CustomGoalState, MonthlyTargetState, RecoveryOption, SavingsReasons

_RISK_SEVERITY = {"none": "info", "low": "info", "moderate": "warning", "high": "alert", "critical": "alert"}


def _d(value) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


# --------------------------------------------------------------------------- #
def explain_guidance(g: GuidanceResult, *, currency: str) -> AdvisorExplanation:
    sd = ph.money(g.safe_daily_spending, currency)
    threshold_action = next((a for a in g.recommended_actions if a.action == "threshold_binding"), None)
    reason = "Your monthly limit is the tighter constraint right now." if threshold_action else None
    action = AdvisorAction("spend_within_daily", PRIMARY, f"Keep daily spending near {sd}.",
                           {"safe_daily": str(g.safe_daily_spending)})
    return AdvisorExplanation(
        headline="Here's your safe spending.",
        impact=f"You can spend about {sd} a day and stay on track.",
        reason=reason,
        key_number=f"Safe daily spend: {sd}.",
        best_next_action=action,
        severity="info",
        facts={"safe_daily": str(g.safe_daily_spending), "safe_weekly": str(g.safe_weekly_spending)},
    )


def explain_affordability(a: AffordabilityResult, *, currency: str, item_label: str = "this") -> AdvisorExplanation:
    expected_after = _d(a.min_after.get("expected", 0))
    if a.verdict == "affordable":
        headline, severity = f"You can afford {item_label}.", "success"
        impact = f"Even after it, your balance stays positive ({ph.money(expected_after, currency)} at the low point)."
        reason, risk, action = None, None, None
    elif a.verdict == "conditional":
        headline, severity = f"You can likely afford {item_label}, with some care.", "warning"
        impact = f"Your guaranteed money covers it; an uncertain payment could make it tight."
        reason = "Worst-case dips below zero, but the expected case stays positive."
        risk, action = None, AdvisorAction("wait_or_trim", SECONDARY, "Waiting for confirmed income would remove the risk.", {})
    else:
        headline, severity = f"{item_label.capitalize()} would stretch you too far right now.", "alert"
        impact = f"You'd be short about {ph.money(a.shortfall, currency)} in the expected case."
        reason = "Even expected income doesn't cover it by the target date."
        risk = None
        action = AdvisorAction("free_up_funds", PRIMARY,
                               f"Free up about {ph.money(a.shortfall, currency)} or wait for more income.",
                               {"shortfall": str(a.shortfall)})
    key = (f"Shortfall: {ph.money(a.shortfall, currency)}." if a.verdict == "unaffordable"
           else f"Low point: {ph.money(expected_after, currency)}.")
    return AdvisorExplanation(headline=headline, impact=impact, reason=reason, key_number=key,
                              best_next_action=action, risk=risk, severity=severity,
                              facts={"verdict": a.verdict, "shortfall": str(a.shortfall)})


def explain_goal(g: GoalFeasibilityResult, *, currency: str) -> AdvisorExplanation:
    if g.feasible:
        headline, severity = "You're on track for this goal.", "success"
        impact = "Your expected balance reaches the target by the date."
        action = None
        key = f"Confidence: {g.confidence}."
    else:
        headline, severity = "You're a bit short on this goal.", "warning"
        impact = f"Saving {ph.money(g.required_daily_saving, currency)} a day would close the gap."
        action = AdvisorAction("save_daily", PRIMARY, f"Set aside {ph.per_day(g.required_daily_saving, currency)}.",
                               {"required_daily_saving": str(g.required_daily_saving)})
        key = f"Needed: {ph.per_day(g.required_daily_saving, currency)}."
    return AdvisorExplanation(headline=headline, impact=impact, reason=f"Confidence is {g.confidence}.",
                              key_number=key, best_next_action=action, severity=severity,
                              facts={"feasible": g.feasible, "confidence": g.confidence,
                                     "required_daily_saving": str(g.required_daily_saving)})


def explain_risk(r: RiskAssessment, *, currency: str) -> AdvisorExplanation:
    severity = _RISK_SEVERITY.get(r.risk_level, "info")
    headline = f"Your finances look {r.risk_level}."
    low = ph.money(r.min_expected_balance, currency)
    impact = f"Your projected low point is {low} on {ph.on_date(r.min_expected_balance_date)}."
    reason = f"Main driver: {r.signals[0].code.replace('_', ' ')}." if r.signals else None
    action = None
    if r.recovery_plan:
        first = r.recovery_plan[0]
        action = AdvisorAction(first.action, PRIMARY, "A recovery step is available.", first.data)
    return AdvisorExplanation(headline=headline, impact=impact, reason=reason,
                              key_number=f"Low point: {ph.money(r.min_expected_balance, currency)}.",
                              best_next_action=action, severity=severity,
                              facts={"risk_level": r.risk_level, "risk_score": r.risk_score})


def explain_consequence(c: ConsequenceResult, *, currency: str, item_label: str = "this") -> AdvisorExplanation:
    before = _d(c.safe_daily_impact.get("without", 0))
    after = _d(c.safe_daily_impact.get("with", 0))
    severity = "success" if c.affordable else "alert"
    headline = f"If you go ahead with {item_label}:"
    impact = f"Your safe daily spend {ph.delta_phrase(before, after, currency)} (now {ph.money(after, currency)})."
    reason = None
    action = None
    if c.required_adjustments:
        adj = c.required_adjustments[0]
        action = AdvisorAction(adj.action, PRIMARY, "An adjustment would keep you comfortable.", adj.data)
    risk = f"Risk level: {c.risk_level}." if c.risk_level in ("high", "critical") else None
    return AdvisorExplanation(headline=headline, impact=impact, reason=reason,
                              key_number=f"Balance after: {ph.money(c.projected_balance_after, currency)}.",
                              best_next_action=action, risk=risk, severity=severity,
                              facts={"affordable": c.affordable, "risk_level": c.risk_level})


def explain_reschedule(r: RescheduleResult, *, currency: str, item_label: str = "this") -> AdvisorExplanation:
    if r.best_date is None:
        return AdvisorExplanation(headline="No clearly better date was found.",
                                  impact="The current date is about as good as any in the window.",
                                  severity="info", facts={})
    best = next((c for c in r.candidates if c.date == r.best_date), None)
    reason = None
    if best is not None:
        factor = next((f for f in best.factors if f.type in ("salary_arrival", "receivable_arrival") and f.impact > 0), None)
        if factor is not None:
            kind = "salary" if factor.type == "salary_arrival" else "expected money"
            amount = ph.money(factor.impact, currency)
            reason = f"{ph.on_date(r.best_date)} is safer because your {kind} of {amount} arrives before then."
    action = AdvisorAction("move_date", PRIMARY, f"Move {item_label} to {ph.on_date(r.best_date)}.",
                           {"best_date": r.best_date.isoformat()})
    key = (f"Projected balance then: {ph.money(best.projected_balance, currency)}." if best else None)
    return AdvisorExplanation(headline=f"{ph.on_date(r.best_date)} looks like the best time.",
                              impact="Picking this date keeps your balance healthier.", reason=reason,
                              key_number=key, best_next_action=action, severity="info",
                              facts={"best_date": r.best_date.isoformat()})


def explain_behavior(p: BehavioralProfile) -> AdvisorExplanation:
    severity = "success" if p.composite_score >= 70 else "warning" if p.composite_score >= 40 else "alert"
    top_weak = p.weaknesses[0] if p.weaknesses else None
    top_opp = p.opportunities[0] if p.opportunities else None
    reason = top_weak.statement if top_weak else (p.strengths[0].statement if p.strengths else None)
    action = None
    if top_opp is not None:
        action = AdvisorAction("improve_behavior", PRIMARY, top_opp.statement + ".", {"metric": top_opp.metric_key})
    return AdvisorExplanation(headline="Here's your money behavior.",
                              impact=f"Your behavior score is {p.composite_score}/100.",
                              reason=reason, key_number=f"Behavior score: {p.composite_score}/100.",
                              best_next_action=action, severity=severity,
                              facts={"composite_score": p.composite_score, "confidence": p.confidence})


def explain_session(s: ActiveSession, *, currency: str) -> AdvisorExplanation:
    remaining = s.budget_base - s.spent_base
    over = s.utilization_percent >= 100
    severity = "alert" if over else "warning" if s.utilization_percent >= 75 else "info"
    impact = (f"You're over the '{s.title}' budget by {ph.money(-remaining, currency)}." if over
              else f"You've used {int(s.utilization_percent)}% of your '{s.title}' budget.")
    return AdvisorExplanation(headline=f"Session '{s.title}' status.", impact=impact,
                              key_number=f"Remaining: {ph.money(remaining, currency)}.",
                              severity=severity, facts={"utilization_percent": str(s.utilization_percent)})


def explain_receivable(*, source_name: str, amount: Decimal, currency: str, days_until: int | None,
                       days_overdue: int | None = None) -> AdvisorExplanation:
    if days_overdue is not None and days_overdue > 0:
        return AdvisorExplanation(headline=f"{ph.money(amount, currency)} from {source_name} is overdue.",
                                  impact=f"It was expected {days_overdue} days ago.",
                                  key_number=f"Amount: {ph.money(amount, currency)}.",
                                  best_next_action=AdvisorAction("follow_up_receivable", PRIMARY,
                                                                 f"A quick check-in with {source_name} may help.", {}),
                                  severity="warning", facts={"days_overdue": days_overdue})
    when = ph.days(days_until) if days_until is not None else "soon"
    return AdvisorExplanation(headline=f"{ph.money(amount, currency)} expected from {source_name}.",
                              impact=f"It should arrive {when}.",
                              key_number=f"Amount: {ph.money(amount, currency)} {when}.",
                              severity="info", facts={"days_until": days_until})


# --------------------------------------------------------------------------- #
_INSIGHT_SEVERITY = {
    "strength": "success", "achievement": "success", "improvement": "success",
    "opportunity": "info", "weakness": "warning", "risk": "alert", "dependency": "warning",
}


def explain_behavioral_insight(insight) -> AdvisorExplanation:
    """Concise advisor commentary for a BehavioralInsight (duck-typed). Observation,
    never a command. Shape: what happened / why it matters / what can be done."""
    action = (AdvisorAction(insight.metric_key or insight.kind, PRIMARY, insight.recommendation, {})
              if insight.recommendation else None)
    risk = insight.consequences if insight.kind in ("risk", "weakness", "dependency") else None
    return AdvisorExplanation(
        headline=insight.finding, impact=insight.impact, reason=insight.reasoning,
        key_number=None, best_next_action=action, risk=risk,
        severity=_INSIGHT_SEVERITY.get(insight.kind, "info"),
        facts={**insight.facts, "consequences": insight.consequences, "confidence_note": insight.confidence_note},
    )


def explain_modifier(finding) -> AdvisorExplanation:
    """Map a ModifierFinding (duck-typed) to the uniform advisor explanation shape."""
    action = AdvisorAction(finding.analyzer, PRIMARY, finding.recommendation, {}) if finding.recommendation else None
    alts = tuple(AdvisorAction(finding.analyzer, SECONDARY, a, {}) for a in finding.alternatives)
    key_number = f"Recovery: about {finding.recovery_time_days} days." if finding.recovery_time_days else None
    return AdvisorExplanation(
        headline=finding.finding, impact=finding.impact, reason=finding.reasoning, key_number=key_number,
        best_next_action=action, alternative_actions=alts, severity="info", facts=finding.facts,
    )


def _strategy_detail(s: DecisionStrategy, currency: str) -> str:
    if s.strategy_kind == "buy_now":
        return "Go ahead now."
    if s.strategy_kind == "use_savings":
        return f"Use {ph.money(s.savings_used, currency)} from your available savings (keeps your reserve)."
    if s.strategy_kind == "wait_for_income":
        return f"Wait until {ph.on_date(s.purchase_date)}, when your income arrives."
    if s.strategy_kind == "reduce_discretionary":
        return f"Set aside about {ph.per_day(s.daily_saving_required, currency)} for {s.saving_days} days, then buy."
    if s.strategy_kind == "split_into_stages":
        return "Split it into stages timed to your income."
    if s.strategy_kind == "move_date":
        return f"Move it to {ph.on_date(s.purchase_date)}."
    return "Consider this option."


def explain_decision(result: DecisionResult) -> AdvisorExplanation:
    currency = result.currency
    label = result.item_label
    verdict_map = {
        "affordable": (f"You can go ahead with {label}.", "success"),
        "tight": (f"{label.capitalize()} is doable, with a little planning.", "warning"),
        "not_now": (f"{label.capitalize()} is hard to do right now — but there are paths to it.", "alert"),
    }
    headline, severity = verdict_map.get(result.verdict, (f"About {label}:", "info"))

    best = result.best_strategy
    impact = f"Your safe daily spend would be about {ph.money(result.impact.daily_budget_after, currency)}."
    reason, best_action, risk = None, None, None
    alternatives: list[AdvisorAction] = []
    if best is not None:
        best_action = AdvisorAction(best.strategy_kind, PRIMARY, _strategy_detail(best, currency),
                                    {"purchase_date": best.purchase_date.isoformat(), "score": best.score})
        if best.strategy_kind in ("wait_for_income", "move_date"):
            reason = next((a for a in best.assumptions), None)
        if best.risk_after in ("high", "critical"):
            risk = f"This raises your risk level to {best.risk_after}."
        others = [s for s in result.strategies if s.strategy_id != best.strategy_id and s.feasible]
        for i, s in enumerate(others[:3]):
            alternatives.append(AdvisorAction(s.strategy_kind, SECONDARY if i == 0 else OPTIONAL,
                                              _strategy_detail(s, currency),
                                              {"purchase_date": s.purchase_date.isoformat(), "score": s.score}))

    key = f"Impact: {result.impact.impact_level}. Safe daily after: {ph.money(result.impact.daily_budget_after, currency)}."
    return AdvisorExplanation(headline=headline, impact=impact, reason=reason, key_number=key,
                              best_next_action=best_action, alternative_actions=tuple(alternatives),
                              risk=risk, severity=severity,
                              facts={"verdict": result.verdict, "impact_level": result.impact.impact_level})


# --------------------------------------------------------------------------- #
def _origin_phrase(origin: str) -> str:
    if origin.startswith("receivable"):
        return "expected money"
    if "salary" in origin:
        return "your salary"
    return "expected income"


def explain_dependency(dep: Dependency, *, currency: str, item_label: str = "This plan") -> AdvisorExplanation:
    when = ph.on_date(dep.income_date)
    window = f" in the {dep.income_time_window}" if dep.income_time_window else ""
    amount = ph.money(dep.income_amount, currency)
    severity = "alert" if dep.risk == "high" else "warning" if dep.risk == "moderate" else "info"
    reason = f"Without {_origin_phrase(dep.income_origin)} of {amount} on {when}{window}, you'd be short by then."
    action = AdvisorAction("confirm_income", PRIMARY,
                           "A quick check that the money is on time would remove the uncertainty.", {})
    return AdvisorExplanation(
        headline=f"{item_label} relies on {_origin_phrase(dep.income_origin)} of {amount} on {when}{window}.",
        impact="If it arrives late, you'd need to use savings or trim the plan.",
        reason=reason, key_number=f"Depends on: {amount} ({dep.risk} risk).",
        best_next_action=action, risk=(f"Dependency risk: {dep.risk}." if dep.risk != "low" else None),
        severity=severity, facts=dep.as_dict(),
    )


def _recovery_action(option: RecoveryOption, currency: str) -> AdvisorAction:
    if option.choice == "distribute":
        months = option.data.get("distribute_months")
        per_month = ph.money(Decimal(option.data.get("per_month_add", "0")), currency)
        detail = f"Spread the shortfall over {months} months (about {per_month} extra each month)."
    elif option.choice == "new_plan":
        detail = "Set a different target amount or date."
    else:
        detail = "Keep your target as-is; the gap isn't carried forward."
    return AdvisorAction(option.choice, OPTIONAL, detail, option.data)


def _top_contributor(reasons: SavingsReasons) -> str | None:
    if reasons.expenses:
        cat = reasons.expenses[0].get("category")
        if cat:
            return f"Spending on {cat} is a main contributor."
    if reasons.decisions:
        return "Upcoming planned spending is the main pressure."
    return None


def explain_monthly_target(
    state: MonthlyTargetState, reasons: SavingsReasons, options: list[RecoveryOption], *, currency: str
) -> AdvisorExplanation:
    eff = ph.money(state.effective_target, currency)
    proj = ph.money(state.projected_net, currency)
    if state.status == "behind":
        severity, headline = "warning", "This month's savings target is at risk."
        reason = _top_contributor(reasons)
        key = f"Projected shortfall: {ph.money(state.shortfall, currency)}."
        best = AdvisorAction("review_recovery_options", PRIMARY, "Here are some ways to respond — your choice.", {})
        alts = tuple(_recovery_action(o, currency) for o in options)
    else:
        severity = "success" if state.status == "met" else "info"
        headline = "You've met this month's target." if state.status == "met" else "You're on track this month."
        reason, key, best, alts = None, f"Saved so far: {ph.money(state.net_so_far, currency)} of {eff}.", None, ()
    return AdvisorExplanation(
        headline=headline, impact=f"Target {eff}, projected {proj}.", reason=reason, key_number=key,
        best_next_action=best, alternative_actions=alts, severity=severity, facts=state.as_dict(),
    )


def explain_custom_goal(state: CustomGoalState, reasons: SavingsReasons, *, currency: str) -> AdvisorExplanation:
    pct = int(state.progress * 100)
    if state.status == "completed":
        return AdvisorExplanation(headline="Goal reached.", impact="You've hit this savings goal.",
                                  key_number=f"Progress: {pct}%.", severity="success", facts=state.as_dict())
    if state.status == "on_track":
        return AdvisorExplanation(
            headline="You're on track for this goal.",
            impact=f"At your current pace you should reach it"
                   + (f" around {ph.on_date(state.projected_completion_date)}." if state.projected_completion_date else "."),
            reason=f"Confidence is {state.confidence}.", key_number=f"Progress: {pct}%.",
            severity="success", facts=state.as_dict(),
        )
    action = AdvisorAction("save_daily", PRIMARY,
                           f"Setting aside {ph.per_day(state.required_daily_saving, currency)} would close the gap.",
                           {"required_daily_saving": str(state.required_daily_saving)})
    return AdvisorExplanation(
        headline="You're a bit short on this goal.",
        impact=f"Saving {ph.money(state.required_daily_saving, currency)} a day would get you there.",
        reason=_top_contributor(reasons) or f"Confidence is {state.confidence}.",
        key_number=f"Needed: {ph.per_day(state.required_daily_saving, currency)}.",
        best_next_action=action, severity="warning", facts=state.as_dict(),
    )
