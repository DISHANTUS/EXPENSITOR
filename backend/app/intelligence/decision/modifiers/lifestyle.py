"""Lifestyle modifier analyzers (C7a-2) — UNBLOCKED by B1.5a.

These read the behavioral profile via ``ctx.behavior_view["metrics"]`` (populated
by decision_service from the BehavioralProfile) — they perform NO behavioural
computation themselves. That is exactly the "needs B1.5 + category linkage" that
caused the original deferral; the slope/frequency math lives in the metrics.
Auto analyzers (no user questions): they fire only when the profile already shows
the pattern at normal confidence.
"""

from __future__ import annotations

from app.intelligence.advisor import phrasing as ph
from app.intelligence.decision.modifiers.base import (
    AnalyzerCtx,
    ModifierFinding,
    recovery_time_days,
    register,
)

_PERSISTENT_MONTHS = 2


def _metric(ctx: AnalyzerCtx, key: str) -> dict | None:
    view = ctx.behavior_view or {}
    metrics = view.get("metrics") or {}
    m = metrics.get(key)
    return m if (m and m.get("confidence") == "normal") else None


# --- Lifestyle Inflation analyzer ------------------------------------------- #
def _inflation_trigger(ctx: AnalyzerCtx) -> bool:
    m = _metric(ctx, "lifestyle_inflation")
    return bool(m and m.get("trend") == "worsening" and (m.get("trend_duration_months") or 0) >= _PERSISTENT_MONTHS)


def _inflation_run(ctx: AnalyzerCtx) -> ModifierFinding | None:
    m = _metric(ctx, "lifestyle_inflation")
    if m is None:
        return None
    dur = m.get("trend_duration_months") or 0
    recovery = recovery_time_days(ctx.scenario, ctx.amount, ctx.when)
    return ModifierFinding(
        analyzer="lifestyle_inflation",
        finding=f"Your discretionary spending has been rising for {dur} month{'s' if dur != 1 else ''}.",
        impact=f"This {ph.money(ctx.amount, ctx.currency)} purchase continues that upward trend.",
        reasoning="Drawn from your discretionary-spend-to-income trend, not this purchase alone.",
        recommendation="Keeping this in line with recent months would steady your savings, if that matters to you.",
        alternatives=("Match this to a typical recent month rather than the rising trend.",),
        recovery_time_days=recovery,
        facts={"trend_duration_months": dur, "discretionary_to_income": m.get("facts", {}).get("discretionary_to_income")},
    )


register("lifestyle_inflation", trigger=_inflation_trigger, run=_inflation_run)


# --- Upgrade / Replacement analyzer ----------------------------------------- #
def _upgrade_trigger(ctx: AnalyzerCtx) -> bool:
    durable = getattr(ctx.attributes, "liquidity_class", "") == "durable_asset"
    m = _metric(ctx, "upgrade_replacement_behavior")
    return bool(durable and m and (m.get("facts", {}).get("replacement_events") or 0) >= 1)


def _upgrade_run(ctx: AnalyzerCtx) -> ModifierFinding | None:
    m = _metric(ctx, "upgrade_replacement_behavior")
    if m is None:
        return None
    events = m.get("facts", {}).get("replacement_events") or 0
    cats = m.get("facts", {}).get("categories") or []
    where = f" (e.g. {cats[0]})" if cats else ""
    recovery = recovery_time_days(ctx.scenario, ctx.amount, ctx.when)
    return ModifierFinding(
        analyzer="upgrade_replacement",
        finding=f"You've replaced or upgraded items in the same category {events} time(s) recently{where}.",
        impact=f"Another {ph.money(ctx.amount, ctx.currency)} replacement adds to that pattern.",
        reasoning="Based on repeat larger purchases in the same category, not this item alone.",
        recommendation="Confirming the current item truly needs replacing avoids an early upgrade, if that matters to you.",
        alternatives=("Delay until the current item is genuinely at end of life.",),
        recovery_time_days=recovery,
        facts={"replacement_events": events, "categories": cats},
    )


register("upgrade_replacement", trigger=_upgrade_trigger, run=_upgrade_run)
