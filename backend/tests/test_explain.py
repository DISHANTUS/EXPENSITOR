"""4b-3 tests: explainability (evidence + confidence + relationship) + open-ended router."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

CHAT = "/api/v1/advisor/chat"
EXPLAIN = "/api/v1/advisor/explain"


async def _auth(client: AsyncClient, email: str) -> dict[str, str]:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123"})
    tokens = (await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123"})).json()
    h = {"Authorization": f"Bearer {tokens['access_token']}"}
    await client.patch("/api/v1/users/me/settings", json={"timezone": "UTC"}, headers=h)
    return h


def _today():
    return datetime.now(timezone.utc).date()


async def test_explain_impact_red_days_has_evidence_and_why(client: AsyncClient) -> None:
    h = await _auth(client, "ex1@example.com")
    today = _today().isoformat()
    await client.put(f"/api/v1/daily-plans/{today}", json={"planned_budget": "100"}, headers=h)
    await client.post("/api/v1/expenses",
                      json={"original_amount": "400", "original_currency": "INR", "expense_date": today}, headers=h)
    ex = (await client.post(EXPLAIN, json={"ref": "impact:red_days"}, headers=h)).json()
    assert ex["evidence"]
    assert ex["why_it_matters"] and "saving" in ex["why_it_matters"].lower()
    assert ex["confidence"] in ("low", "medium", "high")


async def test_explain_relationship_facts_no_judgement(client: AsyncClient) -> None:
    h = await _auth(client, "ex2@example.com")
    past = (_today() - timedelta(days=5)).isoformat()
    # One still pending (outstanding) + one returned late.
    await client.post("/api/v1/receivables",
                      json={"title": "Loan A", "source_name": "Ravi", "source_type": "friend", "kind": "one_time",
                            "original_amount": "3000", "original_currency": "INR", "expected_date": past}, headers=h)
    r2 = (await client.post("/api/v1/receivables",
                            json={"title": "Loan B", "source_name": "Ravi", "source_type": "friend", "kind": "one_time",
                                  "original_amount": "1000", "original_currency": "INR", "expected_date": past},
                            headers=h)).json()
    await client.patch(f"/api/v1/receivables/{r2['id']}", json={"status": "received"}, headers=h)

    ex = (await client.post(EXPLAIN, json={"ref": "relationship:Ravi"}, headers=h)).json()
    labels = {e["label"]: e["value"] for e in ex["evidence"]}
    assert labels["Loans"] == "2"
    assert labels["Late repayments"] == "1"
    assert "outstanding" in ex["claim"].lower()
    assert ex["confidence"] == "medium"  # 2 loans
    assert ex["confidence_word"] == "often"


async def test_chat_capability(client: AsyncClient) -> None:
    h = await _auth(client, "ex3@example.com")
    r = (await client.post(CHAT, json={"message": "what can you do?"}, headers=h)).json()
    assert r["type"] == "answer"
    assert "report" in r["message"].lower()


async def test_chat_who_owes_me(client: AsyncClient) -> None:
    h = await _auth(client, "ex4@example.com")
    fut = (_today() + timedelta(days=5)).isoformat()
    await client.post("/api/v1/receivables",
                      json={"title": "Lunch", "source_name": "Arun", "source_type": "friend", "kind": "one_time",
                            "original_amount": "500", "original_currency": "INR", "expected_date": fut}, headers=h)
    r = (await client.post(CHAT, json={"message": "who owes me money?"}, headers=h)).json()
    assert "Arun" in r["message"]


async def test_chat_relationship_advisory_is_explainable(client: AsyncClient) -> None:
    h = await _auth(client, "ex5@example.com")
    past = (_today() - timedelta(days=3)).isoformat()
    await client.post("/api/v1/receivables",
                      json={"title": "Loan", "source_name": "Ravi", "source_type": "friend", "kind": "one_time",
                            "original_amount": "5000", "original_currency": "INR", "expected_date": past}, headers=h)
    r = (await client.post(CHAT, json={"message": "should I lend more to Ravi?"}, headers=h)).json()
    assert r["type"] == "advisory"
    assert r["explain_ref"] == "relationship:Ravi"
    # "why" then re-explains using conversation memory.
    follow = (await client.post(CHAT, json={"message": "why", "session": r["session"]}, headers=h)).json()
    assert follow["type"] == "advisory"


async def test_chat_where_is_my_money(client: AsyncClient) -> None:
    h = await _auth(client, "ex6@example.com")
    today = _today().isoformat()
    sysid = (await client.get("/api/v1/categories", headers=h)).json()
    food = next(c["id"] for c in sysid if c["name"] == "Food & Dining")
    for amt in ("600", "300", "200"):
        await client.post("/api/v1/expenses",
                          json={"original_amount": amt, "original_currency": "INR", "expense_date": today,
                                "category_id": food}, headers=h)
    r = (await client.post(CHAT, json={"message": "where is my money going?"}, headers=h)).json()
    assert r["type"] == "answer"
    assert "Food & Dining" in r["message"]
    assert r["explain_ref"] == "category:Food & Dining"


async def test_chat_unknown_question_is_honest(client: AsyncClient) -> None:
    h = await _auth(client, "ex7@example.com")
    r = (await client.post(CHAT, json={"message": "tell me a joke"}, headers=h)).json()
    # No data + off-topic -> honest, not a fabricated answer.
    assert r["type"] == "answer"
    assert r["confidence"] == "insufficient" or "not sure" in (r["message"] or "").lower()
