"""Forecast Engine (4b-4) — Future Planning, not Goal Math.

Orchestrates the existing deterministic projection stack into forward-looking
answers: goal ETAs, what-if levers, opportunity cost, life-event affordability,
and a three-path "Future Me". Reuses `projection_service`/`engine`/`goal_feasibility`/
`affordability`/`analytics_service` — adds NO new math primitives and NO LLM.

Honesty rules (hard, non-negotiable):
  * Never fabricate a completion date when monthly savings are <= 0 — return a
    `negative` forecast and offer recovery.
  * Never fabricate a date when there is no usable spending history — return
    `insufficient`.
"""

from __future__ import annotations

import math
import uuid
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.intelligence.projection import affordability
from app.intelligence.projection.calendar_utils import days_in_month
from app.intelligence.projection.scenario import Scenario
from app.models import Income, Receivable, RecurringRule, SavingsGoal
from app.models.enums import ReceivableStatus, RecurringRuleType, SavingsGoalStatus
from app.schemas.advisor_chat import ChatContext, ChatOption
from app.schemas.explain import EvidenceItem
from app.schemas.forecast import (
    Forecast,
    ForecastStory,
    FutureMe,
    GoalRef,
    Lever,
    LeverChip,
    OpportunityCost,
    ScenarioPath,
    TimelineCandidate,
)
from app.services import (
    advice_memory_service,
    analytics_service,
    life_lesson_service,
    projection_service,
    settings_service,
)

_Q = Decimal("0.01")
_ZERO = Decimal("0")
WINDOW_DAYS = 90

# Standard forecast follow-ups (the "make 4b-5 easier" set).
_FOLLOW_UPS = [
    ChatOption(label="See biggest obstacles", message="show biggest obstacles"),
    ChatOption(label="See recovery plan", message="show recovery plan"),
    ChatOption(label="Compare goals", message="compare goals"),
    ChatOption(label="Show opportunity costs", message="show opportunity costs"),
    ChatOption(label="Show Future Me", message="show future me"),
]


# --------------------------------------------------------------------------- #
# small deterministic helpers
# --------------------------------------------------------------------------- #
def _q(amount: Decimal) -> Decimal:
    return Decimal(amount).quantize(_Q, rounding=ROUND_HALF_UP)


def _add_months(anchor: date, months: int) -> date:
    total = anchor.month - 1 + months
    year = anchor.year + total // 12
    month = total % 12 + 1
    return date(year, month, min(anchor.day, days_in_month(year, month)))


def _month_label(when: date) -> str:
    return when.strftime("%B %Y")


def _eta(remaining: Decimal, monthly_net: Decimal, today: date) -> date | None:
    """ETA by savings-rate extrapolation. None when unreachable (honesty rule)."""
    if remaining <= 0:
        return today
    if monthly_net <= 0:
        return None
    months = max(1, math.ceil(float(remaining) / float(monthly_net)))
    return _add_months(today, months)


async def _surface_lesson(db, user_id, context: str, today: date) -> str | None:
    """Surface a CONFIRMED lesson the user taught, relevant to this moment (req 8)."""
    hits = await life_lesson_service.relevant(db, user_id, context=context, today=today, limit=1)
    if not hits:
        return None
    await life_lesson_service.mark_surfaced(db, hits[0])
    return f"A lesson you’ve taught me before: {hits[0].lesson}"


def _confidence(observed_days: int) -> tuple[str, str | None, str | None]:
    """DATA-sufficiency confidence (req 5) — distinct from goal probability."""
    if observed_days <= 0:
        return "insufficient", None, "I don’t have any spending history yet."
    if observed_days < 14:
        return "low", "may", f"Low-confidence forecast — I only have {observed_days} days of spending history."
    if observed_days < 60:
        return "medium", "often", f"Medium-confidence forecast — based on {observed_days} days of history."
    return "high", "consistently", f"High-confidence forecast — based on {observed_days} days of history."


