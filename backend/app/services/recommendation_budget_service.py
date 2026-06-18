"""Recommendation Engine (Budget Intelligence System — Phase 4).

Turns a savings shortfall into Conservative / Balanced / Aggressive option sets the
user chooses from. Cuts follow the locked order (adjustable first; essentials —
food/medicine/housing/utilities — protected unless the user is aggressive-goal AND
insists). Every change shows current→suggested (daily AND monthly), impact, reason
and confidence. When cuts can't close the gap we suggest growing income and explain
honestly why the target is unrealistic. Deterministic — no LLM.
"""

from __future__ import annotations

import calendar as _cal
import uuid
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import LifeStage, OptimizationStyle
from app.schemas.budget_recommendation import (
    GrowIncomeSuggestion,
    RecommendationLine,
    RecommendationSet,
    RecommendationTier,
)
from app.services import calendar_service, feasibility_service, profile_service, reality_service

_Q = Decimal("0.0001")
_ZERO = Decimal("0")
_STUDENTS = {LifeStage.middle_school, LifeStage.high_school, LifeStage.ug_student,
             LifeStage.pg_student, LifeStage.scholarship_student}


def _m(cur: str, v: Decimal) -> str:
    return f"{cur} {v:,.0f}"


def _build_tier(style: str, *, sub_frac: Decimal, life_frac: Decimal, tier_conf: str, difficulty: str,
                title: str, adjustable_lines, gap: Decimal, days: int, cur: str) -> RecommendationTier:
    changes: list[RecommendationLine] = []
    for line in adjustable_lines:
        if line.origin == "recurring":                 # a subscription — deterministic to cut
            cut = (line.monthly * sub_frac).quantize(_Q)
            if cut <= _ZERO:
                continue
            verb = "Cancel" if sub_frac >= 1 else "Reduce"
            changes.append(RecommendationLine(
                label=f"{verb} {line.label}", current_monthly=line.monthly,
                suggested_monthly=(line.monthly - cut).quantize(_Q), monthly_impact=cut,
                reason="Subscriptions are easy to pause or cancel — a clean, reliable saving.",
                confidence="high"))
        else:                                           # lifestyle / fun — show per-day
            cut = (line.monthly * life_frac).quantize(_Q)
            if cut <= _ZERO:
                continue
            cd = (line.monthly / days).quantize(_Q)
            sd = ((line.monthly - cut) / days).quantize(_Q)
            changes.append(RecommendationLine(
                label=f"Trim {line.label.lower()}", current_monthly=line.monthly,
                suggested_monthly=(line.monthly - cut).quantize(_Q), monthly_impact=cut,
                current_daily=cd, suggested_daily=sd,
                reason=f"Bring it from {_m(cur, cd)}/day to {_m(cur, sd)}/day.",
                confidence="low" if life_frac >= Decimal("0.5") else "medium"))
    total = sum((c.monthly_impact for c in changes), _ZERO).quantize(_Q)
    return RecommendationTier(style=style, title=title, total_monthly_impact=total,
                              reaches_goal=total >= gap, confidence=tier_conf, difficulty=difficulty,
                              changes=changes)


def _grow_income(life_stage: LifeStage | None, source_types: set[str], remaining: Decimal, cur: str) -> list[GrowIncomeSuggestion]:
    out: list[GrowIncomeSuggestion] = []
    is_student = life_stage in _STUDENTS
    if "part_time" not in source_types:
        out.append(GrowIncomeSuggestion(
            label="Part-time work",
            detail=f"A few hours a week could cover much of the {_m(cur, remaining)}/month gap.",
            confidence="low"))
    else:
        out.append(GrowIncomeSuggestion(
            label="Extra hours / freelance",
            detail="You already work part-time — a few extra hours or some freelance work could close the gap.",
            confidence="low"))
    if is_student:
        out.append(GrowIncomeSuggestion(
            label="Scholarship / grants",
            detail="Look for scholarships, stipends or assistantships for your course — they don't cost lifestyle.",
            confidence="low"))
    out.append(GrowIncomeSuggestion(
        label="Freelance / side income",
        detail="A small recurring side income is often easier than deep spending cuts.",
        confidence="low"))
    return out


