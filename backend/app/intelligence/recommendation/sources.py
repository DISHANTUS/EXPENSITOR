"""Recommendation source adapters (C9) — map already-computed intelligence into
Recommendations. No financial recomputation: reuses B2 insight strings, savings
states, dependency facts, and advisor_view numbers."""

from __future__ import annotations

from decimal import Decimal

from app.intelligence.advisor import phrasing as ph
from app.intelligence.recommendation.recommendation import (
    BEHAVIORAL_IMPROVEMENT,
    COMMITMENT_MANAGEMENT,
    DEPENDENCY_RISK,
    GOAL_RECOVERY,
    LIFESTYLE_OPTIMIZATION,
    SAVINGS_OPPORTUNITY,
    SPENDING_REDUCTION,
    TIMING_OPPORTUNITY,
    LifeImpact,
    OutcomePreview,
    Recommendation,
    RecommendationContext,
)

_KIND_TO_CATEGORY = {
    "opportunity": SAVINGS_OPPORTUNITY,
    "weakness": SPENDING_REDUCTION,
    "risk": BEHAVIORAL_IMPROVEMENT,
    "dependency": DEPENDENCY_RISK,
}
_TRIM_FRACTION = Decimal("0.30")  # a modest, realistic reduction for benefit estimates


def _slug(category: str) -> str:
    return category.strip().lower().split()[0] if category else "category"


def _rec(category, lever_key, *, title, action, impact, reasoning, expected_benefit, effort, confidence,
         urgency, consequences, life_impact, outcome, evidence) -> Recommendation:
    return Recommendation(
        recommendation_id=f"{category}:{lever_key}", category=category, lever_key=lever_key,
        title=title, action=action, impact=float(impact), reasoning=reasoning,
        expected_benefit=expected_benefit, effort_level=effort, confidence=confidence, urgency=urgency,
        consequences_if_ignored=consequences, life_impact=life_impact, outcome_preview=outcome, evidence=evidence,
    )


def _cut_benefit(monthly_avg: str, currency: str) -> tuple[Decimal, str]:
    saving = (Decimal(str(monthly_avg)) * _TRIM_FRACTION).quantize(Decimal("1"))
    return saving, f"about {ph.money(saving, currency)}/month toward savings"


# --------------------------------------------------------------------------- #
def from_behavioral(ctx: RecommendationContext) -> list[Recommendation]:
    out: list[Recommendation] = []
    for ins in ctx.behavioral_insights:
        category = _KIND_TO_CATEGORY.get(ins.kind)
        if category is None:
            continue  # strengths/improvements/achievements are positive feedback, not actions
        cut = (ins.facts or {}).get("suggested_cut") or (ins.facts or {}).get("top_contributor")
        if cut and cut.get("category"):
            lever = f"reduce_{_slug(cut['category'])}"
            saving, benefit = _cut_benefit(cut.get("monthly_avg", "0"), ctx.currency)
            daily = f"fewer {cut['category']} purchases"
        elif ins.kind == "dependency":
            lever = f"dependency:{(ins.facts or {}).get('income_origin', 'income')}"
            saving, benefit, daily = Decimal("0"), "removes reliance on uncertain income", "none day-to-day"
        else:
            lever = f"behavior:{ins.metric_key}"
            saving, benefit, daily = Decimal("0"), "steadier money behaviour", "small habit adjustment"

        goal = ins.goal_links[0]["goal"] if ins.goal_links else None
        urgency = "high" if ins.kind in ("risk", "dependency") else "medium" if ins.kind == "weakness" else "low"
        effort = "low" if lever.startswith("reduce_") or ins.kind == "dependency" else "medium"
        life = LifeImpact(
            improves=("monthly savings" if saving > 0 else "financial stability"),
            daily_change=daily, unchanged="your goals setup and other plans",
        )
        outcome = OutcomePreview(
            goal_progress_change=(f"helps your {goal} goal" if goal else "none"),
            savings_change=benefit,
            dependency_change=("removes the dependency if acted on" if ins.kind == "dependency" else "none"),
            risk_change=("improves" if ins.kind in ("risk", "weakness") else "unchanged"),
            daily_life_change=daily,
            projected_result=f"{benefit}; the rest of your routine stays the same",
        )
        out.append(_rec(category, lever, title=ins.finding, action=ins.recommendation, impact=ins.priority,
                        reasoning=ins.reasoning, expected_benefit=benefit, effort=effort, confidence=ins.confidence,
                        urgency=urgency, consequences=ins.consequences, life_impact=life, outcome=outcome,
                        evidence={"source": "behavioral_insight", "kind": ins.kind, "metric_key": ins.metric_key}))
    return out


