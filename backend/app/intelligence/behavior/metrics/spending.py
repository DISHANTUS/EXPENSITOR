"""Spending Discipline metrics (90-day rate window)."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from app.intelligence.behavior import scoring
from app.intelligence.behavior.data import BehaviorData, ExpenseRow
from app.intelligence.behavior.registry import DISCIPLINE, LOWER_BETTER, register

_MIN_ROWS = 15
_MIN_SHOPPING = 5
_MIN_CONCENTRATION_ROWS = 20


def _in_range(rows: list[ExpenseRow], start: date, end: date) -> list[ExpenseRow]:
    return [e for e in rows if start <= e.on <= end]


# --------------------------------------------------------------------------- #
@register(key="weekend_overspending", dimension=DISCIPLINE, direction=LOWER_BETTER,
          controllable=True, personality_tags=("social_spender", "impulse_buyer"))
def weekend_overspending(data: BehaviorData) -> scoring.BehavioralMetric:
    key, dim = "weekend_overspending", DISCIPLINE
    rows = data.expenses_in_rate_window()
    if len(rows) < _MIN_ROWS:
        return scoring.insufficient(key, dim, "insufficient_data", {"rows": len(rows)})

    def ratio(start: date, end: date) -> Decimal | None:
        days = (end - start).days + 1
        we_days = sum(1 for i in range(days) if (start + timedelta(days=i)).weekday() >= 5)
        wd_days = days - we_days
        we = sum((e.amount for e in _in_range(rows, start, end) if e.on.weekday() >= 5), Decimal("0"))
        wd = sum((e.amount for e in _in_range(rows, start, end) if e.on.weekday() < 5), Decimal("0"))
        we_avg = we / we_days if we_days else Decimal("0")
        wd_avg = wd / wd_days if wd_days else Decimal("0")
        if wd_avg == 0:
            return None if we_avg == 0 else Decimal("3")  # heavy skew sentinel
        return we_avg / wd_avg

    today = data.window.today
    r = ratio(data.window.rate_start, today)
    if r is None:
        return scoring.insufficient(key, dim, "insufficient_data", {"rows": len(rows)})
    score = 100 - (float(r) - 1.0) * 120
    recent = ratio(today - timedelta(days=44), today)
    prior = ratio(today - timedelta(days=89), today - timedelta(days=45))
    return scoring.metric(
        key=key, dimension=dim, value=r.quantize(Decimal("0.001")), score=scoring.clamp_score(score),
        confidence="normal", trend=scoring.classify_trend(recent, prior, LOWER_BETTER),
        facts={"ratio": str(r.quantize(Decimal("0.001")))},
    )


# --------------------------------------------------------------------------- #
def _salary_occurrences(data: BehaviorData, start: date, end: date) -> list[date]:
    from app.intelligence.projection.calendar_utils import clamp_day, iter_year_months

    out: list[date] = []
    for d in data.salary_days:
        for year, month in iter_year_months(start, end):
            occ = clamp_day(year, month, d)
            if start <= occ <= end:
                out.append(occ)
    return out


def _spike(rows: list[ExpenseRow], occurrences: list[date], start: date, end: date) -> Decimal | None:
    if not occurrences:
        return None
    post_days = {o + timedelta(days=k) for o in occurrences for k in range(3) if start <= o + timedelta(days=k) <= end}
    if not post_days:
        return None
    total_days = (end - start).days + 1
    base_days = total_days - len(post_days)
    if base_days <= 0:
        return None
    post_total = sum((e.amount for e in rows if e.on in post_days), Decimal("0"))
    base_total = sum((e.amount for e in rows if e.on not in post_days), Decimal("0"))
    post_avg = post_total / len(post_days)
    base_avg = base_total / base_days
    if base_avg == 0:
        return None if post_avg == 0 else Decimal("2")
    return post_avg / base_avg


@register(key="salary_day_spending_spike", dimension=DISCIPLINE, direction=LOWER_BETTER,
          controllable=True, personality_tags=("impulse_buyer",))
def salary_day_spending_spike(data: BehaviorData) -> scoring.BehavioralMetric:
    key, dim = "salary_day_spending_spike", DISCIPLINE
    if not data.salary_days:
        return scoring.insufficient(key, dim, "no_salary_data")
    rows = data.expenses_in_rate_window()
    if len(rows) < _MIN_ROWS:
        return scoring.insufficient(key, dim, "insufficient_data", {"rows": len(rows)})

    today = data.window.today
    occ = _salary_occurrences(data, data.window.rate_start, today)
    spike = _spike(rows, occ, data.window.rate_start, today)
    if spike is None:
        return scoring.insufficient(key, dim, "insufficient_data", {"salary_occurrences": len(occ)})
    score = 100 - (float(spike) - 1.0) * 100
    r_start, p_start, p_end = today - timedelta(days=44), today - timedelta(days=89), today - timedelta(days=45)
    recent = _spike(rows, _salary_occurrences(data, r_start, today), r_start, today)
    prior = _spike(rows, _salary_occurrences(data, p_start, p_end), p_start, p_end)
    return scoring.metric(
        key=key, dimension=dim, value=spike.quantize(Decimal("0.001")), score=scoring.clamp_score(score),
        confidence="normal", trend=scoring.classify_trend(recent, prior, LOWER_BETTER),
        facts={"spike_ratio": str(spike.quantize(Decimal("0.001"))), "salary_days": sorted(data.salary_days)},
    )


# --------------------------------------------------------------------------- #
@register(key="shopping_spend_share", dimension=DISCIPLINE, direction=LOWER_BETTER,
          controllable=True, personality_tags=("impulse_buyer", "experience_seeker"))
def shopping_spend_share(data: BehaviorData) -> scoring.BehavioralMetric:
    key, dim = "shopping_spend_share", DISCIPLINE
    if not data.shopping_category_ids:
        return scoring.insufficient(key, dim, "no_shopping_category")
    rows = data.expenses_in_rate_window()
    shop = [e for e in rows if e.category_id in data.shopping_category_ids]
    if len(shop) < _MIN_SHOPPING:
        return scoring.insufficient(key, dim, "insufficient_data", {"shopping_rows": len(shop)})

    def share(rs: list[ExpenseRow]) -> Decimal | None:
        total = sum((e.amount for e in rs), Decimal("0"))
        s = sum((e.amount for e in rs if e.category_id in data.shopping_category_ids), Decimal("0"))
        return scoring.safe_ratio(s, total)

    today = data.window.today
    sh = share(rows) or Decimal("0")
    score = 100 - max(0.0, float(sh) - 0.20) * 250
    recent = share([e for e in rows if e.on >= today - timedelta(days=44)])
    prior = share([e for e in rows if today - timedelta(days=89) <= e.on <= today - timedelta(days=45)])
    return scoring.metric(
        key=key, dimension=dim, value=sh.quantize(Decimal("0.001")), score=scoring.clamp_score(score),
        confidence="normal", trend=scoring.classify_trend(recent, prior, LOWER_BETTER),
        facts={"spend_share": str(sh.quantize(Decimal("0.001"))), "count": len(shop)},
    )


# --------------------------------------------------------------------------- #
def _hhi(rows: list[ExpenseRow]) -> Decimal | None:
    total = sum((e.amount for e in rows), Decimal("0"))
    if total <= 0:
        return None
    by_cat: dict[object, Decimal] = {}
    for e in rows:
        by_cat[e.category_id] = by_cat.get(e.category_id, Decimal("0")) + e.amount
    return sum(((v / total) ** 2 for v in by_cat.values()), Decimal("0"))


@register(key="category_concentration", dimension=DISCIPLINE, direction=LOWER_BETTER,
          forward_risk=True, personality_tags=("impulse_buyer",))
def category_concentration(data: BehaviorData) -> scoring.BehavioralMetric:
    key, dim = "category_concentration", DISCIPLINE
    months = set(data.window.months)
    rows = [e for e in data.expenses if (e.on.year, e.on.month) in months]
    distinct = {e.category_id for e in rows}
    if len(rows) < _MIN_CONCENTRATION_ROWS or len(distinct) < 2:
        return scoring.insufficient(key, dim, "insufficient_data", {"rows": len(rows), "categories": len(distinct)})

    hhi = _hhi(rows)
    if hhi is None:
        return scoring.insufficient(key, dim, "insufficient_data", {"rows": len(rows)})
    score = 100 - max(0.0, float(hhi) - 0.20) * 250

    half = len(data.window.months) // 2
    early_m = set(data.window.months[:half])
    late_m = set(data.window.months[half:])
    prior = _hhi([e for e in rows if (e.on.year, e.on.month) in early_m])
    recent = _hhi([e for e in rows if (e.on.year, e.on.month) in late_m])
    return scoring.metric(
        key=key, dimension=dim, value=hhi.quantize(Decimal("0.001")), score=scoring.clamp_score(score),
        confidence="normal", trend=scoring.classify_trend(recent, prior, LOWER_BETTER),
        facts={"hhi": str(hhi.quantize(Decimal("0.001"))), "categories": len(distinct)},
    )
