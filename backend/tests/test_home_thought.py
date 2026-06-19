"""Home "thought" (UI-X) — contextual goal/receivable/milestone reflection + mood."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def _auth(client: AsyncClient, email: str = "thought@example.com") -> dict[str, str]:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123"})
    tok = (await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123"})).json()
    h = {"Authorization": f"Bearer {tok['access_token']}"}
    await client.patch("/api/v1/users/me/settings", json={"base_currency": "INR", "timezone": "UTC"}, headers=h)
    return h


async def test_default_thought_when_empty(client: AsyncClient):
    h = await _auth(client)
    t = (await client.get("/api/v1/companion/home-thought", headers=h)).json()
    # With nothing user-specific, the orb stays quiet (no lines) — the Home screen
    # shows the "Did You Know" fact card instead, so a fact lives in only one place.
    assert t["lines"] == []
    assert t["mood"] == "idle"


async def test_composes_goal_receivable_and_milestone(client: AsyncClient):
    h = await _auth(client)
    await client.post("/api/v1/income-sources", json={
        "label": "Salary", "source_type": "salary", "kind": "recurring",
        "original_amount": "50000", "original_currency": "INR", "recurrence_day": 1}, headers=h)
    await client.post("/api/v1/savings-goals", json={
        "name": "Japan Fund", "kind": "monthly_target", "original_amount": "2000", "original_currency": "INR"}, headers=h)
    await client.post("/api/v1/receivables", json={
        "title": "Loan to Ravi", "source_name": "Ravi", "source_type": "friend", "kind": "one_time",
        "original_amount": "3000", "original_currency": "INR", "expected_date": "2026-12-10"}, headers=h)
    await client.patch("/api/v1/users/me/profile", json={
        "moving_country": True, "future_country": "jp", "future_move_year": 2028}, headers=h)

    t = (await client.get("/api/v1/companion/home-thought", headers=h)).json()
    blob = " ".join(t["lines"]).lower()
    assert "japan fund" in blob                 # goal status
    assert "ravi" in blob and "3,000" in blob    # who owes
    assert "moving to japan" in blob and "2028" in blob   # milestone


async def test_dated_goal_thought_is_specific(client: AsyncClient):
    """A dated goal's line is concrete — a pace toward its target month, or an
    ahead/behind-by-N-days reading — never just a vague 'on track'."""
    h = await _auth(client, email="dated@example.com")
    await client.post("/api/v1/income-sources", json={
        "label": "Salary", "source_type": "salary", "kind": "recurring",
        "original_amount": "60000", "original_currency": "INR", "recurrence_day": 1}, headers=h)
    await client.post("/api/v1/savings-goals", json={
        "name": "Japan Fund", "kind": "custom_goal", "original_amount": "300000",
        "original_currency": "INR", "target_date": "2027-12-01"}, headers=h)

    t = (await client.get("/api/v1/companion/home-thought", headers=h)).json()
    goal = next((ln for ln in t["lines"] if "japan fund" in ln.lower()), "")
    assert goal
    # Specific: a month/year, a per-month figure, or a days-early/behind reading.
    assert ("2027" in goal or "/month" in goal or "days" in goal)
