"""POST /transactions/parse-sms — over real HTTP.

At the HTTP layer because response_model silently drops undeclared fields, and
because this endpoint stitches the parser to the learned-reason engine, which is
the whole value: a captured spend arrives with the user's own reasons ready to
tap.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.expense import Expense

PARSE = "/api/v1/transactions/parse-sms"


async def _auth(client: AsyncClient, email: str) -> tuple[uuid.UUID, dict[str, str]]:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123", "full_name": "T"})
    tokens = (await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123"})).json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    me = (await client.get("/api/v1/users/me", headers=headers)).json()
    return uuid.UUID(me["id"]), headers


async def test_a_real_debit_sms_becomes_an_expense_candidate(client: AsyncClient):
    _, headers = await _auth(client, "sms1@example.com")
    resp = await client.post(PARSE, headers=headers,
                             json={"text": "Rs.50.00 debited from a/c XX1 to VPA swiggy@ybl UPI Ref 9. -SBI"})
    assert resp.status_code == 200
    cand = resp.json()["candidate"]
    assert cand is not None
    # Every field must survive serialization.
    for field in ("kind", "direction", "amount", "merchant", "is_upi", "reasons", "raw"):
        assert field in cand
    assert cand["kind"] == "expense"
    assert cand["amount"] == "50.00"
    assert cand["merchant"] == "swiggy@ybl"


async def test_a_captured_spend_arrives_with_the_users_own_reasons(client: AsyncClient, db_session: AsyncSession):
    """The point of the whole slice: an auto-detected ₹50 debit comes back with
    the reasons this user gives for ~₹50 spends, ready to one-tap."""
    uid, headers = await _auth(client, "sms-reasons@example.com")
    today = date.today()
    for d in (1, 2, 3):
        db_session.add(Expense(
            user_id=uid, original_amount=Decimal("50"), original_currency="INR",
            exchange_rate=Decimal("1"), converted_amount=Decimal("50"), base_currency="INR",
            expense_date=today - timedelta(days=d), description="chai",
        ))
    await db_session.commit()

    cand = (await client.post(PARSE, headers=headers,
                              json={"text": "Rs 50 debited to shop@upi"})).json()["candidate"]
    assert "chai" in cand["reasons"], "the prompt should offer the user's learned reasons"


async def test_a_credit_sms_becomes_income_with_no_reason_chips(client: AsyncClient):
    # Income doesn't get spend-reason chips — they'd be nonsense for money in.
    _, headers = await _auth(client, "sms-credit@example.com")
    cand = (await client.post(PARSE, headers=headers,
                              json={"text": "a/c credited by Rs.5000 from dad@upi. -ICICI"})).json()["candidate"]
    assert cand["kind"] == "income"
    assert cand["reasons"] == []


async def test_an_otp_returns_no_candidate(client: AsyncClient):
    _, headers = await _auth(client, "sms-otp@example.com")
    resp = await client.post(PARSE, headers=headers,
                             json={"text": "123456 is your OTP for a payment of Rs 500. Do not share."})
    assert resp.status_code == 200
    assert resp.json()["candidate"] is None


async def test_nothing_is_created_by_parsing(client: AsyncClient, db_session: AsyncSession):
    # Parsing must never write an expense — the user confirms first. Verify the
    # ledger is still empty after a parse that DID produce a candidate.
    uid, headers = await _auth(client, "sms-noside@example.com")
    await client.post(PARSE, headers=headers, json={"text": "Rs 999 debited to shop@upi"})

    from sqlalchemy import func, select
    count = await db_session.scalar(select(func.count()).select_from(Expense).where(Expense.user_id == uid))
    assert count == 0, "parsing an SMS must not create an expense; the user confirms first"


async def test_requires_auth(client: AsyncClient):
    assert (await client.post(PARSE, json={"text": "Rs 50 debited to x@upi"})).status_code == 401


async def test_empty_text_is_rejected(client: AsyncClient):
    _, headers = await _auth(client, "sms-empty@example.com")
    assert (await client.post(PARSE, headers=headers, json={"text": ""})).status_code == 422


# --- receipt OCR endpoint ----------------------------------------------------

PARSE_RECEIPT = "/api/v1/transactions/parse-receipt"

_RECEIPT = """FRESH MART
Milk 1L   58.00
Bread     45.00
Grand Total  103.00
"""


async def test_a_receipt_becomes_a_candidate_with_items_and_reasons(client: AsyncClient, db_session: AsyncSession):
    uid, headers = await _auth(client, "receipt1@example.com")
    # A ~103 spend history so the total's chips are populated.
    from datetime import date, timedelta
    from decimal import Decimal as D
    for d in (1, 2, 3):
        db_session.add(Expense(
            user_id=uid, original_amount=D("103"), original_currency="INR",
            exchange_rate=D("1"), converted_amount=D("103"), base_currency="INR",
            expense_date=date.today() - timedelta(days=d), description="weekly groceries",
        ))
    await db_session.commit()

    resp = await client.post(PARSE_RECEIPT, headers=headers, json={"text": _RECEIPT})
    assert resp.status_code == 200
    cand = resp.json()["candidate"]
    assert cand is not None
    assert cand["total"] == "103.00"
    assert cand["merchant"] == "FRESH MART"
    names = {i["name"] for i in cand["items"]}
    assert {"Milk 1L", "Bread"} <= names
    for i in cand["items"]:
        assert {"name", "price"} <= set(i)          # fields survive serialization
    assert "weekly groceries" in cand["reasons"]


async def test_non_receipt_text_returns_no_candidate(client: AsyncClient):
    _, headers = await _auth(client, "receipt-none@example.com")
    resp = await client.post(PARSE_RECEIPT, headers=headers,
                             json={"text": "see you at 5pm, bring the charger"})
    assert resp.status_code == 200
    assert resp.json()["candidate"] is None


async def test_parsing_a_receipt_creates_nothing(client: AsyncClient, db_session: AsyncSession):
    uid, headers = await _auth(client, "receipt-noside@example.com")
    await client.post(PARSE_RECEIPT, headers=headers, json={"text": _RECEIPT})
    from sqlalchemy import func, select
    count = await db_session.scalar(select(func.count()).select_from(Expense).where(Expense.user_id == uid))
    assert count == 0, "parsing a receipt must not record anything; the user confirms"


async def test_receipt_requires_auth(client: AsyncClient):
    assert (await client.post(PARSE_RECEIPT, json={"text": "Total 50"})).status_code == 401