# --------------------------------------------------------------------------- #
# observed savings rate (the primary forecast driver)
# --------------------------------------------------------------------------- #
async def _monthly_income(db: AsyncSession, user_id: uuid.UUID, today: date, settings) -> Decimal:
    start = today.fromordinal(today.toordinal() - (WINDOW_DAYS - 1))
    total = await db.scalar(
        select(func.coalesce(func.sum(Income.converted_amount), 0)).where(
            Income.user_id == user_id, Income.deleted_at.is_(None),
            Income.received_date >= start, Income.received_date <= today,
        )
    ) or _ZERO
    if total > 0:
        return (Decimal(total) / WINDOW_DAYS) * 30
    if settings.monthly_income_estimate:
        return Decimal(settings.monthly_income_estimate)
    return _ZERO


async def _savings_rate(db, user_id, scenario: Scenario, settings):
    """Return (monthly_income, monthly_spend, monthly_net) from observed behavior."""
    monthly_spend = scenario.spending.mu * 30
    monthly_income = await _monthly_income(db, user_id, scenario.today, settings)
    return _q(monthly_income), _q(monthly_spend), _q(monthly_income - monthly_spend)


# --------------------------------------------------------------------------- #
# levers
# --------------------------------------------------------------------------- #
async def _subscriptions(db, user_id) -> list[RecurringRule]:
    return list((await db.execute(
        select(RecurringRule).where(
            RecurringRule.user_id == user_id, RecurringRule.deleted_at.is_(None),
            RecurringRule.is_active.is_(True), RecurringRule.rule_type == RecurringRuleType.subscription,
        ).order_by(RecurringRule.converted_amount.desc())
    )).scalars().all())


def _lever_chips(category_sums: dict[str, Decimal], subscriptions: list[RecurringRule]) -> list[LeverChip]:
    """Visual what-if chips built from the user's ACTUAL top categories + subs."""
    chips: list[LeverChip] = []
    top = sorted(category_sums.items(), key=lambda kv: kv[1], reverse=True)
    for label, _ in top[:2]:
        chips.append(LeverChip(label=f"{label} −10%", ref=f"category:{label}:-10"))
        chips.append(LeverChip(label=f"{label} −20%", ref=f"category:{label}:-20"))
    if subscriptions:
        chips.append(LeverChip(label="Cancel subscriptions", ref="sub:*:cancel"))
    chips.append(LeverChip(label="Save +1000", ref="save:+1000"))
    chips.append(LeverChip(label="Save +2000", ref="save:+2000"))
    return chips


async def _parse_levers(db, user_id, refs: list[str], category_sums: dict[str, Decimal],
                        subscriptions: list[RecurringRule]):
    """Resolve lever refs to (applied levers, extra_monthly_saving, extra_remaining)."""
    applied: list[Lever] = []
    extra_monthly = _ZERO
    extra_remaining = _ZERO  # +ve pushes the goal later (e.g. money you won't get back)
    cat_lower = {k.lower(): (k, v) for k, v in category_sums.items()}

    for raw in refs:
        ref = raw.strip()
        parts = ref.split(":")
        head = parts[0].lower() if parts else ""

        if head == "category" and len(parts) >= 3:
            name, op = parts[1], parts[2]
            pct = abs(Decimal(op.replace("%", "")))
            match = cat_lower.get(name.lower())
            if not match:
                match = next((v for k, v in cat_lower.items() if name.lower() in k), None)
            if match:
                label, monthly = match
                delta = _q(monthly * pct / 100)
                extra_monthly += delta
                applied.append(Lever(ref=ref, label=f"{label} −{int(pct)}%", kind="category", monthly_delta=delta))

        elif head == "sub" and len(parts) >= 3:
            target = parts[1]
            if target == "*":
                amount = _q(sum((s.converted_amount for s in subscriptions), _ZERO))
                extra_monthly += amount
                applied.append(Lever(ref=ref, label="Cancel subscriptions", kind="subscription", monthly_delta=amount))
            else:
                sub = next((s for s in subscriptions if target.lower() in s.label.lower()), None)
                if sub:
                    amount = _q(sub.converted_amount)
                    extra_monthly += amount
                    applied.append(Lever(ref=ref, label=f"Cancel {sub.label}", kind="subscription", monthly_delta=amount))

        elif head == "save" and len(parts) >= 2:
            amount = _q(Decimal(parts[1].replace("+", "")))
            extra_monthly += amount
            applied.append(Lever(ref=ref, label=f"Save +{int(amount)}", kind="savings", monthly_delta=amount))

        elif head == "recv" and len(parts) >= 2:
            name = parts[1]
            outstanding = await db.scalar(
                select(func.coalesce(func.sum(Receivable.converted_amount), 0)).where(
                    Receivable.user_id == user_id, Receivable.deleted_at.is_(None),
                    Receivable.status == ReceivableStatus.pending,
                    Receivable.source_name.ilike(f"%{name}%"),
                )
            ) or _ZERO
            outstanding = _q(Decimal(outstanding))
            extra_remaining += outstanding
            applied.append(Lever(ref=ref, label=f"If {name.title()} never repays", kind="receivable",
                                 monthly_delta=_ZERO))

        elif head == "spending":
            applied.append(Lever(ref=ref, label="Keep spending as-is", kind="baseline", monthly_delta=_ZERO))

    return applied, _q(extra_monthly), _q(extra_remaining)


