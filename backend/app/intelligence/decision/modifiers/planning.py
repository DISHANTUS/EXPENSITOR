"""Planning analyzers (thin views — no new logic): opportunity timing &
funding strategy reuse the Decision Engine's output; opportunity lost reuses the
savings engine + dependencies. This is the 'not just affordability' section."""

from __future__ import annotations

import dataclasses
import uuid
from datetime import date
from decimal import Decimal

from app.intelligence.advisor import phrasing as ph
from app.intelligence.decision.modifiers.base import AnalyzerCtx, ModifierFinding, register
from app.intelligence.projection.planned_projection import OutflowEvent
from app.intelligence.projection.scenario import Scenario
from app.intelligence.savings import engine as savings_engine


def _augment(scenario: Scenario, amount: Decimal, when: date) -> Scenario:
    effective = max(scenario.today, when)
    extra = OutflowEvent(effective, amount, "hypothetical", uuid.uuid4(), False, 0)
    return dataclasses.replace(scenario, outflows=scenario.outflows + (extra,),
                               horizon=max(scenario.horizon, effective))


# --------------------------------------------------------------------------- #
def _opportunity_timing_run(ctx: AnalyzerCtx) -> ModifierFinding | None:
    result = ctx.decision_result
    if result is None:
        return None
    timing = [s for s in result.strategies if s.strategy_kind in ("wait_for_income", "move_date") and s.feasible]
    deps = list(result.dependencies)
    if not timing and not deps:
        return None
    best = min(timing, key=lambda s: s.purchase_date) if timing else None
    risks = [d for d in deps if d.get("risk") in ("moderate", "high")]
    rec = (f"A safer date is {ph.on_date(best.purchase_date)} (income arrives first)." if best
           else "Confirming the money you're relying on would remove the timing risk.")
    return ModifierFinding(
        analyzer="opportunity_timing",
        finding=(f"{ph.on_date(best.purchase_date)} is a safer time than now." if best
                 else "This purchase relies on money that hasn't arrived yet."),
        impact=(f"{len(risks)} dependency(ies) carry timing risk." if risks else "Timing looks flexible."),
        reasoning="Based on when your expected income lands relative to this spend.",
        recommendation=rec, recovery_time_days=result.impact.days_until_recovery,
        facts={"best_date": best.purchase_date.isoformat() if best else None, "dependencies": deps},
    )


register("opportunity_timing", trigger=lambda c: c.decision_result is not None, run=_opportunity_timing_run)


# --------------------------------------------------------------------------- #
def _funding_strategy_run(ctx: AnalyzerCtx) -> ModifierFinding | None:
    result = ctx.decision_result
    if result is None:
        return None
    feasible = [s for s in result.strategies if s.feasible]
    kinds = [s.strategy_kind for s in feasible]
    best = result.best_strategy
    return ModifierFinding(
        analyzer="funding_strategy",
        finding=f"{len(feasible)} funding option(s): {', '.join(k.replace('_', ' ') for k in kinds) or 'pay now'}.",
        impact=f"Recommended: {best.strategy_kind.replace('_', ' ') if best else 'pay from current balance'}.",
        reasoning="Drawn from your balance, expected income, receivables, and savings room.",
        recommendation=(f"Best fit: {best.strategy_kind.replace('_', ' ')}." if best else "Pay from your current balance."),
        alternatives=tuple(k.replace("_", " ") for k in kinds if not best or k != best.strategy_kind),
        recovery_time_days=result.impact.days_until_recovery,
        facts={"strategies": kinds, "best": best.strategy_kind if best else None},
    )


register("funding_strategy", trigger=lambda c: c.decision_result is not None, run=_funding_strategy_run)


# --------------------------------------------------------------------------- #
def _opportunity_lost_run(ctx: AnalyzerCtx) -> ModifierFinding:
    cur = ctx.currency
    augmented = _augment(ctx.scenario, ctx.amount, ctx.when)
    affected: list[dict] = []
    for g in ctx.goals:
        if g.kind == "monthly_target":
            before = savings_engine.evaluate_monthly_target(ctx.scenario, base_target=g.target_amount, net_so_far=ctx.net_so_far)
            after = savings_engine.evaluate_monthly_target(augmented, base_target=g.target_amount, net_so_far=ctx.net_so_far)
            if before.status != "behind" and after.status == "behind":
                affected.append({"goal": g.name, "before": before.status, "after": after.status})
        elif g.target_date is not None and g.target_date <= ctx.scenario.horizon:
            before = savings_engine.evaluate_custom_goal(ctx.scenario, target_amount=g.target_amount, target_date=g.target_date)
            after = savings_engine.evaluate_custom_goal(augmented, target_amount=g.target_amount, target_date=g.target_date)
            b, a = before.projected_completion_date, after.projected_completion_date
            if b is not None and (a is None or a > b):
                delay = (a - b).days if a is not None else None
                affected.append({"goal": g.name, "completion_before": b.isoformat(),
                                 "completion_after": a.isoformat() if a else None, "delay_days": delay})

    deps = list(ctx.decision_result.dependencies) if ctx.decision_result else []
    recovery = ctx.decision_result.impact.days_until_recovery if ctx.decision_result else None
    if affected or deps:
        finding = f"This affects {len(affected)} savings goal(s) and {len(deps)} dependent plan(s)."
        impact = "Spending this now sets back other goals/plans, beyond just affordability."
        rec = "Consider a funding option that protects your goals (e.g. wait for income or split it)."
    else:
        finding = "This doesn't set back your savings goals or upcoming plans."
        impact = "Your goals and plans stay on track."
        rec = "You're clear to proceed on this front."
    return ModifierFinding(
        analyzer="opportunity_lost", finding=finding, impact=impact,
        reasoning="Compared your goals/plans with and without this spend.",
        recommendation=rec, recovery_time_days=recovery,
        facts={"savings_targets": affected, "dependent_plans": deps,
               "recovery_time_days": recovery},
    )


register("opportunity_lost",
         trigger=lambda c: bool(c.goals) or (c.decision_result is not None and bool(c.decision_result.dependencies)),
         run=_opportunity_lost_run)
