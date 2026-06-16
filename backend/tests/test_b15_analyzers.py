"""Proof that B1.5a unblocks the deferred C7a-2 Lifestyle-Inflation & Upgrade
analyzers — they fire from the behavioral profile via ctx.behavior_view, with no
behavioural computation of their own."""

from __future__ import annotations

import types
from datetime import date
from decimal import Decimal

import app.intelligence.decision.modifiers  # noqa: F401  (registers analyzers)
import app.intelligence.decision.modifiers.lifestyle as life
from app.intelligence.advisor import tone
from app.intelligence.decision.modifiers.base import AnalyzerCtx, ModifierInputs


def _ctx(behavior_view, liquidity="consumable"):
    return AnalyzerCtx(
        request=None, attributes=types.SimpleNamespace(liquidity_class=liquidity), scenario=None,
        inputs=ModifierInputs(involves=("none",)), currency="INR", amount=Decimal("30000"),
        when=date(2026, 6, 20), behavior_view=behavior_view,
    )


def _inflation_view(trend="worsening", dur=4, conf="normal"):
    return {"metrics": {"lifestyle_inflation": {
        "score": 45, "trend": trend, "confidence": conf, "trend_duration_months": dur,
        "facts": {"discretionary_to_income": "0.55"}}}}


def test_lifestyle_inflation_analyzer_fires(monkeypatch):
    monkeypatch.setattr(life, "recovery_time_days", lambda *a, **k: 12)
    ctx = _ctx(_inflation_view())
    assert life._inflation_trigger(ctx)
    f = life._inflation_run(ctx)
    assert f.analyzer == "lifestyle_inflation" and "4 months" in f.finding
    assert tone.is_clean(*f.texts())


def test_lifestyle_inflation_skips_when_flat():
    assert not life._inflation_trigger(_ctx(_inflation_view(trend="flat", dur=0)))


def test_lifestyle_inflation_skips_low_confidence():
    assert not life._inflation_trigger(_ctx(_inflation_view(conf="low")))


def test_upgrade_analyzer_fires_for_durable_asset(monkeypatch):
    monkeypatch.setattr(life, "recovery_time_days", lambda *a, **k: 20)
    view = {"metrics": {"upgrade_replacement_behavior": {
        "score": 60, "trend": "unknown", "confidence": "normal", "trend_duration_months": None,
        "facts": {"replacement_events": 2, "categories": ["Electronics"]}}}}
    ctx = _ctx(view, liquidity="durable_asset")
    assert life._upgrade_trigger(ctx)
    f = life._upgrade_run(ctx)
    assert f.analyzer == "upgrade_replacement" and "Electronics" in f.finding
    assert tone.is_clean(*f.texts())


def test_upgrade_analyzer_skips_non_durable():
    view = {"metrics": {"upgrade_replacement_behavior": {
        "score": 60, "trend": "unknown", "confidence": "normal",
        "facts": {"replacement_events": 2, "categories": []}}}}
    assert not life._upgrade_trigger(_ctx(view, liquidity="consumable"))