# --------------------------------------------------------------------------- #
# paths / story / opportunity cost
# --------------------------------------------------------------------------- #
def _path(mode: str, label: str, monthly_net: Decimal, remaining: Decimal, today: date, narrative: str) -> ScenarioPath:
    eta = _eta(remaining, monthly_net, today)
    return ScenarioPath(mode=mode, label=label, eta=eta, monthly_rate=_q(monthly_net), narrative=narrative)


def _future_me(monthly_net, monthly_spend, top_cat, remaining, today, currency) -> FutureMe:
    trim = _q((top_cat[1] if top_cat else monthly_spend) * Decimal("0.15"))
    creep = _q(monthly_spend * Decimal("0.10"))
    cur_eta = _eta(remaining, monthly_net, today)

    current = _path("current", "Current Path", monthly_net, remaining, today,
                    "You keep your current spending and saving habits."
                    + (f" {top_cat[0]} stays your largest cost." if top_cat else ""))
    opt_label = top_cat[0] if top_cat else "spending"
    optimistic = _path("optimistic", "Optimistic Path", monthly_net + trim, remaining, today,
                       f"You keep saving and trim {opt_label} a little "
                       f"(about {analytics_service._fmt(trim, currency)}/month).")
    conservative = _path("conservative", "Conservative Path", monthly_net - creep, remaining, today,
                         "Spending creeps up and a little less goes to savings each month.")
    _ = cur_eta
    return FutureMe(current_path=current, optimistic_path=optimistic, conservative_path=conservative)


def _opportunity_costs(applied: list[Lever], baseline_eta, monthly_net, remaining, today, currency) -> list[OpportunityCost]:
    out: list[OpportunityCost] = []
    for lever in applied:
        if lever.kind == "baseline":
            continue
        if lever.kind == "receivable":
            out.append(OpportunityCost(lever_label=lever.label, summary=f"{lever.label}: your goal would arrive later."))
            continue
        annual = _q(lever.monthly_delta * 12)
        days_earlier = None
        if baseline_eta is not None and monthly_net > 0 and lever.monthly_delta > 0:
            new_eta = _eta(remaining, monthly_net + lever.monthly_delta, today)
            if new_eta is not None:
                days_earlier = max(0, (baseline_eta - new_eta).days)
        if days_earlier:
            summary = f"{lever.label}: saves {analytics_service._fmt(annual, currency)}/yr — goal arrives {days_earlier} days earlier."
        else:
            summary = f"{lever.label}: saves {analytics_service._fmt(annual, currency)}/yr."
        out.append(OpportunityCost(lever_label=lever.label, annual_savings=annual, days_earlier=days_earlier, summary=summary))
    return out


def _story(goal_name, currency, eta, opt_eta, top_cat) -> ForecastStory:
    beginning = (f"At your current rate, {goal_name} completes around {_month_label(eta)}." if eta
                 else f"At your current rate, {goal_name} isn’t reachable yet — savings need to turn positive first.")
    if top_cat:
        annual_trim = _q(top_cat[1] * Decimal("0.15") * 12)
        middle = (f"The biggest factor slowing progress is {top_cat[0]} "
                  f"({analytics_service._fmt(top_cat[1], currency)}/month). Reducing it 15% would save about "
                  f"{analytics_service._fmt(annual_trim, currency)} a year.")
    else:
        middle = "I’ll spot your biggest slowing factor once there’s a bit more spending history."
    end = (f"If you trim it, you could reach {goal_name} by {_month_label(opt_eta)}." if opt_eta and eta and opt_eta < eta
           else "Small, steady changes move the date the most.")
    return ForecastStory(beginning=beginning, middle=middle, end=end)


