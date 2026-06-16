"""B1.5a profile-level tests: root cause (R2), notification kinds (R4),
composite stability (R5), and the root-cause B2 insight."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

from app.intelligence.behavior import metrics  # noqa: F401  (register)
from app.intelligence.behavior.data import BehaviorData, CategoryInfo, ExpenseRow, IncomeRow, build_window
from app.intelligence.behavior.insights import build_behavioral_insights
from app.intelligence.behavior.profile import WEAK_SCORE
from app.intelligence.behavior.scoring import build_profile_from_data

TODAY = date(2026, 6, 15)
ESS, DISC = uuid.uuid4(), uuid.uuid4()
CATS = {ESS: CategoryInfo("Rent & Housing", True), DISC: CategoryInfo("Food & Dining", False)}
COMPLETE = [(2026, 1), (2026, 2), (2026, 3), (2026, 4), (2026, 5)]
_NEW_KEYS = {"lifestyle_inflation", "spending_escalation_rate", "category_volatility",
             "commitment_pressure", "upgrade_replacement_behavior"}


def _data(**over) -> BehaviorData:
    base = dict(
        window=build_window(TODAY), base_currency="INR", monthly_threshold=None,
        monthly_income_estimate=Decimal("10000"), starting_balance=Decimal("0"),
        expenses=(), incomes=(), income_sources=(), sessions=(), receivables=(), planned=(),
        categories=CATS, salary_days=frozenset(), shopping_category_ids=frozenset(),
    )
    base.update(over)
    return BehaviorData(**base)


def _rising() -> tuple:
    exp = []
    counts = {(2026, 1): 4, (2026, 2): 6, (2026, 3): 8, (2026, 4): 10, (2026, 5): 12}
    for (y, m), k in counts.items():
        # spread across distinct days so this isolates lifestyle inflation (no same-day impulse clusters)
        exp += [ExpenseRow(date(y, m, 1 + i), Decimal("500"), DISC) for i in range(k)]
        exp.append(ExpenseRow(date(y, m, 25), Decimal("2000"), ESS))
    inc = [IncomeRow(date(y, m, 1), Decimal("10000"), "salary") for (y, m) in COMPLETE]
    return tuple(exp), tuple(inc)


def test_root_cause_synthesizes_primary(monkeypatch):
    exp, inc = _rising()
    profile = build_profile_from_data(_data(expenses=exp, incomes=inc))
    rc = profile.advisor_view().get("root_cause")
    assert rc and rc["primary_metric"] in {"lifestyle_inflation", "spending_escalation_rate"}
    assert "increasing for" in rc["statement"]


def test_root_cause_surfaces_as_top_insight():
    exp, inc = _rising()
    profile = build_profile_from_data(_data(expenses=exp, incomes=inc))
    insights = build_behavioral_insights(profile)
    assert insights and insights[0].metric_key == "root_cause"
    assert "biggest pressure" in insights[0].finding


def test_notification_kinds_published():
    exp, inc = _rising()
    profile = build_profile_from_data(_data(expenses=exp, incomes=inc))
    kinds = profile.advisor_view()["notification_kinds"]
    assert kinds["lifestyle_inflation"] == ["warning", "opportunity"]
    assert kinds["commitment_pressure"] == ["warning"]


def test_trend_duration_flows_to_insights():
    exp, inc = _rising()
    profile = build_profile_from_data(_data(expenses=exp, incomes=inc))
    infl = [s for s in profile.weaknesses + profile.risks if s.metric_key == "lifestyle_inflation"]
    assert infl and infl[0].trend_duration_months == 4


def test_composite_stability_for_healthy_user():
    # Flat, comfortable spending with rate-window density -> normal confidence.
    # The new metrics must NOT drag a healthy user down (R5).
    exp = []
    d = build_window(TODAY).month_start
    while d <= TODAY:
        exp.append(ExpenseRow(d, Decimal("100"), DISC))          # flat daily discretionary
        if d.day == 11:
            exp.append(ExpenseRow(d, Decimal("2000"), ESS))      # flat monthly essential
        d += timedelta(days=1)
    inc = [IncomeRow(date(y, m, 1), Decimal("12000"), "salary") for (y, m) in COMPLETE]
    profile = build_profile_from_data(_data(expenses=tuple(exp), incomes=tuple(inc)))

    # The B1.5 metrics evaluate (normal confidence) and must NOT drag a healthy user (R5).
    healthy_new = [m for m in profile.metrics if m.key in _NEW_KEYS and m.confidence == "normal"]
    assert len(healthy_new) >= 3
    for m in healthy_new:
        assert m.score >= WEAK_SCORE, f"{m.key} dragged a healthy user to {m.score}"
    assert profile.composite_score >= 50          # no downward swing below neutral


def test_cold_start_composite_unchanged_at_fifty():
    profile = build_profile_from_data(_data())
    assert profile.composite_score == 50 and profile.confidence == "low"
