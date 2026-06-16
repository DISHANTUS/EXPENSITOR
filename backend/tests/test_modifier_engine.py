"""Tests for the modifier orchestrator: influence step, targeted questions, dedup."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from app.intelligence.decision import modifier_engine
from app.intelligence.decision.attributes import classify
from app.intelligence.decision.modifiers.base import AnalyzerCtx, ModifierInputs
from app.intelligence.decision.request import DecisionKind, DecisionRequest, OutflowShape
from app.intelligence.projection.scenario import Scenario
from app.intelligence.projection.spending_model import SpendingModel

TODAY = date(2026, 6, 1)


def _ctx(inputs: ModifierInputs) -> AnalyzerCtx:
    scn = Scenario(today=TODAY, horizon=TODAY + timedelta(days=120), base_currency="INR",
                   current_balance=Decimal("100000"), spending=SpendingModel(Decimal("0"), Decimal("0"), "normal", 90, 90),
                   income_events=(), outflows=())
    req = DecisionRequest(item_label="x", amount_base=Decimal("300"), decision_kind=DecisionKind.custom,
                          outflow_shape=OutflowShape.one_time)
    return AnalyzerCtx(request=req, attributes=classify(req, scn), scenario=scn, inputs=inputs,
                       currency="INR", amount=Decimal("300"), when=TODAY)


def _keys(res) -> set[str]:
    return {q["key"] for q in res["pending_questions"]}


def test_influence_step_asked_first():
    res = modifier_engine.run(_ctx(ModifierInputs(involves=None)))
    assert "involves" in _keys(res)            # the single influence question
    assert res["findings"] == []               # nothing else runs yet


def test_targeted_questions_only_for_selected_influence():
    res = modifier_engine.run(_ctx(ModifierInputs(involves=("free_delivery",))))
    keys = _keys(res)
    assert "original_amount" in keys and "delivery_fee" in keys
    assert "involves" not in keys              # influence already answered
    assert res["findings"] == []               # free_delivery still needs inputs


def test_questions_deduped_across_analyzers():
    # free_delivery + offer both need original_amount -> asked once.
    res = modifier_engine.run(_ctx(ModifierInputs(involves=("free_delivery", "offer"))))
    originals = [q for q in res["pending_questions"] if q["key"] == "original_amount"]
    assert len(originals) == 1


def test_satisfied_inputs_produce_findings():
    mi = ModifierInputs(involves=("free_delivery",), original_amount=Decimal("250"), delivery_fee=Decimal("60"),
                        free_delivery_threshold=Decimal("350"), final_amount=Decimal("350"), items_useful="no")
    res = modifier_engine.run(_ctx(mi))
    assert any(f["analyzer"] == "free_delivery" for f in res["findings"])
    assert "original_amount" not in _keys(res)