# --------------------------------------------------------------------------- #
# goal loading
# --------------------------------------------------------------------------- #
async def _active_goals(db, user_id) -> list[SavingsGoal]:
    rows = (await db.execute(
        select(SavingsGoal).where(
            SavingsGoal.user_id == user_id, SavingsGoal.deleted_at.is_(None),
            SavingsGoal.status == SavingsGoalStatus.active,
        )
    )).scalars().all()
    return sorted(rows, key=lambda g: (g.target_date is None, g.target_date or date.max))


def _progress_pct(progress: Decimal, target: Decimal) -> float | None:
    if target <= 0:
        return None
    return float(min(Decimal("100"), max(_ZERO, progress / target * 100)).quantize(Decimal("0.1")))


# --------------------------------------------------------------------------- #
# public entry
# --------------------------------------------------------------------------- #
async def forecast(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    question: str | None = None,
    goal_id: str | None = None,
    levers: list[str] | None = None,
    target_date: date | None = None,
    expected_cost: Decimal | None = None,
    event_type: str | None = None,
    session: ChatContext | None = None,
) -> Forecast:
    levers = levers or []
    ctx = session or ChatContext()
    settings = await settings_service.get_settings(db, user_id)
    currency = settings.base_currency
    scenario = await projection_service.get_scenario(db, user_id)
    today = scenario.today

    monthly_income, monthly_spend, monthly_net = await _savings_rate(db, user_id, scenario, settings)
    conf, conf_word, conf_note = _confidence(scenario.spending.observed_days)
    month_end = today.replace(day=days_in_month(today.year, today.month))
    category_sums = await analytics_service._category_sums(  # noqa: SLF001
        db, user_id, today.replace(day=1), month_end)
    top_cat = max(category_sums.items(), key=lambda kv: kv[1]) if category_sums else None
    subscriptions = await _subscriptions(db, user_id)
    chips = _lever_chips(category_sums, subscriptions)

    # Life-event affordability (req 1/6) takes precedence when a cost is given.
    if expected_cost is not None and target_date is not None:
        return await _life_event(db, user_id, scenario, settings, currency, conf, conf_word, conf_note,
                                 expected_cost, target_date, event_type, chips, ctx, question=question)

    goals = await _active_goals(db, user_id)
    goal_refs = [
        GoalRef(id=str(g.id), name=g.name,
                eta=_eta(max(_ZERO, g.converted_amount - scenario.current_balance), monthly_net, today),
                progress_pct=_progress_pct(scenario.current_balance, g.converted_amount))
        for g in goals
    ]

    # Compare-goals view (req 2).
    if question and "compare goal" in question.lower():
        return _compare_goals(goal_refs, currency, conf, conf_word, conf_note, chips, ctx)

    # No goal: still deliver opportunity cost (req 5) + negative detection (req 6).
    if not goals:
        return _no_goal(monthly_net, subscriptions, chips, currency, conf, conf_word, conf_note, ctx)

    # Pick the focus goal.
    goal = next((g for g in goals if goal_id and str(g.id) == goal_id), goals[0])
    target = Decimal(goal.converted_amount)
    progress = scenario.current_balance
    remaining = max(_ZERO, target - progress)

    applied, extra_monthly, extra_remaining = await _parse_levers(
        db, user_id, levers, category_sums, subscriptions)
    eff_net = monthly_net + extra_monthly
    eff_remaining = remaining + extra_remaining

    # Negative-savings detection (req 6) — honesty rule, no fabricated dates.
    if eff_net <= 0:
        return _negative(monthly_net, monthly_income, monthly_spend, goal.name, currency,
                         conf, conf_word, conf_note, top_cat, chips, ctx)

    eta = _eta(eff_remaining, eff_net, today)
    opt_trim = _q((top_cat[1] if top_cat else monthly_spend) * Decimal("0.15"))
    opt_eta = _eta(eff_remaining, eff_net + opt_trim, today)
    future = _future_me(eff_net, monthly_spend, top_cat, eff_remaining, today, currency)
    opp = _opportunity_costs(applied, eta, eff_net, eff_remaining, today, currency)
    # Non-goal opportunity cost surfaces too: show the priciest subscription's annual cost.
    if subscriptions and not any(o.lever_label.startswith("Cancel") for o in opp):
        s = subscriptions[0]
        opp.append(OpportunityCost(lever_label=s.label, annual_savings=_q(s.converted_amount * 12),
                                   summary=f"{s.label}: {analytics_service._fmt(s.converted_amount, currency)}/month "
                                           f"= {analytics_service._fmt(_q(s.converted_amount * 12), currency)}/year."))

    headline = _month_label(eta) if eta else "Not reachable at the current rate"
    reasoning = (f"Based on your savings rate of {analytics_service._fmt(eff_net, currency)}/month, "
                 f"a goal of {analytics_service._fmt(target, currency)}, and current progress of "
                 f"{analytics_service._fmt(progress, currency)}.")
    evidence = [
        EvidenceItem(label="Current savings rate", value=f"{analytics_service._fmt(eff_net, currency)}/month"),
        EvidenceItem(label="Goal amount", value=analytics_service._fmt(target, currency)),
        EvidenceItem(label="Current progress", value=analytics_service._fmt(progress, currency)),
        EvidenceItem(label="Remaining", value=analytics_service._fmt(eff_remaining, currency)),
    ]
    timeline = [TimelineCandidate(label=f"Forecasted {goal.name} completion", date=eta)] if eta else []

    # Remember this forecast so the companion can later ask whether it came true
    # (4b-5a learning loop). Importance-gated + deduped inside the service.
    if eta is not None:
        await advice_memory_service.record_advice(
            db, user_id, kind="forecast", subject_type="goal", subject_id=goal.id, subject_label=goal.name,
            claim=f"reach {goal.name} around {headline}", expected_value=target, expected_date=eta,
            assumptions={"monthly_net": str(eff_net), "progress": str(progress), "forecast_type": "goal_eta"},
            base_currency=currency, today=today,
        )

    surfaced = await _surface_lesson(db, user_id, f"{goal.name} {question or ''}", today)

    return Forecast(
        kind="what_if" if applied else "goal",
        headline=headline, currency=currency, confidence=conf, confidence_word=conf_word, confidence_note=conf_note,
        reasoning=reasoning, scenarios=[future.current_path, future.optimistic_path, future.conservative_path],
        evidence=evidence, opportunity_costs=opp, story=_story(goal.name, currency, eta, opt_eta, top_cat),
        levers=chips, applied_levers=applied, timeline_candidates=timeline, goals=goal_refs, future_me=future,
        follow_ups=_FOLLOW_UPS, surfaced_lesson=surfaced, explain_ref=f"category:{top_cat[0]}" if top_cat else None,
        session=ctx.model_copy(update={"last_explain_ref": f"category:{top_cat[0]}" if top_cat else ctx.last_explain_ref}),
    )


