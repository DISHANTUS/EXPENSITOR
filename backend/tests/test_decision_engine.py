"""Pure tests for the Financial Decision Engine (C7a)."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

from app.intelligence.decision import engine
from app.intelligence.decision.request import (
    DecisionRequest,
    EmotionalImportance,
    Flexibility,
    UserConstraints,
)
from app.intelligence.projection.income_projection import IncomeEvent
from app.intelligence.projection.scenario import Scenario
from app.intelligence.projection.spending_model import SpendingModel

TODAY = date(2026, 6, 1)


def _scn(*, balance="0", mu="0", horizon_days=160, income=(), threshold=None) -> Scenario:
    return Scenario(
        today=TODAY, horizon=TODAY + timedelta(days=horizon_days), base_currency="INR",
        current_balance=Decimal(balance),
        spending=SpendingModel(Decimal(mu), Decimal("0"), "normal", 90, 90),
        income_events=tuple(income), outflows=(),
        monthly_threshold=Decimal(threshold) if threshold is not None else None,
    )


def _income(day, amount, rel="0.9", origin="income_source:salary"):
    return IncomeEvent(TODAY + timedelta(days=day), Decimal(amount), Decimal(rel), uuid.uuid4(), origin)


def _req(amount, **over) -> DecisionRequest:
    kw = dict(item_label="thing", amount_base=Decimal(amount))
    kw.update(over)
    return DecisionRequest(**kw)


def _kinds(result) -> set[str]:
    return {s.strategy_kind for s in result.strategies}


def test_affordable_now():
    result = engine.evaluate(_scn(balance="100000", mu="0"), _req("2000"))
    assert result.verdict == "affordable"
    assert result.can_do_now is True
    assert result.best_strategy is not None and result.best_strategy.strategy_kind in ("buy_now", "use_savings")


def test_impact_level_scales_with_size():
    minor = engine.evaluate(_scn(balance="100000"), _req("300"))
    significant = engine.evaluate(_scn(balance="100000"), _req("60000"))
    assert minor.impact.impact_level in ("none", "minor")
    assert significant.impact.impact_level == "significant"


def test_not_affordable_now_waits_for_income():
    scn = _scn(balance="0", mu="0", income=[_income(10, "25000")])
    result = engine.evaluate(scn, _req("5000"))
    assert result.verdict == "tight"
    wait = next((s for s in result.strategies if s.strategy_kind == "wait_for_income"), None)
    assert wait is not None and wait.feasible and wait.purchase_date == TODAY + timedelta(days=10)
    assert result.best_strategy.strategy_kind in ("wait_for_income", "split_into_stages")


def test_excluded_strategy_is_never_suggested():
    scn = _scn(balance="0", income=[_income(10, "25000")])
    result = engine.evaluate(scn, _req("5000", excluded_strategies=("wait_for_income",)))
    assert "wait_for_income" not in _kinds(result)
    # still offers an alternative path
    assert any(s.feasible for s in result.strategies)


def test_use_savings_preserves_floor():
    # threshold=30000 -> emergency floor 30000; balance 100000 -> available 70000; 5000 fits.
    result = engine.evaluate(_scn(balance="100000", mu="0", threshold="30000"), _req("5000"))
    use = next((s for s in result.strategies if s.strategy_kind == "use_savings"), None)
    assert use is not None and use.feasible
    assert "emergency_reserve_preserved" in use.constraints_used


def test_reduce_discretionary_cut_math():
    scn = _scn(balance="0", mu="2000")  # capacity = 1000/day
    result = engine.evaluate(scn, _req("3000", target_date=TODAY + timedelta(days=10)))
    reduce = next((s for s in result.strategies if s.strategy_kind == "reduce_discretionary"), None)
    assert reduce is not None
    assert reduce.daily_saving_required == Decimal("300.00")  # 3000 / 10 days
    assert reduce.saving_days == 10 and reduce.feasible is True


def test_move_date_blocked_by_fixed_date_constraint():
    scn = _scn(balance="0", income=[_income(10, "25000")])
    fixed = _req("5000", flexibility=Flexibility.fixed_date, constraints=UserConstraints(date_fixed=True))
    result = engine.evaluate(scn, fixed)
    assert "move_date" not in _kinds(result)
    assert "wait_for_income" not in _kinds(result)  # cannot delay either
    assert result.attributes.can_move_date is False


def test_move_date_offered_when_flexible():
    scn = _scn(balance="0", income=[_income(12, "25000")])
    result = engine.evaluate(scn, _req("5000", flexibility=Flexibility.flexible))
    assert "move_date" in _kinds(result) or "wait_for_income" in _kinds(result)


def test_emotional_importance_recorded_in_attributes():
    result = engine.evaluate(_scn(balance="100000"), _req("2000", emotional_importance=EmotionalImportance.critical))
    assert result.attributes.emotional_importance == "critical"


def test_to_facts_shape():
    result = engine.evaluate(_scn(balance="100000"), _req("2000"))
    facts = result.to_facts()
    assert set(facts) >= {
        "item_label", "amount", "currency", "attributes", "can_do_now", "verdict",
        "now_consequence", "best_strategy", "strategies", "impact", "dependencies",
    }
    assert facts["dependencies"] == []  # future hook, empty for now
    assert facts["impact"]["impact_level"] in ("none", "minor", "moderate", "significant")
    # every strategy carries the required metadata
    for s in facts["strategies"]:
        assert {"strategy_id", "strategy_kind", "assumptions", "tradeoffs", "constraints_used"} <= set(s)
