"""Decision-modifier orchestrator (C7a-2).

Runs every applicable analyzer over one AnalyzerCtx. Input-driven analyzers that
lack their data contribute QUESTIONS (deduped by key — asked once); satisfied or
auto analyzers contribute FINDINGS. The influence step is asked first when the
user hasn't said what influenced the purchase. Stateless; nothing is assumed.
"""

from __future__ import annotations

from typing import Any

import app.intelligence.decision.modifiers  # noqa: F401  (registers analyzers)
from app.intelligence.decision.modifiers.base import (
    INFLUENCE_QUESTION,
    MODIFIER_REGISTRY,
    AnalyzerCtx,
)


def run(ctx: AnalyzerCtx) -> dict[str, Any]:
    findings = []
    questions = []
    if ctx.inputs.involves is None:
        questions.append(INFLUENCE_QUESTION)

    for analyzer in MODIFIER_REGISTRY.values():
        if not analyzer.trigger(ctx):
            continue
        missing = analyzer.required_inputs(ctx)
        if missing:
            questions.extend(missing)
        else:
            finding = analyzer.run(ctx)
            if finding is not None:
                findings.append(finding)

    # Ask each input once even if several analyzers need it (Information Utility Rule).
    seen: set[str] = set()
    deduped = []
    for q in questions:
        if q.key in seen:
            continue
        seen.add(q.key)
        deduped.append(q)

    return {
        "findings": [f.as_dict() for f in findings],
        "pending_questions": [q.as_dict() for q in deduped],
        "_findings": findings,  # raw, for the advisor wrapper
    }