def from_dependencies(ctx: RecommendationContext) -> list[Recommendation]:
    out: list[Recommendation] = []
    for dep in ctx.dependencies:
        if dep.get("risk") not in ("moderate", "high"):
            continue
        when = dep.get("income_date")
        amount = ph.money(Decimal(str(dep.get("income_amount", 0))), ctx.currency)
        life = LifeImpact(improves="certainty of your near-term budget",
                          daily_change="the plan shifts to a safer date", unchanged="the plan itself still happens")
        outcome = OutcomePreview(
            goal_progress_change="none", savings_change="none",
            dependency_change=f"removes reliance on {amount} arriving on time", risk_change="improves",
            daily_life_change="plan happens a few days later", projected_result="same plan, less timing risk",
        )
        out.append(_rec(
            TIMING_OPPORTUNITY, "move_date",
            title=f"A safer time exists for a plan that relies on {amount}.",
            action=f"Moving it after {when} would remove that dependency, if the date is flexible.",
            impact=0.7 if dep.get("risk") == "high" else 0.5, reasoning=f"Risk if it's late: {dep.get('risk')}.",
            expected_benefit="removes a timing risk", effort="low", confidence="normal",
            urgency="high" if dep.get("risk") == "high" else "medium",
            consequences="If the money is late, that plan's budget gets tight.",
            life_impact=life, outcome=outcome, evidence={"source": "dependency", **dep}))
    return out


def from_savings(ctx: RecommendationContext) -> list[Recommendation]:
    out: list[Recommendation] = []
    cut = (ctx.advisor_view or {}).get("best_categories_to_cut", [])
    top_cut = cut[0] if cut else None
    for goal in ctx.goals:
        if goal.status != "behind":
            continue
        gap = goal.shortfall
        gap_txt = ph.money(gap, ctx.currency)
        # lever: use existing savings
        if ctx.available_savings > 0:
            contrib = min(ctx.available_savings, gap)
            out.append(_goal_rec("use_savings", goal, ctx,
                                 title=f"You're {gap_txt} behind your {goal.name} goal.",
                                 action=f"Using {ph.money(contrib, ctx.currency)} from existing savings would close most of the gap, if that suits you.",
                                 contribution=contrib, effort="low",
                                 daily="no change to daily spending", unchanged="your daily budget and plans"))
        # lever: wait for upcoming income
        if ctx.next_income:
            inc_amt = Decimal(str(ctx.next_income["amount"]))
            out.append(_goal_rec("wait_for_income", goal, ctx,
                                 title=f"Income is expected on {ctx.next_income['date']}.",
                                 action=f"Waiting for the {ph.money(inc_amt, ctx.currency)} would fund the {goal.name} goal without cuts.",
                                 contribution=min(inc_amt, gap), effort="low",
                                 daily="no change — just a short wait", unchanged="your spending and other plans"))
        # lever: reduce a category
        if top_cut:
            saving, _ = _cut_benefit(top_cut.get("monthly_avg", "0"), ctx.currency)
            out.append(_goal_rec(f"reduce_{_slug(top_cut['category'])}", goal, ctx,
                                 title=f"Reducing {top_cut['category']} could help your {goal.name} goal.",
                                 action=f"Trimming {top_cut['category']} would add about {ph.money(saving, ctx.currency)}/month, if saving more matters to you.",
                                 contribution=saving, effort="medium",
                                 daily=f"fewer {top_cut['category']} purchases", unchanged="your events and savings reserve"))
    return out


