"""Pure tests for the decision-modifier analyzers (C7a-2)."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import app.intelligence.decision.modifiers  # noqa: F401  (registers analyzers)
from app.intelligence.advisor import tone
from app.intelligence.decision.attributes import classify
from app.intelligence.decision.modifiers.base import MODIFIER_REGISTRY, AnalyzerCtx, ModifierInputs
from app.intelligence.decision.request import DecisionKind, DecisionRequest, OutflowShape
from app.intelligence.projection.scenario import Scenario
from app.intelligence.projection.spending_model import SpendingModel

TODAY = date(2026, 6, 1)


def _scn(balance="100000") -> Scenario:
    return Scenario(
        today=TODAY, horizon=TODAY + timedelta(days=120), base_currency="INR",
        current_balance=Decimal(balance), spending=SpendingModel(Decimal("0"), Decimal("0"), "normal", 90, 90),
        income_events=(), outflows=(),
    )


def _ctx(inputs: ModifierInputs, *, amount="2000", kind=DecisionKind.purchase,
         shape=OutflowShape.one_time, recurrence=None, tenure=None) -> AnalyzerCtx:
    scn = _scn()
    req = DecisionRequest(item_label="thing", amount_base=Decimal(amount), decision_kind=kind,
                          outflow_shape=shape, recurrence_months=recurrence, tenure_months=tenure)
    return AnalyzerCtx(request=req, attributes=classify(req, scn), scenario=scn, inputs=inputs,
                       currency="INR", amount=Decimal(amount), when=TODAY)


def _run(key: str, ctx: AnalyzerCtx):
    finding = MODIFIER_REGISTRY[key].run(ctx)
    if finding is not None:
        assert tone.lint(" ".join(finding.texts())) == []
    return finding


def test_free_delivery_net_impact():
    mi = ModifierInputs(involves=("free_delivery",), original_amount=Decimal("250"), delivery_fee=Decimal("60"),
                        free_delivery_threshold=Decimal("350"), final_amount=Decimal("350"), items_useful="no")
    f = _run("free_delivery", _ctx(mi))
    assert f.facts["net"] == "40"  # added 100 to save 60 delivery
    assert "40" in f.recommendation


def test_offer_cashback_net():
    mi = ModifierInputs(involves=("cashback",), original_amount=Decimal("700"), final_amount=Decimal("1000"),
                        offer={"kind": "cashback", "cashback": 200}, items_useful="no")
    f = _run("offer", _ctx(mi))
    assert f.facts["saving"] == "200" and f.facts["extra_spend"] == "300" and f.facts["net"] == "100"


def test_decision_change_records_change():
    mi = ModifierInputs(involves=("offer",), original_amount=Decimal("250"), final_amount=Decimal("420"), items_useful="no")
    f = _run("decision_change", _ctx(mi))
    assert f.facts["decision_changed"] is True and f.facts["change_cost"] == "170"
    assert f.facts["would_have_bought_anyway"] is False


def test_subscription_yearly_saves():
    mi = ModifierInputs(subscription={"alt_cadence": 12, "alt_price": 500, "expected_usage_months": 12})
    f = _run("subscription", _ctx(mi, amount="150", kind=DecisionKind.subscription, shape=OutflowShape.recurring, recurrence=1))
    assert f.facts["break_even_months"] == 3
    assert "save" in f.recommendation.lower()


def test_emi_total_and_months():
    mi = ModifierInputs(emi={"down_payment": 5000, "installment": 3000, "duration_months": 12, "cash_price": 40000})
    f = _run("emi", _ctx(mi, amount="40000", kind=DecisionKind.emi, shape=OutflowShape.tenured, tenure=12))
    assert f.facts["total_payable"] == "41000" and f.facts["months_until_free"] == 12
    assert f.facts["extra_vs_cash"] == "1000"


def test_future_commitment_annualises():
    f = _run("future_commitment", _ctx(ModifierInputs(), amount="499", kind=DecisionKind.subscription,
                                       shape=OutflowShape.recurring, recurrence=1))
    assert f.facts["annual_commitment"] == "5988"


def test_bundle_optional_vs_required():
    mi = ModifierInputs(involves=("bundle",), bundle_add_ons=(
        {"name": "bag", "cost": 2000, "required": False}, {"name": "warranty", "cost": 3000, "required": True}))
    f = _run("bundle", _ctx(mi, amount="60000"))
    assert f.facts["optional_extras"] == "2000" and f.facts["required_extras"] == "3000"


def test_hidden_cost_true_total():
    mi = ModifierInputs(hidden_items=({"name": "case", "cost": 1000}, {"name": "cloud", "cost": 200, "recurring": True}))
    f = _run("hidden_cost", _ctx(mi, amount="60000"))  # purchase -> durable_asset triggers it
    assert f.facts["expected_total"] == "61000" and f.facts["recurring_monthly"] == "200"


def test_hidden_cost_none_returns_no_finding():
    f = MODIFIER_REGISTRY["hidden_cost"].run(_ctx(ModifierInputs(hidden_items=()), amount="60000"))
    assert f is None
