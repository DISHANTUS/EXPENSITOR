"""Deterministic intent parser for the NL Action Layer (authoritative; no LLM).

Classifies an utterance into one intent and extracts structured fields. Emits
`missing` for required scalars it can't find (the caller then asks). Target-entity
resolution (which outing/goal/receivable) is done by the service against the DB.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from app.intelligence.nlp import entities

# intents
ADD_EXPENSE = "add_expense"
ADD_INCOME = "add_income"
ADD_RECEIVABLE = "add_receivable"
MARK_RECEIVABLE_RECEIVED = "mark_receivable_received"
MOVE_EVENT = "move_event"
CHANGE_SAVINGS_TARGET = "change_savings_target"
CREATE_SAVINGS_GOAL = "create_savings_goal"
BUY_DECISION = "buy_decision"
UNKNOWN = "unknown"

MUTATING = {ADD_EXPENSE, ADD_INCOME, ADD_RECEIVABLE, MARK_RECEIVABLE_RECEIVED, MOVE_EVENT,
            CHANGE_SAVINGS_TARGET, CREATE_SAVINGS_GOAL}

_OCCASIONS = ("outing", "date", "trip", "vacation", "party", "birthday", "festival",
              "celebration", "dinner", "movie", "event")


@dataclass(frozen=True)
class ParseResult:
    intent: str
    fields: dict[str, Any] = field(default_factory=dict)
    reason_context: str | None = None
    confidence: float = 0.0
    missing: tuple[str, ...] = ()

    @property
    def mutating(self) -> bool:
        return self.intent in MUTATING


def _classify(t: str) -> str:
    if re.search(r"\bmark\b.*\breceived\b", t) or re.search(r"\bgot\b.*\bback\b", t) or re.search(r"\breceived\b.*\bfrom\b", t):
        return MARK_RECEIVABLE_RECEIVED
    if re.search(r"\b(lent|loaned)\b", t) or re.search(r"\bgave\s+(?:a\s+)?loan\b", t):
        return ADD_RECEIVABLE                                   # I lent X -> X owes me
    if re.search(r"\bwill\s+(give|send|pay|transfer)\b", t) or re.search(r"\bowes?\b|\bexpecting\b", t):
        return ADD_RECEIVABLE
    if (re.search(r"\b(gave me|paid me|got paid)\b", t)
            or re.search(r"\b(received|got|earned)\b.*\b(salary|pay|income|bonus|refund|freelance)\b", t)
            or re.search(r"\b(salary|income|bonus|refund)\b.*\b(came|arrived|credited|received|in)\b", t)):
        return ADD_INCOME                                       # money I've already received
    if re.search(r"\b(move|reschedule|shift|postpone)\b", t):
        return MOVE_EVENT
    if re.search(r"\b(change|set|update|increase|decrease|raise|lower)\b.*\bsavings?\b.*\b(target|goal)\b", t) \
            or re.search(r"\bsavings?\s+(target|goal)\b.*\bto\b", t):
        return CHANGE_SAVINGS_TARGET
    if re.search(r"\bsave\b.*\b(this month|per month|monthly|a month)\b", t) or re.search(r"\bset\b.*\bsavings?\s+goal\b", t):
        return CREATE_SAVINGS_GOAL
    if re.search(r"\b(add|spent|spend|log|paid|record)\b", t):
        return ADD_EXPENSE
    if re.search(r"\b(buy|order|purchase|wanna|want to (?:buy|get|order))\b", t):
        return BUY_DECISION
    return UNKNOWN


def _target_label(t: str, intent: str) -> str | None:
    if intent == MOVE_EVENT:
        for occ in _OCCASIONS:
            if re.search(rf"\b{occ}\b", t):
                return occ
        return "event"
    if intent == CHANGE_SAVINGS_TARGET:
        m = re.search(r"\b(?:my\s+)?(\w+)\s+savings?\s+(?:target|goal)\b", t) or re.search(r"\b(?:my\s+)?(\w+)\s+goal\b", t)
        return m.group(1) if m else None
    return None


def parse(text: str, *, today: date, valid_category_names: set[str]) -> ParseResult:
    raw = text.strip()
    t = raw.lower()
    intent = _classify(t)
    if intent == UNKNOWN:
        return ParseResult(intent=UNKNOWN, confidence=0.0)

    amount, currency = entities.extract_amount(raw)
    when = entities.extract_date(raw, today)
    window, exact = entities.extract_time(raw)
    reason = entities.extract_reason_context(raw)

    fields: dict[str, Any] = {"amount": amount, "currency": currency, "date": when,
                              "time_window": window, "exact_time": exact}
    missing: list[str] = []

    if intent == ADD_EXPENSE:
        fields["category"] = entities.extract_category(raw, valid_category_names)
        if amount is None:
            missing.append("amount")
    elif intent == ADD_INCOME:
        fields["source_type"] = entities.extract_income_source_type(raw)
        if amount is None:
            missing.append("amount")
    elif intent == ADD_RECEIVABLE:
        name, stype = entities.extract_source(raw)
        fields["source_name"], fields["source_type"] = name, stype
        if amount is None:
            missing.append("amount")
        if name is None:
            missing.append("source_name")
    elif intent == MARK_RECEIVABLE_RECEIVED:
        name, _ = entities.extract_source(raw)
        fields["target_label"] = name
    elif intent == MOVE_EVENT:
        fields["target_label"] = _target_label(t, intent)
    elif intent == CHANGE_SAVINGS_TARGET:
        fields["target_label"] = _target_label(t, intent)
        if amount is None:
            missing.append("amount")
    elif intent == CREATE_SAVINGS_GOAL:
        fields["kind"] = "custom_goal" if when else "monthly_target"
        if amount is None:
            missing.append("amount")
    elif intent == BUY_DECISION:
        if amount is None:
            missing.append("amount")

    confidence = 1.0 if not missing else 0.5
    return ParseResult(intent=intent, fields=fields, reason_context=reason,
                       confidence=confidence, missing=tuple(missing))
