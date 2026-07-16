"""Daily-granularity spending-pattern detection (learning-loop extension).

The existing BehavioralProfile (C6) reasons in monthly buckets only — this
module adds a day-level view: per-category rolling averages, and detection of
a SUSTAINED shift (this week trending meaningfully away from the prior
baseline), as distinct from ordinary day-to-day noise. A detected shift
becomes an AdviceMemory row via the existing 4b-5a loop, so the follow-up,
answer, and life-lesson machinery all just work unchanged — this module only
decides WHEN to ask, not how the asking/answering/remembering works.

Derive-on-read, like everything else here: call detect_and_record_shifts()
from wherever Home/brief data is already being computed. Calling this on
every load is safe: record_advice()'s own dedup covers a still-PENDING row,
and this module additionally skips re-raising the same subject if it was
touched (answered or not) within _RECENT_TOUCH_DAYS — otherwise, since the
underlying weekly averages don't change between page loads, answering a
shift question would immediately get asked again on the very next Home open.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AdviceMemory, Expense
from app.models.enums import AdviceKind, AdviceStatus
from app.services import advice_memory_service, category_service

_MIN_HISTORY_DAYS = 14           # don't start pattern-shift detection before this much history exists
_RECENT_WINDOW_DAYS = 7          # "this week"
_RECENT_TOUCH_DAYS = 14          # don't re-raise a subject answered/asked this recently
_BASELINE_WINDOW_DAYS = 14       # the 14 days immediately before the recent window
_SHIFT_THRESHOLD = Decimal("0.30")       # 30% relative deviation counts as a shift
_MIN_BASELINE_DAILY_AVG = Decimal("1")   # ignore near-zero baselines (avoids noisy % on tiny numbers)
# A "per-day average" is only a meaningful model for categories the user
# actually spends on most days. Rent hits once a month, so in a week it has no
# rent — which a naive daily average reads as "rent dropped 100%!". Requiring
# the category to be active on a good share of BASELINE days keeps episodic
# spending (rent, EMIs, insurance) out of the daily model entirely; month-scale
# movement is already the BehavioralProfile's job (category_volatility).
_MIN_ACTIVE_DAY_RATIO = Decimal("0.5")


async def has_min_history(db: AsyncSession, user_id: uuid.UUID, today: date) -> bool:
    earliest = await db.scalar(
        select(func.min(Expense.expense_date)).where(
            Expense.user_id == user_id, Expense.deleted_at.is_(None))
    )
    return earliest is not None and (today - earliest).days >= _MIN_HISTORY_DAYS


async def _category_daily_avg(
    db: AsyncSession, user_id: uuid.UUID, start: date, end: date
) -> dict[uuid.UUID | None, Decimal]:
    """Average per-day spend by category over [start, end] — divided by the
    number of days in the window (not just days with a transaction), so a
    quiet day correctly pulls the average down rather than being ignored."""
    days = (end - start).days + 1
    rows = await db.execute(
        select(Expense.category_id, func.coalesce(func.sum(Expense.converted_amount), 0))
        .where(Expense.user_id == user_id, Expense.deleted_at.is_(None),
               Expense.expense_date >= start, Expense.expense_date <= end)
        .group_by(Expense.category_id)
    )
    return {cid: Decimal(total) / days for cid, total in rows.all()}


async def _daily_categories(
    db: AsyncSession, user_id: uuid.UUID, start: date, end: date
) -> set[uuid.UUID]:
    """Categories spent on often enough over [start, end] for a per-day
    average to mean anything — see [_MIN_ACTIVE_DAY_RATIO]."""
    days = (end - start).days + 1
    rows = await db.execute(
        select(Expense.category_id, func.count(func.distinct(Expense.expense_date)))
        .where(Expense.user_id == user_id, Expense.deleted_at.is_(None),
               Expense.expense_date >= start, Expense.expense_date <= end,
               Expense.category_id.is_not(None))
        .group_by(Expense.category_id)
    )
    return {cid for cid, active in rows.all() if Decimal(active) / days >= _MIN_ACTIVE_DAY_RATIO}


async def _recently_resolved(db: AsyncSession, user_id: uuid.UUID, label: str, today: date) -> bool:
    """True if this subject already got a spending_shift answer within the
    touch window — record_advice()'s own dedup only reuses a still-PENDING
    row, so without this a resolved shift would be re-raised on the very
    next brief load (the underlying weekly averages haven't moved)."""
    cutoff = datetime.combine(today - timedelta(days=_RECENT_TOUCH_DAYS), datetime.min.time(), tzinfo=timezone.utc)
    row = await db.scalar(
        select(AdviceMemory.id).where(
            AdviceMemory.user_id == user_id, AdviceMemory.deleted_at.is_(None),
            AdviceMemory.kind == AdviceKind.spending_shift.value, AdviceMemory.subject_label == label,
            AdviceMemory.status != AdviceStatus.pending.value,
            AdviceMemory.answered_at.is_not(None), AdviceMemory.answered_at >= cutoff,
        ).limit(1)
    )
    return row is not None


async def detect_and_record_shifts(
    db: AsyncSession, user_id: uuid.UUID, *, today: date, base_currency: str | None = None,
) -> list[AdviceMemory]:
    """Compare this week's per-category daily average to the prior baseline
    window; where it's moved by more than the threshold, remember a
    spending_shift advice row and make it due immediately (a shift deserves a
    near-term "what changed?", not the generic 30-day category cadence)."""
    if not await has_min_history(db, user_id, today):
        return []

    recent_start = today - timedelta(days=_RECENT_WINDOW_DAYS - 1)
    baseline_end = recent_start - timedelta(days=1)
    baseline_start = baseline_end - timedelta(days=_BASELINE_WINDOW_DAYS - 1)

    recent = await _category_daily_avg(db, user_id, recent_start, today)
    baseline = await _category_daily_avg(db, user_id, baseline_start, baseline_end)
    # Only categories with a genuine day-to-day rhythm — otherwise a monthly
    # rent bill reads as "rent dropped to 0/day this week".
    daily = await _daily_categories(db, user_id, baseline_start, baseline_end)
    baseline = {cid: avg for cid, avg in baseline.items() if cid in daily}
    if not baseline:
        return []

    name_map = {c.id: c.name for c in await category_service.list_for_user(db, user_id)}
    created: list[AdviceMemory] = []
    for category_id, base_avg in baseline.items():
        if category_id is None or base_avg < _MIN_BASELINE_DAILY_AVG:
            continue
        recent_avg = recent.get(category_id, Decimal("0"))
        deviation = abs(recent_avg - base_avg) / base_avg
        if deviation < _SHIFT_THRESHOLD:
            continue

        label = name_map.get(category_id, "that category")
        if await _recently_resolved(db, user_id, label, today):
            continue
        direction = "higher" if recent_avg > base_avg else "lower"
        claim = (f"{label} spending has been running {direction} lately — about "
                 f"{recent_avg:.0f}/day this week vs your usual {base_avg:.0f}/day")
        row = await advice_memory_service.record_advice(
            db, user_id, kind=AdviceKind.spending_shift.value, subject_type="category",
            subject_label=label, category_id=category_id, claim=claim,
            expected_value=base_avg, base_currency=base_currency, today=today,
        )
        if row.status == AdviceStatus.pending.value and (row.follow_up_due is None or row.follow_up_due > today):
            row.follow_up_due = today
            await db.commit()
            await db.refresh(row)
        created.append(row)
    return created
