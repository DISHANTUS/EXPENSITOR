"""Conversational profile mutation (Budget Intelligence System — Phase 5).

propose() parses a life change and previews it (nothing changes). apply() applies
it, recalculates the Reality + Feasibility engines, and reports the before/after
impact. The user never has to find a settings page — they tell Advary.
"""

from __future__ import annotations

import uuid

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.intelligence.budget import life_changes
from app.models import IncomeSource
from app.models.enums import IncomeKind, IncomeSourceType
from app.schemas.financial_profile import FinancialProfileUpdate
from app.schemas.income_source import IncomeSourceCreate
from app.schemas.profile_mutation import (
    ImpactDiff,
    ProfileChangeProposal,
    ProfileChangeResult,
    ProposedChange,
)
from app.services import (
    calendar_service,
    feasibility_service,
    income_source_service,
    profile_service,
    reality_service,
    settings_service,
)

_SOURCE_LABELS = {"part_time": "Part-time job", "scholarship": "Scholarship", "family_support": "Family support"}
_BAND_WORD = {"very_high": "Very High", "high": "High", "medium": "Medium", "low": "Low", "very_low": "Very Low"}


def _proposed(changes: list[life_changes.Change]) -> list[ProposedChange]:
    return [ProposedChange(target=c.target, field=c.field,
                           value=None if c.value is None else str(c.value), label=c.label)
            for c in changes]


async def propose(db: AsyncSession, user_id: uuid.UUID, text: str) -> ProfileChangeProposal:
    today = await calendar_service.user_today(db, user_id)
    changes = life_changes.parse(text, today)
    if not changes:
        return ProfileChangeProposal(
            understood=False, changes=[], preview=(
                "I didn't catch a change I can make to your profile. Try things like "
                "\"I moved to Tokyo\", \"my rent is now 80000\", \"I got a part-time job\", "
                "or \"my family stopped sending money\"."))
    needs_amount = any(c.target == "income_add" and c.value is None for c in changes)
    lines = "; ".join(c.label for c in changes)
    preview = f"Got it. I'll update: {lines}."
    if needs_amount:
        preview += " (Tell me the monthly amount for the income I should add.)"
    preview += " Want me to apply this?"
    return ProfileChangeProposal(understood=True, changes=_proposed(changes), preview=preview, needs_amount=needs_amount)


async def apply(db: AsyncSession, user_id: uuid.UUID, text: str) -> ProfileChangeResult:
    today = await calendar_service.user_today(db, user_id)
    changes = life_changes.parse(text, today)

    before_r = await reality_service.build(db, user_id)
    before_f = await feasibility_service.assess(db, user_id)

    profile_updates: dict = {}
    applied: list[life_changes.Change] = []
    base_currency = before_r.base_currency

    for c in changes:
        if c.target == "profile":
            profile_updates[c.field] = c.value
            applied.append(c)
        elif c.target == "future_move":
            profile_updates["moving_country"] = True
            profile_updates["future_country"] = c.value
            if c.extra.get("year"):
                profile_updates["future_move_year"] = c.extra["year"]
            applied.append(c)
        elif c.target == "income_add" and c.value is not None:
            await income_source_service.create(db, user_id, IncomeSourceCreate(
                label=_SOURCE_LABELS.get(c.field, c.field.replace("_", " ").title()),
                source_type=IncomeSourceType(c.field), kind=IncomeKind.recurring,
                original_amount=c.value, original_currency=base_currency, recurrence_day=1))
            applied.append(c)
        elif c.target == "income_remove":
            await db.execute(update(IncomeSource).where(
                IncomeSource.user_id == user_id, IncomeSource.deleted_at.is_(None),
                IncomeSource.source_type == IncomeSourceType(c.field)).values(is_active=False))
            await db.commit()
            applied.append(c)

    if profile_updates:
        await profile_service.update_profile(db, user_id, FinancialProfileUpdate(**profile_updates))

    after_r = await reality_service.build(db, user_id)
    after_f = await feasibility_service.assess(db, user_id)

    notes: list[str] = []
    if abs(after_r.housing_ratio - before_r.housing_ratio) >= 0.01:
        notes.append(f"Housing went from {before_r.housing_ratio*100:.0f}% to "
                     f"{after_r.housing_ratio*100:.0f}% of your income.")
    if before_f.overall_band != after_f.overall_band:
        notes.append(f"Savings probability moved from {_BAND_WORD.get(before_f.overall_band, before_f.overall_band)} "
                     f"to {_BAND_WORD.get(after_f.overall_band, after_f.overall_band)}.")
    if after_f.comfortable_surplus != before_f.comfortable_surplus:
        cur = after_r.base_currency
        notes.append(f"You now have about {cur} {after_f.comfortable_surplus:,.0f} comfortably free each month "
                     f"(was {cur} {before_f.comfortable_surplus:,.0f}).")

    impact = ImpactDiff(
        housing_ratio_before=before_r.housing_ratio, housing_ratio_after=after_r.housing_ratio,
        probability_before=before_f.overall_band, probability_after=after_f.overall_band,
        comfortable_surplus_before=before_f.comfortable_surplus,
        comfortable_surplus_after=after_f.comfortable_surplus, notes=notes)
    msg = "Done — I've updated your profile." + (f" {notes[0]}" if notes else "")
    return ProfileChangeResult(applied=_proposed(applied), impact=impact, message=msg)
