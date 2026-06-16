"""Pure tests for effectiveness (E3), trust (E4), decay (mod 5), E7 boundaries."""

from __future__ import annotations

from datetime import date

from app.intelligence.outcomes import build_effectiveness, classify_circumstance, decay_weight, trust_level
from app.intelligence.outcomes.effectiveness import (
    MIXED,
    STILL_LEARNING,
    USUALLY_DOESNT_WORK,
    USUALLY_WORKS,
    WORKS_BUT_CIRCUMSTANCES,
)

TODAY = date(2026, 6, 15)


def _o(outcome, circ=None, src="derived", on=TODAY):
    return {"outcome": outcome, "circumstance": circ, "source": src, "evaluated_on": on}


def test_classify_circumstance():
    assert classify_circumstance("medical issue") == "medical"
    assert classify_circumstance("an unexpected expense") == "unexpected_expense"
    assert classify_circumstance("income was late this month") == "income_delay"
    assert classify_circumstance("I changed my mind") is None


def test_decay_bands():
    assert decay_weight(0) == 1.0 and decay_weight(3) == 0.75
    assert decay_weight(6) == 0.5 and decay_weight(12) == 0.35 and decay_weight(18) == 0.25


def test_trust_bands():
    assert trust_level(2) == "low" and trust_level(5) == "medium" and trust_level(8) == "high"


def test_usually_works():
    e = build_effectiveness("reduce_food", [_o("success")] * 3, today=TODAY)
    assert e.conclusion == USUALLY_WORKS and e.success_count == 3 and e.failure_count == 0


def test_usually_doesnt_work():
    e = build_effectiveness("move_date", [_o("failed")] * 3, today=TODAY)
    assert e.conclusion == USUALLY_DOESNT_WORK and e.failure_count == 3


def test_E7_circumstance_is_not_lever_failure():
    outs = [_o("success"), _o("success"), _o("success"), _o("failed", "medical"), _o("failed", "travel")]
    e = build_effectiveness("reduce_food", outs, today=TODAY)
    assert e.conclusion == WORKS_BUT_CIRCUMSTANCES
    assert e.circumstance_count == 2 and e.failure_count == 0 and e.success_count == 3


def test_mixed_is_medium_confidence():
    e = build_effectiveness("x", [_o("success"), _o("failed"), _o("success"), _o("failed")], today=TODAY)
    assert e.conclusion == MIXED and e.trust_level == "medium" and "Based on 4" in e.advisor_confidence


def test_still_learning_low_evidence():
    e = build_effectiveness("x", [_o("success")] * 2, today=TODAY)
    assert e.conclusion == STILL_LEARNING and e.trust_level == "low" and e.advisor_confidence == "Still learning."


def test_decay_weights_recent_more():
    old = date(2025, 5, 1)   # ~13 months before TODAY
    e = build_effectiveness("x", [_o("success", on=TODAY), _o("failed", on=old), _o("failed", on=old)], today=TODAY)
    assert e.success_rate > 0.6 and e.conclusion == USUALLY_WORKS   # recent success outweighs two stale failures


def test_source_split_counts():
    e = build_effectiveness("x", [_o("success", src="derived"), _o("success", src="user_reported"), _o("failed")], today=TODAY)
    assert e.derived_count == 2 and e.reported_count == 1 and e.evidence_count == 3


def test_contradiction_completed_but_ineffective():
    e = build_effectiveness("x", [_o("partial"), _o("partial"), _o("partial"), _o("failed")], today=TODAY)
    assert "completed_but_ineffective" in e.contradictions


def test_contradiction_rejected_but_effective():
    e = build_effectiveness("x", [_o("success")] * 3, today=TODAY, accepted=1, total_feedback=5)
    assert "rejected_but_effective" in e.contradictions
