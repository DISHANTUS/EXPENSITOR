"""Pure tests for the deterministic NL parser (authoritative; no LLM)."""

from __future__ import annotations

from datetime import date, time
from decimal import Decimal

from app.intelligence.nlp import parser as nlp

TODAY = date(2026, 6, 1)
CATS = {"Food & Dining", "Rent & Housing", "Shopping", "Transportation", "Entertainment", "Groceries"}


def _p(text):
    return nlp.parse(text, today=TODAY, valid_category_names=CATS)


def test_add_expense():
    r = _p("add ₹250 lunch expense")
    assert r.intent == nlp.ADD_EXPENSE
    assert r.fields["amount"] == Decimal("250") and r.fields["category"] == "Food & Dining"
    assert r.missing == ()


def test_add_expense_missing_amount_asks():
    r = _p("add lunch expense")
    assert r.intent == nlp.ADD_EXPENSE and "amount" in r.missing


def test_move_event():
    r = _p("Move outing to July 18")
    assert r.intent == nlp.MOVE_EVENT
    assert r.fields["target_label"] == "outing" and r.fields["date"] == date(2026, 7, 18)


def test_add_receivable_with_time_window():
    r = _p("Father will give ₹15,000 on June 20 evening")
    assert r.intent == nlp.ADD_RECEIVABLE
    assert r.fields["amount"] == Decimal("15000")
    assert r.fields["source_name"] == "Father" and r.fields["source_type"] == "family"
    assert r.fields["date"] == date(2026, 6, 20) and r.fields["time_window"] == "evening"


def test_add_receivable_exact_time():
    r = _p("Rahul will send ₹5000 at 5pm on June 24")
    assert r.intent == nlp.ADD_RECEIVABLE
    assert r.fields["exact_time"] == time(17, 0) and r.fields["time_window"] == "evening"


def test_change_savings_target():
    r = _p("Change my phone savings target to ₹40,000")
    assert r.intent == nlp.CHANGE_SAVINGS_TARGET
    assert r.fields["target_label"] == "phone" and r.fields["amount"] == Decimal("40000")


def test_mark_receivable_received():
    r = _p("Mark Rahul's receivable as received")
    assert r.intent == nlp.MARK_RECEIVABLE_RECEIVED and r.fields["target_label"] == "Rahul"


def test_buy_decision():
    r = _p("I want to buy a phone for ₹30,000")
    assert r.intent == nlp.BUY_DECISION and r.fields["amount"] == Decimal("30000")


def test_create_monthly_savings_goal():
    r = _p("I want to save ₹50,000 this month")
    assert r.intent == nlp.CREATE_SAVINGS_GOAL
    assert r.fields["amount"] == Decimal("50000") and r.fields["kind"] == "monthly_target"


def test_relative_date_and_unknown():
    assert _p("add ₹100 expense tomorrow").fields["date"] == date(2026, 6, 2)
    assert _p("what's the weather like").intent == nlp.UNKNOWN
