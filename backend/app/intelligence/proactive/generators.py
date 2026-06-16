"""Proactive generators — each surfaces ONE already-computed source as ProactiveItems.

Pure + deterministic, registry-style (one fn each). Every item stands alone (R1),
respects preferences (R2 — opportunities only from policy-filtered recommendations),
and self-gates on confidence so cold-start stays silent (R4). No new math.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from decimal import Decimal

from app.intelligence.advisor import phrasing as ph
from app.intelligence.proactive.context import ProactiveContext
from app.intelligence.proactive.item import (
    ACHIEVEMENT,
    ALERT,
    OPPORTUNITY,
    REMINDER,
    WARNING,
    ProactiveItem,
)

GENERATORS: list[Callable[[ProactiveContext], list[ProactiveItem]]] = []


def _register(fn: Callable[[ProactiveContext], list[ProactiveItem]]):
    GENERATORS.append(fn)
    return fn


def _money(value, currency: str) -> str:
    return ph.money(Decimal(str(value)), currency)


def _fmt_date(value) -> str:
    d = date.fromisoformat(value) if isinstance(value, str) else value
    return ph.on_date(d)


def _metric(ctx: ProactiveContext, key: str) -> dict | None:
    m = ctx.metrics.get(key)
    return m if (m and m.get("confidence") == "normal") else None


# --- dependency risk (alert) ----------------------------------------------- #
@_register
def gen_dependency(ctx: ProactiveContext) -> list[ProactiveItem]:
    out = []
    for d in ctx.dependencies:
        if d.get("risk") not in ("moderate", "high"):
            continue
        amount = _money(d.get("income_amount", 0), ctx.currency)
        when = _fmt_date(d["income_date"]) if d.get("income_date") else "its expected date"
        high = d.get("risk") == "high"
        out.append(ProactiveItem(
            kind=ALERT if high else WARNING, category="dependency",
            title="A plan is leaning on money that could be late",
            what_happened=f"An upcoming plan depends on {amount} expected on {when}.",
            why_it_matters="If it arrives late, that plan could fall short and squeeze the rest of your month.",
            what_next="A quick check that the money is on time would remove the uncertainty.",
            most_useful_number=f"Amount riding on it: {amount}.",
            severity="alert" if high else "warning", priority=0.92 if high else 0.74,
            eligible_for_notification=True, expires_at=d.get("income_date"),
            trigger_reason=f"dependency:{d.get('risk')}:{d.get('income_date')}", evidence=d,
        ))
    return out


# --- income timing (reminder) ----------------------------------------------- #
@_register
def gen_income_timing(ctx: ProactiveContext) -> list[ProactiveItem]:
    ni = ctx.next_income
    if not ni or ni.get("amount") in (None, "") or not ni.get("date"):
        return []
    days = (date.fromisoformat(ni["date"]) - ctx.today).days
    if days < 0 or days > 1:
        return []
    amount = _money(ni["amount"], ni.get("currency") or ctx.currency)
    when = "today" if days == 0 else "tomorrow"
    tail = ""
    if ni.get("exact"):
        tail = f" (around {ni['exact']})"
    elif ni.get("window"):
        tail = f" (in the {ni['window']})"
    return [ProactiveItem(
        kind=REMINDER, category="income", title=f"Income expected {when}",
        what_happened=f"You're expecting {amount} {when}{tail}.",
        why_it_matters="It's about to lift what you can safely spend and fund your plans.",
        what_next="Worth holding any flexible spending until it lands.",
        most_useful_number=f"Incoming: {amount}.",
        severity="info", priority=0.6, eligible_for_notification=True,
        expires_at=ni["date"], trigger_reason=f"income_due:{ni['date']}", evidence=ni,
    )]


# --- financial stress worsening (warning) ----------------------------------- #
@_register
def gen_stress(ctx: ProactiveContext) -> list[ProactiveItem]:
    m = _metric(ctx, "financial_stress_index")
    if m is None or m.get("trend") != "worsening":
        return []
    dur = m.get("trend_duration_months") or 0
    contributors = m.get("facts", {}).get("contributors") or []
    top = contributors[0]["name"].replace("_", " ") if contributors else "a few pressures"
    return [ProactiveItem(
        kind=WARNING, category="stress", title="Financial pressure has been building",
        what_happened=f"Your financial stress has been rising for {dur} month{'s' if dur != 1 else ''}.",
        why_it_matters="More of your budget is going to pressure points, leaving less slack.",
        what_next=f"Easing {top} would relieve the most pressure, if that matters to you.",
        most_useful_number=None,
        severity="warning", priority=0.7 + min(0.15, 0.03 * dur), eligible_for_notification=True,
        expires_at=None, trigger_reason=f"stress_worsening:{dur}m", evidence=m.get("facts", {}),
    )]


# --- goals: behind + sacrifice (warning) ------------------------------------ #
@_register
def gen_goals(ctx: ProactiveContext) -> list[ProactiveItem]:
    out = []
    for g in ctx.goals:
        if g.get("status") != "behind":
            continue
        short = g.get("shortfall")
        num = f"About {_money(short, ctx.currency)} short." if short and Decimal(str(short)) > 0 else None
        out.append(ProactiveItem(
            kind=WARNING, category="goal", title=f"You're behind on {g.get('name', 'a goal')}",
            what_happened=f"Your {g.get('name', 'goal')} is tracking below the pace it needs.",
            why_it_matters="At the current pace it won't reach its target on time.",
            what_next="A small, steady top-up would bring it back on track, if it's a priority.",
            most_useful_number=num, severity="warning", priority=0.72,
            eligible_for_notification=True, expires_at=None,
            trigger_reason=f"goal_behind:{g.get('name')}", evidence=g,
        ))
    if ctx.goal_sacrifice:
        sac = ctx.goal_sacrifice
        out.append(ProactiveItem(
            kind=WARNING, category="goal", title="One goal is crowding out another",
            what_happened=sac["statement"],
            why_it_matters="The slower goal will keep falling behind while the pool funds the other.",
            what_next="Rebalancing how much each goal gets would even out progress.",
            most_useful_number=None, severity="warning", priority=0.68,
            eligible_for_notification=True, expires_at=None,
            trigger_reason="goal_sacrifice", evidence=sac,
        ))
    return out


# --- health movement (achievement / warning) -------------------------------- #
@_register
def gen_health_movement(ctx: ProactiveContext) -> list[ProactiveItem]:
    h = ctx.health
    if not h or h.get("overall_confidence") != "normal":
        return []
    out = []
    pillars = {p["key"]: p for p in h.get("pillars", [])}
    if h.get("worsening_area") and (drag := h.get("biggest_drag")):
        p = pillars.get(h["worsening_area"], {})
        out.append(ProactiveItem(
            kind=WARNING, category="health", title=f"Your {p.get('label', 'health')} is slipping",
            what_happened=f"{drag['statement'].capitalize()} is the biggest drag on your {p.get('label', 'health')}.",
            why_it_matters="It's pulling your overall financial health down the most right now.",
            what_next="Addressing this one area would lift your score more than anything else.",
            most_useful_number=f"Overall health: {h.get('overall_score')}/100.",
            severity="warning", priority=0.66, eligible_for_notification=False, expires_at=None,
            trigger_reason=f"health_worsening:{h['worsening_area']}", evidence={"pillar": p, "drag": drag},
        ))
    if h.get("improving_area"):
        p = pillars.get(h["improving_area"], {})
        out.append(ProactiveItem(
            kind=ACHIEVEMENT, category="health", title=f"Your {p.get('label', 'health')} is improving",
            what_happened=f"Your {p.get('label', 'health')} has been moving in the right direction.",
            why_it_matters="Sustained improvement here compounds into a stronger overall position.",
            what_next="Keeping this up will keep lifting your overall health.",
            most_useful_number=f"Overall health: {h.get('overall_score')}/100.",
            severity="success", priority=0.4, eligible_for_notification=True, expires_at=None,
            trigger_reason=f"health_improving:{h['improving_area']}", evidence={"pillar": p},
        ))
    return out


# --- lifestyle inflation / commitment pressure (warning) -------------------- #
@_register
def gen_lifestyle(ctx: ProactiveContext) -> list[ProactiveItem]:
    out = []
    li = _metric(ctx, "lifestyle_inflation")
    if li and li.get("trend") == "worsening":
        dur = li.get("trend_duration_months") or 0
        out.append(ProactiveItem(
            kind=WARNING, category="lifestyle", title="Spending has been creeping up",
            what_happened=f"Your discretionary spending has risen for {dur} month{'s' if dur != 1 else ''}.",
            why_it_matters="Lifestyle creep quietly reduces how much you can keep each month.",
            what_next="Holding spending near a typical recent month would steady your savings.",
            most_useful_number=None, severity="warning", priority=0.6 + min(0.12, 0.03 * dur),
            eligible_for_notification=False, expires_at=None,
            trigger_reason=f"lifestyle_inflation:{dur}m", evidence=li.get("facts", {}),
        ))
    cp = _metric(ctx, "commitment_pressure")
    if cp and cp.get("trend") == "worsening":
        out.append(ProactiveItem(
            kind=WARNING, category="commitment", title="Recurring commitments are growing",
            what_happened="Your fixed recurring commitments have been climbing relative to income.",
            why_it_matters="Higher fixed costs leave less flexibility when something unexpected comes up.",
            what_next="Reviewing recent recurring additions would free up headroom.",
            most_useful_number=None, severity="warning", priority=0.58,
            eligible_for_notification=False, expires_at=None,
            trigger_reason="commitment_pressure", evidence=cp.get("facts", {}),
        ))
    return out


# --- savings achievement ----------------------------------------------------- #
@_register
def gen_savings_achievement(ctx: ProactiveContext) -> list[ProactiveItem]:
    sc = _metric(ctx, "savings_consistency")
    if not sc or sc.get("score", 0) < 75:
        return []
    return [ProactiveItem(
        kind=ACHIEVEMENT, category="savings", title="You've kept your savings going",
        what_happened="You've been saving consistently.",
        why_it_matters="A steady savings habit is the strongest foundation for your goals.",
        what_next="Worth keeping the streak alive.",
        most_useful_number=None, severity="success", priority=0.42,
        eligible_for_notification=True, expires_at=None,
        trigger_reason="savings_streak", evidence=sc.get("facts", {}),
    )]


# --- opportunity (top recommendation; R2 preference-respecting) ------------- #
@_register
def gen_opportunity(ctx: ProactiveContext) -> list[ProactiveItem]:
    excluded = set(ctx.excluded_levers)
    rec = next((r for r in ctx.recommendations if r.get("lever_key") not in excluded), None)
    if rec is None:
        return []
    return [ProactiveItem(
        kind=OPPORTUNITY, category="recommendation", title=rec.get("title", "An opportunity"),
        what_happened="There's a realistic opportunity to strengthen your position.",
        why_it_matters=rec.get("reasoning", "It would improve where you stand."),
        what_next=rec.get("action", "Consider this option."),
        most_useful_number=(f"Expected benefit: {rec['expected_benefit']}." if rec.get("expected_benefit") else None),
        severity="info", priority=0.5, eligible_for_notification=False, expires_at=None,
        trigger_reason=f"recommendation:{rec.get('lever_key')}", evidence={"recommendation_id": rec.get("recommendation_id")},
    )]
