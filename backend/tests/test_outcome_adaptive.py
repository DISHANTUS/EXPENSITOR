"""Pure tests for adaptive planning (E2) + the E7 invariant (facts unchanged)."""

from __future__ import annotations

from datetime import date

from app.intelligence.outcomes import build_effectiveness, build_plan

TODAY = date(2026, 6, 15)
REC_A = {"lever_key": "reduce_food", "title": "Trim food", "score": 0.5, "impact": 0.6, "outcome_preview": {"x": "y"}}
REC_B = {"lever_key": "move_date", "title": "Move it", "score": 0.6, "impact": 0.7, "outcome_preview": {"a": "b"}}


def _o(outcome, circ=None):
    return {"outcome": outcome, "circumstance": circ, "source": "derived", "evaluated_on": TODAY}


def _eff(lever, outs, **kw):
    return build_effectiveness(lever, outs, today=TODAY, **kw)


def test_effective_boosted_ineffective_downranked():
    eff = {"reduce_food": _eff("reduce_food", [_o("success")] * 3),
           "move_date": _eff("move_date", [_o("failed")] * 3)}
    plan = build_plan([REC_A, REC_B], eff)
    order = [r["lever_key"] for r in plan["recommendations"]]
    assert order[0] == "reduce_food"                       # boosted above B's higher base score
    assert "reduce_food" in plan["outcome_influence"]["boosted"]
    assert "move_date" in plan["outcome_influence"]["downranked"]
    assert "move_date" in plan["strategies_that_fail"] and "reduce_food" in plan["strategies_that_work"]


def test_E7_effective_lever_with_circumstances_stays_recommended():
    eff = {"reduce_food": _eff("reduce_food", [_o("success")] * 3 + [_o("failed", "medical"), _o("failed", "travel")])}
    plan = build_plan([REC_A], eff)
    levers = [r["lever_key"] for r in plan["recommendations"]]
    assert "reduce_food" in levers                          # NOT dropped
    assert "reduce_food" not in plan["outcome_influence"]["downranked"]
    assert "reduce_food" in plan["circumstance_limited"]


def test_E7_circumstances_change_only_annotations_not_facts():
    eff = {"reduce_food": _eff("reduce_food", [_o("failed", "medical")] * 3)}
    out = build_plan([REC_A], eff)["recommendations"][0]
    # financial fields byte-identical; only advisor annotation added
    assert out["impact"] == REC_A["impact"] and out["outcome_preview"] == REC_A["outcome_preview"]
    assert out["score"] == REC_A["score"]
    assert "advisor_learning" in out and "_rank" not in out


def test_adaptive_rec_exposes_full_confidence_block():
    eff = {"reduce_food": _eff("reduce_food", [_o("success")] * 8)}
    block = build_plan([REC_A], eff)["recommendations"][0]["advisor_learning"]
    assert set(block) >= {"advisor_confidence", "evidence_count", "trust_level", "last_success", "last_failure", "conclusion"}
    assert block["trust_level"] == "high" and block["evidence_count"] == 8


def test_contradictions_surfaced_in_plan():
    eff = {"x": _eff("x", [_o("partial"), _o("partial"), _o("partial"), _o("failed")])}
    plan = build_plan([{"lever_key": "x", "score": 0.5}], eff)
    assert any(c["kind"] == "completed_but_ineffective" for c in plan["contradictions"])


def test_still_learning_lever_is_neutral():
    eff = {"reduce_food": _eff("reduce_food", [_o("success")] * 2)}  # <3 evidence
    plan = build_plan([REC_A], eff)
    assert "reduce_food" not in plan["outcome_influence"]["boosted"]
    assert "reduce_food" not in plan["outcome_influence"]["downranked"]