def _goal_rec(lever, goal, ctx, *, title, action, contribution, effort, daily, unchanged) -> Recommendation:
    contrib_txt = ph.money(contribution, ctx.currency)
    life = LifeImpact(improves=f"progress toward {goal.name}", daily_change=daily, unchanged=unchanged)
    outcome = OutcomePreview(
        goal_progress_change=f"~{contrib_txt} toward {goal.name}",
        savings_change=(contrib_txt if lever.startswith("reduce_") else "none"),
        dependency_change="none", risk_change="unchanged", daily_life_change=daily,
        projected_result=f"{goal.name} gets ~{contrib_txt} closer; {unchanged} stays as-is",
    )
    return _rec(GOAL_RECOVERY, lever, title=title, action=action,
                impact=min(1.0, float(contribution / goal.shortfall)) if goal.shortfall > 0 else 0.5,
                reasoning=f"You're {ph.money(goal.shortfall, ctx.currency)} behind this goal.",
                expected_benefit=f"~{contrib_txt} toward {goal.name}", effort=effort, confidence="normal",
                urgency="high" if goal.target_date else "medium",
                consequences=f"Without action, {goal.name} stays behind schedule.",
                life_impact=life, outcome=outcome,
                evidence={"source": "savings_goal", "goal": goal.name, "estimated_recovery_contribution": str(contribution)})


def from_advisor_and_load(ctx: RecommendationContext) -> list[Recommendation]:
    out: list[Recommendation] = []
    low = (ctx.advisor_view or {}).get("low_impact_categories", [])
    if low:
        c = low[0]
        saving, benefit = _cut_benefit(c.get("monthly_avg", "0"), ctx.currency)
        life = LifeImpact(improves="monthly savings", daily_change=f"slightly less {c['category']}",
                          unchanged="everything you value day-to-day")
        outcome = OutcomePreview(goal_progress_change="none", savings_change=benefit, dependency_change="none",
                                 risk_change="unchanged", daily_life_change=f"minor {c['category']} trim",
                                 projected_result=f"{benefit} with little lifestyle effect")
        out.append(_rec(LIFESTYLE_OPTIMIZATION, f"reduce_{_slug(c['category'])}",
                        title=f"{c['category']} is a low-impact place to save.", impact=0.4,
                        action=f"A small {c['category']} reduction frees up money with little lifestyle effect, if you'd like.",
                        reasoning="It's a small share of your spending.", expected_benefit=benefit, effort="low",
                        confidence="normal", urgency="low", consequences="No downside if left as-is.",
                        life_impact=life, outcome=outcome, evidence={"source": "advisor_view", **c}))
    load = ctx.recurring_load
    if load and float(load.get("load_ratio", 0)) >= 0.30:
        monthly = load.get("recurring_monthly", "0")
        life = LifeImpact(improves="monthly flexibility", daily_change="review subscriptions/commitments",
                          unchanged="anything you actively use")
        outcome = OutcomePreview(goal_progress_change="none", savings_change=f"up to {ph.money(Decimal(str(monthly)), ctx.currency)}/month if trimmed",
                                 dependency_change="none", risk_change="improves", daily_life_change="cancel unused commitments",
                                 projected_result="lower fixed monthly load")
        out.append(_rec(COMMITMENT_MANAGEMENT, "manage_commitments",
                        title=f"Recurring commitments are about {ph.money(Decimal(str(monthly)), ctx.currency)}/month.", impact=0.55,
                        action="Reviewing subscriptions/commitments could free up monthly room, if any are unused.",
                        reasoning="Recurring costs are a large share of your budget.", expected_benefit="frees monthly room",
                        effort="medium", confidence="normal", urgency="medium",
                        consequences="Fixed costs keep pressure on every month.", life_impact=life, outcome=outcome,
                        evidence={"source": "recurring_load", **load}))
    return out


def all_sources(ctx: RecommendationContext) -> list[Recommendation]:
    return [*from_behavioral(ctx), *from_dependencies(ctx), *from_savings(ctx), *from_advisor_and_load(ctx)]