async def recommend(db: AsyncSession, user_id: uuid.UUID, *,
                    target: Decimal | None = None, insist: bool = False) -> RecommendationSet:
    reality = await reality_service.build(db, user_id)
    feas = await feasibility_service.assess(db, user_id)
    profile = await profile_service.get_profile(db, user_id)
    today = await calendar_service.user_today(db, user_id)
    days = _cal.monthrange(today.year, today.month)[1]
    cur = reality.base_currency

    if target is None:
        target = reality.goals.total
    comfortable = feas.comfortable_surplus
    gap = (target - comfortable).quantize(_Q)

    if target <= _ZERO:
        return RecommendationSet(
            base_currency=cur, target_monthly=None, comfortable_surplus=comfortable,
            gap_monthly=_ZERO, on_track=True, tiers=[], grow_income=[],
            summary="No savings goal set yet — tell me a target and I'll build options to reach it.")
    if gap <= _ZERO:
        return RecommendationSet(
            base_currency=cur, target_monthly=target.quantize(_Q), comfortable_surplus=comfortable,
            gap_monthly=_ZERO, on_track=True, tiers=[], grow_income=[],
            summary=f"You can comfortably save {_m(cur, target)} a month — you're on track, no cuts needed.")

    adjustable = reality.adjustable.lines
    tiers = [
        _build_tier("conservative", sub_frac=Decimal("0.5"), life_frac=Decimal("0.15"),
                    tier_conf="high", difficulty="easy", title="Easy wins",
                    adjustable_lines=adjustable, gap=gap, days=days, cur=cur),
        _build_tier("balanced", sub_frac=Decimal("1"), life_frac=Decimal("0.30"),
                    tier_conf="medium", difficulty="moderate", title="Balanced",
                    adjustable_lines=adjustable, gap=gap, days=days, cur=cur),
        _build_tier("aggressive", sub_frac=Decimal("1"), life_frac=Decimal("0.50"),
                    tier_conf="low", difficulty="hard", title="Aggressive",
                    adjustable_lines=adjustable, gap=gap, days=days, cur=cur),
    ]

    # Essentials are protected — only the aggressive-goal user who explicitly insists
    # can opt into trimming food, and even then with a clear health warning.
    style = OptimizationStyle(reality.optimization_style)
    protection_note: str | None = (
        "I'm only suggesting cuts to adjustable spending — food, medicine, rent and utilities "
        "stay protected because they affect your wellbeing.")
    if insist and style == OptimizationStyle.aggressive_goal:
        food = next((ln for ln in reality.protected.lines if "food" in ln.label.lower()), None)
        if food:
            cut = (food.monthly * Decimal("0.10")).quantize(_Q)
            tiers[2].changes.append(RecommendationLine(
                label=f"Reduce {food.label.lower()} (you asked)", current_monthly=food.monthly,
                suggested_monthly=(food.monthly - cut).quantize(_Q), monthly_impact=cut,
                current_daily=(food.monthly / days).quantize(_Q),
                suggested_daily=((food.monthly - cut) / days).quantize(_Q),
                reason="I don't normally recommend reducing food — it may affect your health — but since you asked, this is a small, careful trim.",
                confidence="low", protected=True))
            tiers[2].total_monthly_impact = (tiers[2].total_monthly_impact + cut).quantize(_Q)
            tiers[2].reaches_goal = tiers[2].total_monthly_impact >= gap
        protection_note = ("Because you asked, I've included a careful food trim in the aggressive plan — "
                           "but I'd avoid cutting essentials if there's any other way.")

    grow_income: list[GrowIncomeSuggestion] = []
    why_not: str | None = None
    best = max((t.total_monthly_impact for t in tiers), default=_ZERO)
    if best < gap:
        remaining = (gap - best).quantize(_Q)
        source_types = {s.source_type for s in reality.income_sources}
        grow_income = _grow_income(profile.life_stage, source_types, remaining, cur)
        why_not = (
            f"To save {_m(cur, target)} you'd need about {_m(cur, gap)} more than is comfortably available "
            f"({_m(cur, comfortable)}). Reasonable cuts free up around {_m(cur, best)} — the remaining "
            f"{_m(cur, remaining)} would mean cutting essentials like food, which I don't recommend. "
            f"Let's grow income or aim for about {_m(cur, (comfortable + best).quantize(_Q))} for now.")

    reachable = [t for t in tiers if t.reaches_goal]
    if reachable:
        pick = reachable[0]
        summary = (f"You can reach {_m(cur, target)} with the {pick.style} plan "
                   f"(+{_m(cur, pick.total_monthly_impact)}/month). Pick the level that fits your life.")
    else:
        summary = (f"Even the aggressive plan frees about {_m(cur, best)} of the {_m(cur, gap)} needed — "
                   f"growing income is the realistic path to {_m(cur, target)}.")

    return RecommendationSet(
        base_currency=cur, target_monthly=target.quantize(_Q), comfortable_surplus=comfortable,
        gap_monthly=gap, on_track=False, tiers=tiers, grow_income=grow_income,
        why_not=why_not, essential_protection_note=protection_note, summary=summary)
