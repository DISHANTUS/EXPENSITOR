"""Bank-SMS parsing: catch real transactions, reject everything that isn't one.

The two failure modes that matter, in order:
  - a false positive (an OTP saying "Rs 500" becoming a ₹500 expense) erodes
    trust faster than anything, so most of this file is rejection.
  - then: on a real transaction, get the amount, direction and merchant right.

Formats below are close to what Indian banks (SBI, HDFC, ICICI, Axis, etc.)
actually send for UPI, card and transfers.
"""

from __future__ import annotations

import pytest

from app.intelligence.companion import sms_parser as sms


# --- real transactions get parsed ------------------------------------------


@pytest.mark.parametrize(
    "text,kind,amount,merchant",
    [
        ("Rs.50.00 debited from a/c XX1234 on 17-Jul-26 to VPA zomato@paytm UPI Ref 123. -SBI",
         "expense", "50.00", "zomato@paytm"),
        ("INR 2,000.00 spent on your HDFC Bank Card at BIGBAZAAR on 17-07-26",
         "expense", "2000.00", "BIGBAZAAR"),
        ("Rs 250 debited via UPI to swiggy@ybl on 17Jul. -Axis Bank",
         "expense", "250", "swiggy@ybl"),
        ("Your a/c XX5678 credited by Rs.5000 on 17Jul26 by UPI from RAMESH KUMAR. -ICICI",
         "income", "5000", "RAMESH KUMAR"),
        ("₹120.00 debited towards electricity@upi on 17/07/2026",
         "expense", "120.00", "electricity@upi"),
        ("INR 15,750.50 credited to your account from ACME PAYROLL. -HDFC",
         "income", "15750.50", "ACME PAYROLL"),
    ],
)
def test_a_real_transaction_is_parsed(text, kind, amount, merchant):
    out = sms.parse(text)
    assert out is not None, "this is a real transaction and should parse"
    assert out["kind"] == kind
    assert out["amount"] == amount
    assert out["merchant"] == merchant


def test_direction_maps_to_expense_or_income():
    assert sms.parse("Rs 50 debited to shop@upi")["kind"] == "expense"
    assert sms.parse("Rs 50 credited from dad@upi")["kind"] == "income"


def test_upi_is_flagged_when_present():
    assert sms.parse("Rs 50 debited via UPI to shop@upi")["is_upi"] is True
    assert sms.parse("Rs 2000 spent on your Card at BIGBAZAAR")["is_upi"] is False


def test_a_known_merchant_seeds_a_reason_but_an_unknown_one_does_not():
    # A guess is offered only when there's a real merchant to base it on.
    assert sms.parse("Rs 50 debited to swiggy@ybl")["suggested_reason"] == "swiggy@ybl"
    assert sms.parse("Rs 50 debited from a/c XX1")["suggested_reason"] is None


def test_the_raw_text_is_kept():
    text = "Rs 50 debited to shop@upi"
    assert sms.parse(text)["raw"] == text


# --- everything that is NOT a transaction is rejected ----------------------


@pytest.mark.parametrize(
    "text",
    [
        # OTPs — the classic false positive: they name an amount but aren't a spend.
        "123456 is your OTP for a transaction of Rs 500 at Amazon. Do not share.",
        "Your one-time password is 8842. Valid for a payment of Rs.2000.",
        # Promos / marketing.
        "Get 10% cashback offer up to Rs 200 on your next UPI payment! T&C apply.",
        "MEGA SALE: flat Rs 1000 discount. Shop now and win exciting prizes!",
        # Balance pings — no transaction happened.
        "Available balance in a/c XX1234 is Rs 12,500.00 as on 17-Jul.",
        # Scheduled / future — hasn't happened yet.
        "Rs 999 will be debited on 20-Jul for your Netflix e-mandate.",
        "Reminder: minimum amount due Rs 3,500 on your card is due on 25-Jul.",
        # Requests — someone asking, not a completed payment.
        "RAHUL is requesting Rs 300 via UPI. Approve in your app.",
        # Failures / reversals.
        "Your payment of Rs 500 failed. Please try again.",
        "Rs 250 transaction was declined due to insufficient balance.",
        # Genuinely unrelated.
        "Your order has been shipped and will arrive tomorrow.",
    ],
)
def test_a_non_transaction_sms_is_rejected(text):
    assert sms.parse(text) is None, f"should NOT be treated as a transaction: {text!r}"


def test_a_transaction_with_no_amount_is_rejected():
    # Direction word but no rupee amount -> not actionable.
    assert sms.parse("Your account was debited today. Check your statement.") is None


def test_a_bare_number_without_a_currency_marker_is_not_an_amount():
    # "debited 50" with no Rs/INR/₹ is too weak a signal.
    assert sms.parse("account debited 50 points as reward") is None


def test_empty_and_whitespace_are_rejected():
    assert sms.parse("") is None
    assert sms.parse("   ") is None


def test_an_otp_that_also_says_debited_still_loses():
    # The nastiest false positive: contains BOTH "otp" and "debited". Reject.
    text = "OTP 4471 to authorise Rs 5000 being debited from your account."
    assert sms.parse(text) is None
