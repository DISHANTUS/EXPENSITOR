"""Payables — borrowed money the user owes (AI-intervention foundation)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def _auth(client: AsyncClient, email: str = "payable@example.com") -> dict[str, str]:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123"})
    tok = (await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123"})).json()
    h = {"Authorization": f"Bearer {tok['access_token']}"}
    await client.patch("/api/v1/users/me/settings", json={"base_currency": "INR", "timezone": "UTC"}, headers=h)
    return h


async def test_create_borrowed_money(client: AsyncClient) -> None:
    h = await _auth(client)
    r = await client.post("/api/v1/payables", json={
        "source_name": "Arun", "original_amount": "5000", "original_currency": "INR",
        "return_expectation": "required", "due_date": "2026-08-15", "reason": "Short on rent"}, headers=h)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["source_name"] == "Arun"
    assert float(body["converted_amount"]) == 5000
    assert body["status"] == "open" and body["return_expectation"] == "required"
    assert body["days_overdue"] == 0


async def test_relationship_support_has_no_repayment(client: AsyncClient) -> None:
    h = await _auth(client, "payable2@example.com")
    r = await client.post("/api/v1/payables", json={
        "source_name": "Pranav", "original_amount": "500", "original_currency": "INR",
        "return_expectation": "not_expected"}, headers=h)
    assert r.status_code == 201, r.text
    assert r.json()["return_expectation"] == "not_expected"
    assert r.json()["due_date"] is None


async def test_overdue_is_derived(client: AsyncClient) -> None:
    h = await _auth(client, "payable3@example.com")
    r = await client.post("/api/v1/payables", json={
        "source_name": "Old debt", "original_amount": "100", "original_currency": "INR",
        "due_date": "2020-01-01"}, headers=h)
    assert r.json()["days_overdue"] > 0


async def test_settle_marks_settled_at(client: AsyncClient) -> None:
    h = await _auth(client, "payable4@example.com")
    pid = (await client.post("/api/v1/payables", json={
        "source_name": "Arun", "original_amount": "5000", "original_currency": "INR"}, headers=h)).json()["id"]
    r = await client.patch(f"/api/v1/payables/{pid}", json={"status": "settled"}, headers=h)
    assert r.status_code == 200
    assert r.json()["status"] == "settled" and r.json()["settled_at"] is not None


async def test_payables_are_separate_from_receivables(client: AsyncClient) -> None:
    # Borrowed money must NOT appear as a receivable (it would pollute income).
    h = await _auth(client, "payable5@example.com")
    await client.post("/api/v1/payables", json={
        "source_name": "Arun", "original_amount": "5000", "original_currency": "INR"}, headers=h)
    receivables = (await client.get("/api/v1/receivables", headers=h)).json()
    assert receivables["total"] == 0
    payables = (await client.get("/api/v1/payables", headers=h)).json()
    assert payables["total"] == 1


async def test_repayment_plan_reuses_affordability(client: AsyncClient) -> None:
    h = await _auth(client, "payable_plan@example.com")
    await client.post("/api/v1/income-sources", json={
        "label": "Salary", "source_type": "salary", "kind": "recurring",
        "original_amount": "50000", "original_currency": "INR", "recurrence_day": 1}, headers=h)
    pid = (await client.post("/api/v1/payables", json={
        "source_name": "Kaguya", "original_amount": "5000", "original_currency": "INR"}, headers=h)).json()["id"]

    r = await client.post(f"/api/v1/payables/{pid}/repayment-plan",
                          json={"target_date": "2026-12-15", "preference": "gradual"}, headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["who"] == "Kaguya"
    assert isinstance(body["feasible"], bool)
    assert body["verdict"] in ("affordable", "conditional", "unaffordable")
    assert body["monthly_pace"] and isinstance(body["impact"], list) and body["impact"]


async def test_repayment_plan_404_for_unknown_payable(client: AsyncClient) -> None:
    h = await _auth(client, "payable_plan2@example.com")
    r = await client.post("/api/v1/payables/00000000-0000-0000-0000-000000000000/repayment-plan",
                          json={"target_date": "2026-12-15"}, headers=h)
    assert r.status_code == 404


async def test_accept_plan_records_commitment_and_shows_in_timeline(client: AsyncClient) -> None:
    h = await _auth(client, "payable_commit@example.com")
    pid = (await client.post("/api/v1/payables", json={
        "source_name": "Kaguya", "original_amount": "5000", "original_currency": "INR"}, headers=h)).json()["id"]

    r = await client.post(f"/api/v1/payables/{pid}/commit-repayment",
                          json={"target_date": "2026-08-15", "preference": "gradual"}, headers=h)
    assert r.status_code == 200, r.text
    fact = r.json()["fact"]
    assert fact["type"] == "repayment_commitment"
    assert fact["person"] == "Kaguya"
    assert fact["commitment_status"] == "active"

    # the commitment becomes a timeline entry (the follow-up engine remembers it)
    tl = await client.get("/api/v1/timeline", headers=h)
    assert tl.status_code == 200, tl.text
    assert "Kaguya" in tl.text and "Committed to repay" in tl.text


async def test_amount_must_be_positive(client: AsyncClient) -> None:
    h = await _auth(client, "payable6@example.com")
    r = await client.post("/api/v1/payables", json={
        "source_name": "x", "original_amount": "0", "original_currency": "INR"}, headers=h)
    assert r.status_code == 422