# --------------------------------------------------------------------------- #
# specialized builders
# --------------------------------------------------------------------------- #
def _negative(monthly_net, monthly_income, monthly_spend, goal_name, currency,
              conf, conf_word, conf_note, top_cat, chips, ctx) -> Forecast:
    headline = "Your balance is decreasing"
    reasoning = (f"At your current rate, you spend {analytics_service._fmt(monthly_spend, currency)}/month against "
                 f"{analytics_service._fmt(monthly_income, currency)}/month income — a net of "
                 f"{analytics_service._fmt(monthly_net, currency)}. I can’t estimate a completion date for "
                 f"{goal_name} until savings turn positive.")
    evidence = [
        EvidenceItem(label="Monthly income", value=analytics_service._fmt(monthly_income, currency)),
        EvidenceItem(label="Monthly spending", value=analytics_service._fmt(monthly_spend, currency)),
        EvidenceItem(label="Net per month", value=analytics_service._fmt(monthly_net, currency)),
    ]
    follow_ups = [
        ChatOption(label="Recovery plan", message="show recovery plan"),
        ChatOption(label="Biggest expenses", message="show biggest obstacles"),
    ]
    if top_cat:
        follow_ups.append(ChatOption(label=f"Reduce {top_cat[0]} 10%", message=f"what if i reduce {top_cat[0]} by 10%"))
    follow_ups.append(ChatOption(label="Cancel subscriptions", message="what if i cancel my subscriptions"))
    return Forecast(
        kind="negative", headline=headline, currency=currency, confidence=conf, confidence_word=conf_word,
        confidence_note=conf_note, reasoning=reasoning, evidence=evidence, levers=chips, follow_ups=follow_ups,
        session=ctx,
    )


