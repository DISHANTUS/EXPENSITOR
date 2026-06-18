"""Concise spoken replies for the Voice Conversation Layer (Sprint 5c, deterministic).

We never read a full report aloud. This condenses a verbose `ChatTurn`
(report / comparison / drilldown / forecast / recap / advisory / clarify) into ONE
useful spoken line + a navigation hint — "say the number, then show the graph".
Numbers are rounded to a friendly magnitude ("about 5,000 rupees"). No LLM.
"""

from __future__ import annotations

import re
from decimal import Decimal

from app.schemas.advisor_chat import ChatTurn

_CURRENCY_WORD = {
    "INR": "rupees", "USD": "dollars", "EUR": "euros", "GBP": "pounds", "JPY": "yen",
    "AUD": "dollars", "CAD": "dollars", "SGD": "dollars",
}


def _round_nice(v: Decimal) -> int:
    n = int(abs(v))
    if n >= 100_000:
        step = 10_000
    elif n >= 10_000:
        step = 1_000
    elif n >= 1_000:
        step = 1_000
    elif n >= 100:
        step = 50
    else:
        step = 10
    return int(round(n / step) * step) if step else n


def spoken_amount(v: Decimal | None, currency: str) -> str:
    """A speech-friendly, rounded amount: 5,320 -> 'about 5,000 rupees'."""
    if v is None:
        return ""
    word = _CURRENCY_WORD.get((currency or "").upper(), (currency or "").upper())
    return f"about {_round_nice(v):,} {word}".strip()


def _period_phrase(label: str) -> str:
    """Lower-case only relative labels ('This week' -> 'this week') mid-sentence;
    keep month names ('Jun 2026') as-is so they read naturally."""
    parts = label.split()
    if parts and parts[0] in ("This", "Last", "Yesterday", "Today", "So"):
        return label[0].lower() + label[1:]
    return label


def _first_chunk(msg: str, *, max_sentences: int = 2, max_len: int = 220) -> str:
    """First line / couple of sentences — long bulleted answers get a tail nudge."""
    msg = (msg or "").strip()
    if not msg:
        return "I’m not sure how to answer that one yet."
    head = msg.split("\n", 1)[0].strip()
    multi = "\n" in msg or msg.count("•") > 1
    sentences = re.split(r"(?<=[.!?])\s+", head)
    out = " ".join(sentences[:max_sentences]).strip()
    if len(out) > max_len:
        out = out[:max_len].rsplit(" ", 1)[0] + "…"
    if multi and not out.endswith("?"):
        out += " Want the rest?"
    return out


def summarize(turn: ChatTurn) -> tuple[str, str | None]:
    """Return (concise spoken line, navigate-hint | None)."""
    t = turn.type

    if t == "report" and turn.report:
        r = turn.report
        s = r.summary
        line = f"You spent {spoken_amount(s.total_spent, s.currency)} {_period_phrase(r.period_label)}"
        if s.saved and s.saved > 0:
            line += f", and saved {spoken_amount(s.saved, s.currency)}"
        line += "."
        if s.red_days:
            line += f" {s.red_days} day{'s' if s.red_days != 1 else ''} went over budget."
        return line + " Want the details?", "report"

    if t == "comparison" and turn.report and turn.report.delta:
        d = turn.report.delta
        if d.spent_change_pct is not None:
            direction = "more" if d.spent_change_pct >= 0 else "less"
            line = f"You’re spending about {abs(d.spent_change_pct):.0f} percent {direction} than the previous {turn.report.kind}."
            if d.biggest_increase:
                line += f" Mostly {d.biggest_increase.label.lower()}."
            return line, "report"
        return "I compared the two periods — want to see the breakdown?", "report"

    if t == "drilldown" and turn.drilldown:
        dd = turn.drilldown
        n = len(dd.items)
        if dd.kind == "red_days":
            return f"You had {n} red day{'s' if n != 1 else ''}.", "report"
        if dd.kind == "crown_days":
            return f"You stayed under budget on {n} day{'s' if n != 1 else ''}.", "report"
        tail = f", about {spoken_amount(dd.total, dd.currency)}" if dd.total else ""
        return f"{dd.title}: {n} item{'s' if n != 1 else ''}{tail}.", None

    if t == "forecast" and turn.forecast:
        fc = turn.forecast
        if fc.confidence == "insufficient" and fc.confidence_note:
            return fc.confidence_note, None
        line = fc.headline
        if fc.scenarios:
            line += " Want to hear the paths?"
        return line, None

    if t == "clarify":
        return (turn.message or "Which one did you mean?"), None
    if t == "follow_up" and turn.follow_up:
        return turn.follow_up.question, None
    if t == "reflection" and turn.reflection:
        return turn.reflection.question, None

    # help / tour: speak the steps and let the client open the named screen.
    if t in ("help", "tour"):
        return _first_chunk(turn.message or ""), turn.route

    # recap / advisory / answer / unsupported and anything else: trust the (short) message.
    return _first_chunk(turn.message or ""), turn.route
