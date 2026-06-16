"""Adaptive planning (E2) — rerank + annotate C9 recommendations by outcome history.

Pure + deterministic. Outcomes influence ORDERING/RANKING/CONFIDENCE/ANNOTATIONS
ONLY — never the recommendations' financial fields. Strong down-rank is reserved
for genuine ineffectiveness (E7); circumstance-limited levers stay recommended.
Surfaces contradictions (mod 6) as adaptive insights.
"""

from __future__ import annotations

from typing import Any

from app.intelligence.outcomes.effectiveness import (
    LeverEffectiveness,
    USUALLY_DOESNT_WORK,
    USUALLY_WORKS,
    WORKS_BUT_CIRCUMSTANCES,
)

# outcome-signal deltas applied to a rec's existing C9 score (ordering only)
_DELTA = {USUALLY_WORKS: 0.25, USUALLY_DOESNT_WORK: -0.5, WORKS_BUT_CIRCUMSTANCES: 0.0}


def _confidence_block(eff: LeverEffectiveness | None) -> dict[str, Any]:
    if eff is None:
        return {"advisor_confidence": "Still learning.", "evidence_count": 0, "trust_level": "low",
                "last_success": None, "last_failure": None, "conclusion": "still_learning"}
    return {"advisor_confidence": eff.advisor_confidence, "evidence_count": eff.evidence_count,
            "trust_level": eff.trust_level, "last_success": eff.last_success,
            "last_failure": eff.last_failure, "conclusion": eff.conclusion}


def build_plan(recommendations: list[dict[str, Any]], effectiveness: dict[str, LeverEffectiveness]) -> dict[str, Any]:
    annotated, boosted, downranked = [], [], []
    for rec in recommendations:
        lever = rec.get("lever_key")
        eff = effectiveness.get(lever)
        delta = _DELTA.get(eff.conclusion, 0.0) if eff else 0.0
        block = _confidence_block(eff)
        # rerank key only — the rec's financial fields are copied through untouched
        item = {**rec, "advisor_learning": block, "_rank": float(rec.get("score", 0.0)) + delta}
        annotated.append(item)
        if delta > 0:
            boosted.append(lever)
        elif delta < 0:
            downranked.append(lever)

    annotated.sort(key=lambda r: r["_rank"], reverse=True)
    for r in annotated:
        r.pop("_rank", None)

    works = [lev for lev, e in effectiveness.items() if e.conclusion == USUALLY_WORKS]
    fails = [lev for lev, e in effectiveness.items() if e.conclusion == USUALLY_DOESNT_WORK]
    circumstance_limited = [lev for lev, e in effectiveness.items() if e.conclusion == WORKS_BUT_CIRCUMSTANCES]
    contradictions = [{"lever_key": lev, "kind": c, "evidence_count": e.evidence_count, "trust_level": e.trust_level}
                      for lev, e in effectiveness.items() for c in e.contradictions]

    return {
        "recommendations": annotated,
        "strategies_that_work": works,
        "strategies_that_fail": fails,
        "circumstance_limited": circumstance_limited,        # E7 third conclusion
        "contradictions": contradictions,                    # mod 6
        "outcome_influence": {"boosted": boosted, "downranked": downranked},
    }