def _no_goal(monthly_net, subscriptions, chips, currency, conf, conf_word, conf_note, ctx) -> Forecast:
    opp = [OpportunityCost(lever_label=s.label, annual_savings=_q(s.converted_amount * 12),
                           summary=f"{s.label}: {analytics_service._fmt(s.converted_amount, currency)}/month "
                                   f"= {analytics_service._fmt(_q(s.converted_amount * 12), currency)}/year.")
           for s in subscriptions[:5]]
    headline = ("You don’t have a savings goal yet" if monthly_net > 0
                else "Your balance is decreasing and you have no goal set")
    reasoning = (f"Your net savings rate is {analytics_service._fmt(monthly_net, currency)}/month. "
                 "Set a goal in Budget Setup and I’ll project a completion date across scenarios. "
                 + ("Meanwhile, here’s what your recurring costs add up to per year." if opp else ""))
    return Forecast(
        kind="insufficient", headline=headline, currency=currency, confidence=conf, confidence_word=conf_word,
        confidence_note=conf_note, reasoning=reasoning, opportunity_costs=opp, levers=chips,
        follow_ups=[ChatOption(label="Show opportunity costs", message="show opportunity costs"),
                    ChatOption(label="See biggest obstacles", message="show biggest obstacles")],
        session=ctx,
    )


def _compare_goals(goal_refs, currency, conf, conf_word, conf_note, chips, ctx) -> Forecast:
    if not goal_refs:
        return Forecast(kind="insufficient", headline="No goals to compare", currency=currency, confidence="high",
                        reasoning="You don’t have any active savings goals yet.", session=ctx)
    lines = [f"• {g.name}: {(_month_label(g.eta) if g.eta else 'not reachable at the current rate')}" for g in goal_refs]
    timeline = [TimelineCandidate(label=f"Forecasted {g.name} completion", date=g.eta) for g in goal_refs if g.eta]
    return Forecast(
        kind="compare_goals", headline="Your goals, side by side", currency=currency, confidence=conf,
        confidence_word=conf_word, confidence_note=conf_note,
        reasoning="\n".join(lines), goals=goal_refs, timeline_candidates=timeline, levers=chips,
        follow_ups=_FOLLOW_UPS, session=ctx,
    )


async def _life_event(db, user_id, scenario, settings, currency, conf, conf_word, conf_note,
                      expected_cost, target_date, event_type, chips, ctx, *, question=None) -> Forecast:
    result = affordability.evaluate(scenario, Decimal(expected_cost), target_date)
    label = (event_type or "this").strip().title()
    verdict_word = {"affordable": "Yes", "conditional": "Probably", "unaffordable": "Not yet"}.get(result.verdict, "Maybe")
    headline = f"{verdict_word} — {label} on {target_date.strftime('%d %b %Y')}"
    expected_after = result.min_after.get("expected", _ZERO)
    reasoning = (f"A {analytics_service._fmt(Decimal(expected_cost), currency)} cost on "
                 f"{target_date.strftime('%d %b %Y')} leaves an expected low-point balance of "
                 f"{analytics_service._fmt(expected_after, currency)} afterward.")
    evidence = [
        EvidenceItem(label="Expected cost", value=analytics_service._fmt(Decimal(expected_cost), currency)),
        EvidenceItem(label="Lowest balance after (expected)", value=analytics_service._fmt(expected_after, currency)),
        EvidenceItem(label="Worst-case low point", value=analytics_service._fmt(result.min_after.get("worst", _ZERO), currency)),
        EvidenceItem(label="Verdict", value=result.verdict),
    ]
    surfaced = await _surface_lesson(db, user_id, f"{event_type or ''} {label} {question or ''}", scenario.today)
    return Forecast(
        kind="life_event", headline=headline, currency=currency, confidence=conf, confidence_word=conf_word,
        confidence_note=conf_note, reasoning=reasoning, evidence=evidence, levers=chips,
        timeline_candidates=[TimelineCandidate(label=f"Planned {label}", date=target_date, kind="plan")],
        follow_ups=_FOLLOW_UPS, surfaced_lesson=surfaced, session=ctx,
    )
