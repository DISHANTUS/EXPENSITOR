"""Pure tests for the aggressive bidirectional grounding guard (C5 Phase 3b).

Covers every validation dimension the spec requires: numbers, money, percentages,
dates, times, entities, paragraph count, ordered-list order+count, severity
wording, and confidence wording. Any mismatch -> not ok (caller falls back).
"""

from __future__ import annotations

from app.intelligence.commentary.ollama import adapter, guard

# A realistic deterministic commentary (mirrors Commentary.as_dict()).
DET = {
    "paragraphs": [
        "₹250 expense added (Food & Dining). I checked this against today's budget, your goals and upcoming plans.",
        "This plan currently relies on the ₹15,000 expected from your father on Jun 24 around 5 PM. "
        "If that arrives later than expected, you may need to use savings or trim the plan budget.",
        "₹683 left to spend today. Your next expected income is ₹15,000 from your father on Jun 24.",
    ],
    "attention": "This plan currently relies on the ₹15,000 expected from your father on Jun 24 around 5 PM. "
                 "If that arrives later than expected, you may need to use savings or trim the plan budget.",
    "timing_note": "Your next expected income is ₹15,000 from your father on Jun 24.",
    "most_useful_number": "₹683 left to spend today.",
    "confidence_note": None,
    "severity": "warning",
    "facts": {"grounding": ["15000.0000", "2026-06-24", "17:00", "your father", "250.0000", "683.0000"]},
}

FAITHFUL = (
    "I've logged your ₹250 Food & Dining expense and checked it against today's budget, your goals "
    "and upcoming plans.\n\n"
    "For now this plan leans on the ₹15,000 you expect from your father on Jun 24 around 5 PM; if it "
    "lands later, you might dip into savings or trim the plan budget.\n\n"
    "That leaves ₹683 to spend today. Your next expected income is ₹15,000 from your father on Jun 24."
)


def _spec():
    return adapter.from_commentary(DET).grounding


def test_faithful_rephrase_passes():
    assert guard.validate(FAITHFUL, _spec()).ok


def test_added_money_rejected():
    bad = FAITHFUL.replace("upcoming plans.", "upcoming plans. Consider setting aside ₹2,000.")
    r = guard.validate(bad, _spec())
    assert not r.ok and r.reason == "added_money" and "2000" in r.offending_tokens


def test_added_date_rejected():
    bad = FAITHFUL.replace("on Jun 24 around 5 PM", "on Jul 4 around 5 PM")
    r = guard.validate(bad, _spec())
    assert not r.ok and r.reason == "added_date"


def test_added_time_rejected():
    bad = FAITHFUL.replace("around 5 PM", "around 9 AM")
    r = guard.validate(bad, _spec())
    assert not r.ok and r.reason in ("added_time", "dropped_time")


def test_added_percentage_rejected():
    bad = FAITHFUL.replace("to spend today.", "to spend today, about 12% of your budget.")
    r = guard.validate(bad, _spec())
    assert not r.ok and r.reason == "added_percent" and "12" in r.offending_tokens


def test_added_entity_rejected():
    bad = FAITHFUL.replace("from your father on Jun 24.", "from your father, via Netflix, on Jun 24.")
    r = guard.validate(bad, _spec())
    assert not r.ok and r.reason == "added_entity" and "Netflix" in r.offending_tokens


def test_dropped_required_number_rejected():
    # remove the ₹683 the user relies on
    bad = FAITHFUL.replace("That leaves ₹683 to spend today. ", "")
    r = guard.validate(bad, _spec())
    assert not r.ok and r.reason == "dropped_money" and "683" in r.offending_tokens


def test_paragraph_count_mismatch_rejected():
    bad = FAITHFUL.replace("\n\n", " ", 1)   # collapse to 2 paragraphs
    r = guard.validate(bad, _spec())
    assert not r.ok and r.reason == "paragraph_count"


def test_tone_violation_rejected():
    bad = FAITHFUL.replace("Food & Dining expense", "wasteful Food & Dining expense")
    r = guard.validate(bad, _spec())
    assert not r.ok and r.reason == "tone"


def test_invented_alarm_rejected():
    bad = FAITHFUL.replace("trim the plan budget.", "trim the plan budget. This is critical.")
    r = guard.validate(bad, _spec())
    assert not r.ok and r.reason in ("severity_escalation", "paragraph_count")


def test_confidence_added_rejected():
    bad = FAITHFUL.replace("on Jun 24.", "on Jun 24, based on limited history.")
    r = guard.validate(bad, _spec())
    assert not r.ok and r.reason == "confidence_mismatch"


def test_confidence_removed_rejected():
    det = {**DET, "confidence_note": "This read is based on limited history so far.",
           "paragraphs": [*DET["paragraphs"][:2],
                          "₹683 left to spend today. This read is based on limited history so far."]}
    spec = adapter.from_commentary(det).grounding
    dropped = FAITHFUL   # FAITHFUL has no hedge phrase
    r = guard.validate(dropped, spec)
    assert not r.ok and r.reason == "confidence_mismatch"


def test_ordered_items_order_and_count():
    spec = guard.GroundingSpec(
        allowed={c: set() for c in ("money", "percent", "date", "time", "number", "caps")},
        required={}, grounding_tokens=(), escalation_markers=set(), confidence_hedged=False,
        paragraph_count=1, ordered_items=("alpha", "beta", "gamma"), severity="info")
    assert guard.validate("we have alpha, then beta, then gamma here.", spec).ok
    assert not guard.validate("we have beta, then alpha, then gamma here.", spec).ok   # reordered
    assert not guard.validate("we have alpha and gamma here.", spec).ok                # dropped one
