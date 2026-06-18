"""Reality Engine (Budget Intelligence System — Phase 2).

Builds the monthly money reality from the user's PROFILE + income sources +
recurring commitments + savings goals, grouped into the 4 buckets. This is the
deterministic foundation the feasibility waterfall (Phase 3) and recommendation
engine (Phase 4) reason over. Survival (essentials) is computed before savings.
"""

from __future__ import annotations

import calendar as _cal
import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.intelligence.budget import buckets
from app.models import IncomeSource, RecurringRule, SavingsGoal
from app.models.enums import ExpenseBucket, FoodSituation, IncomeKind, SavingsGoalKind, SavingsGoalStatus
from app.schemas.budget_reality import BudgetLine, BucketBreakdown, BudgetReality, IncomeLine
from app.services import calendar_service, profile_service, settings_service

_Q = Decimal("0.0001")
_ZERO = Decimal("0")


def _total(lines: list[BudgetLine]) -> Decimal:
    return sum((ln.monthly for ln in lines), _ZERO).quantize(_Q)


async def build(db: AsyncSession, user_id: uuid.UUID) -> BudgetReality:
    settings = await settings_service.get_settings(db, user_id)
    profile = await profile_service.get_profile(db, user_id)
    today = await calendar_service.user_today(db, user_id)
    days = _cal.monthrange(today.year, today.month)[1]

    # --- Income, broken out by source ---
    sources = (await db.execute(
        select(IncomeSource).where(
            IncomeSource.user_id == user_id, IncomeSource.deleted_at.is_(None),
            IncomeSource.is_active.is_(True), IncomeSource.kind == IncomeKind.recurring,
        ).order_by(IncomeSource.converted_amount.desc())
    )).scalars().all()
    income_lines = [
        IncomeLine(label=s.label, source_type=s.source_type.value, monthly=s.converted_amount.quantize(_Q))
        for s in sources
    ]
    if not income_lines and settings.monthly_income_estimate:
        income_lines = [IncomeLine(label="Income", source_type="other",
                                   monthly=settings.monthly_income_estimate.quantize(_Q))]
    income_total = sum((ln.monthly for ln in income_lines), _ZERO).quantize(_Q)

    # --- Recurring commitments, classified into buckets ---
    rules = (await db.execute(
        select(RecurringRule).where(
            RecurringRule.user_id == user_id, RecurringRule.deleted_at.is_(None),
            RecurringRule.is_active.is_(True),
        )
    )).scalars().all()

    protected: list[BudgetLine] = []
    committed: list[BudgetLine] = []
    adjustable: list[BudgetLine] = []

    # Profile-derived essentials. Rent is PROTECTED housing (cut last, like food).
    # Food from onboarding is a recurring essential ONLY when the user mostly eats
    # out (a genuinely committed food spend). For home-cooked / mixed / other,
    # food style is lifestyle info — not a daily budget — so it must NOT inflate
    # Essential Living; real food spending is learned from logged expenses instead.
    if profile.food_situation == FoodSituation.mostly_outside:
        if profile.food_monthly:
            protected.append(BudgetLine(label="Food (eating out)", monthly=profile.food_monthly.quantize(_Q),
                                        origin="profile", kind="essential_living"))
        elif profile.food_daily:
            protected.append(BudgetLine(label="Food (eating out)", monthly=(profile.food_daily * days).quantize(_Q),
                                        origin="profile", kind="essential_living"))
    if profile.transport_monthly:
        protected.append(BudgetLine(label="Transport", monthly=profile.transport_monthly.quantize(_Q),
                                    origin="profile", kind="essential_living"))
    if profile.rent_monthly:
        protected.append(BudgetLine(label="Rent", monthly=profile.rent_monthly.quantize(_Q),
                                    origin="profile", kind="housing"))
    if profile.lifestyle_monthly:
        adjustable.append(BudgetLine(label="Lifestyle & fun", monthly=profile.lifestyle_monthly.quantize(_Q),
                                     origin="profile"))

    _by_bucket = {ExpenseBucket.protected: protected, ExpenseBucket.committed: committed,
                  ExpenseBucket.adjustable: adjustable}
    for r in rules:
        bucket = buckets.bucket_for_recurring(r.rule_type)
        kind = buckets.protected_kind(r.label) if bucket == ExpenseBucket.protected else None
        _by_bucket[bucket].append(
            BudgetLine(label=r.label, monthly=r.converted_amount.quantize(_Q), origin="recurring", kind=kind))

    # --- Goals (monthly savings targets) ---
    goal_rows = (await db.execute(
        select(SavingsGoal).where(
            SavingsGoal.user_id == user_id, SavingsGoal.deleted_at.is_(None),
            SavingsGoal.status == SavingsGoalStatus.active,
            SavingsGoal.kind == SavingsGoalKind.monthly_target,
        )
    )).scalars().all()
    goals = [BudgetLine(label=g.name, monthly=g.converted_amount.quantize(_Q), origin="goal") for g in goal_rows]

    protected_total = _total(protected)
    committed_total = _total(committed)
    essentials_total = (protected_total + committed_total).quantize(_Q)
    housing_total = _total([ln for ln in protected if ln.kind == "housing"])
    housing_ratio = float((housing_total / income_total).quantize(Decimal("0.001"))) if income_total > _ZERO else 0.0

    return BudgetReality(
        base_currency=settings.base_currency,
        optimization_style=profile.optimization_style.value,
        income_sources=income_lines,
        income_total=income_total,
        protected=BucketBreakdown(bucket="protected", lines=protected, total=protected_total),
        committed=BucketBreakdown(bucket="committed", lines=committed, total=committed_total),
        adjustable=BucketBreakdown(bucket="adjustable", lines=adjustable, total=_total(adjustable)),
        goals=BucketBreakdown(bucket="goal", lines=goals, total=_total(goals)),
        essentials_total=essentials_total,
        available_after_essentials=(income_total - essentials_total).quantize(_Q),
        housing_total=housing_total,
        housing_ratio=housing_ratio,
    )
