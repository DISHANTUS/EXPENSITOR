"""Recommendation effectiveness (E3) + Trust Score (E4) + Learning Boundaries (E7).

Pure + deterministic over a lever's outcome rows. Decay-weights recent outcomes
(mod 5), separates genuine lever failures from CIRCUMSTANCE failures (E7), and
yields the three distinct conclusions: usually_works / usually_doesnt_work /
works_but_circumstances_interfere (plus mixed / still_learning). Strong down-rank
is reserved for genuine ineffectiveness — circumstance failures never qualify.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from app.intelligence.outcomes.types import (
    ABANDONED,
    FAILED,
    PARTIAL,
    SUCCESS,
    USER_REPORTED,
    age_months,
    decay_weight,
    trust_level,
)

# conclusions
USUALLY_WORKS = "usually_works"
USUALLY_DOESNT_WORK = "usually_doesnt_work"
WORKS_BUT_CIRCUMSTANCES = "works_but_circumstances_interfere"
MIXED = "mixed"
STILL_LEARNING = "still_learning"

_MIN_EVIDENCE = 3


@dataclass(frozen=True)
class LeverEffectiveness:
    lever_key: str
    success_count: int
    failure_count: int          # E7: genuine lever failures (circumstance excluded)
    abandoned_count: int
    circumstance_count: int     # E7
    evidence_count: int
    derived_count: int
    reported_count: int
    trust_level: str
    acceptance_rate: float | None
    completion_rate: float
    success_rate: float
    conclusion: str
    advisor_confidence: str
    last_success: str | None
    last_failure: str | None
    contradictions: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "lever_key": self.lever_key, "success_count": self.success_count,
            "failure_count": self.failure_count, "abandoned_count": self.abandoned_count,
            "circumstance_count": self.circumstance_count, "evidence_count": self.evidence_count,
            "derived_count": self.derived_count, "reported_count": self.reported_count,
            "trust_level": self.trust_level, "acceptance_rate": self.acceptance_rate,
            "completion_rate": round(self.completion_rate, 3), "success_rate": round(self.success_rate, 3),
            "conclusion": self.conclusion, "advisor_confidence": self.advisor_confidence,
            "last_success": self.last_success, "last_failure": self.last_failure,
            "contradictions": list(self.contradictions),
        }


def _confidence_phrase(level: str, evidence: int) -> str:
    if level == "low":
        return "Still learning."
    return f"Based on {evidence} previous outcome{'s' if evidence != 1 else ''}."


def _conclude(success_rate: float, genuine_failures: int, circ: int, evidence: int) -> str:
    if evidence < _MIN_EVIDENCE:
        return STILL_LEARNING
    if genuine_failures >= 2 and success_rate <= 0.34:
        return USUALLY_DOESNT_WORK
    if circ >= 2 and success_rate >= 0.5:
        return WORKS_BUT_CIRCUMSTANCES
    if success_rate >= 0.6:
        return USUALLY_WORKS
    return MIXED


def _contradictions(completion_rate: float, success_rate: float, acceptance_rate: float | None,
                    evidence: int, success_count: int) -> tuple[str, ...]:
    out = []
    if evidence >= _MIN_EVIDENCE:
        if completion_rate >= 0.6 and success_rate <= 0.34:
            out.append("completed_but_ineffective")
        if acceptance_rate is not None and acceptance_rate <= 0.34 and success_rate >= 0.6 and success_count >= 2:
            out.append("rejected_but_effective")
    return tuple(out)


def build_effectiveness(
    lever_key: str, outcomes: list[dict[str, Any]], *, today: date,
    accepted: int = 0, total_feedback: int = 0,
) -> LeverEffectiveness:
    """outcomes: this lever's recommendation outcome rows
    ({outcome, circumstance, source, evaluated_on: date})."""
    success = partial = failure = abandoned = circ = derived = reported = 0
    w_success = w_complete = w_genuine = 0.0
    last_success = last_failure = None

    for o in outcomes:
        st, circumstance, src, on = o["outcome"], o.get("circumstance"), o.get("source"), o["evaluated_on"]
        w = decay_weight(age_months(on, today))
        if src == USER_REPORTED:
            reported += 1
        else:
            derived += 1
        iso = on.isoformat() if isinstance(on, date) else str(on)

        # E7: a failure attributed to circumstance is NOT a lever failure.
        if st == FAILED and circumstance:
            circ += 1
            last_failure = max(last_failure or iso, iso)
            continue

        w_genuine += w
        if st == SUCCESS:
            success += 1
            w_success += w
            w_complete += w
            last_success = max(last_success or iso, iso)
        elif st == PARTIAL:
            partial += 1
            w_complete += w
        elif st == FAILED:
            failure += 1
            last_failure = max(last_failure or iso, iso)
        elif st == ABANDONED:
            abandoned += 1
            last_failure = max(last_failure or iso, iso)

    evidence = success + partial + failure + abandoned + circ
    success_rate = (w_success / w_genuine) if w_genuine else 0.0
    completion_rate = (w_complete / w_genuine) if w_genuine else 0.0
    acceptance_rate = (accepted / total_feedback) if total_feedback else None
    level = trust_level(evidence)
    conclusion = _conclude(success_rate, failure + abandoned, circ, evidence)
    return LeverEffectiveness(
        lever_key=lever_key, success_count=success, failure_count=failure, abandoned_count=abandoned,
        circumstance_count=circ, evidence_count=evidence, derived_count=derived, reported_count=reported,
        trust_level=level, acceptance_rate=acceptance_rate, completion_rate=completion_rate,
        success_rate=success_rate, conclusion=conclusion, advisor_confidence=_confidence_phrase(level, evidence),
        last_success=last_success, last_failure=last_failure,
        contradictions=_contradictions(completion_rate, success_rate, acceptance_rate, evidence, success),
    )
