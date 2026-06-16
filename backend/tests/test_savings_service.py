"""DB + endpoint tests: savings goals, recovery, income timing, dependencies."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

SAVINGS = "/api/v1/savings-goals"
FUTURE = (date.today() + timedelta(days=45)).isoformat()


async def _auth(client: AsyncClient, email: str) -> dict[str, str]:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123"})
    tokens = (await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123"})).json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def test_monthly_target_crud_and_state(client: AsyncClient):
    h = await _auth(client, "saver@e.com")
    created = await client.post(SAVINGS, json={
        "name": "Monthly savings", "kind": "monthly_target",
        "original_amount": "50000", "original_currency": "INR"}, headers=h)
    assert created.status_code == 201, created.text
    goal = created.json()
    assert goal["target_date"] is None and goal["converted_amount"] == "50000.0000"

    state = await client.get(f"{SAVINGS}/{goal['id']}/state", headers=h)
    assert state.status_code == 200
    body = state.json()
    # new user with no income -> behind, with 3 recovery options + an explanation
    assert body["state"]["status"] == "behind"
    assert {o["choice"] for o in body["recovery_options"]} == {"keep_unchanged", "distribute", "new_plan"}
    assert body["explanation"]["severity"] == "warning"


async def test_recovery_distribute_does_not_change_base_target(client: AsyncClient):
    h = await _auth(client, "recover@e.com")
    goal = (await client.post(SAVINGS, json={
        "name": "Monthly", "kind": "monthly_target", "original_amount": "50000", "original_currency": "INR"}, headers=h)).json()

    resp = await client.post(f"{SAVINGS}/{goal['id']}/recovery", json={"choice": "distribute", "distribute_months": 3}, headers=h)
    assert resp.status_code == 200, resp.text
    after = resp.json()
    assert after["recovery_mode"] == "distribute"
    assert float(after["carried_deficit"]) > 0
    assert after["original_amount"] == "50000.0000"        # base target NEVER auto-changed
    assert after["distribute_months"] == 3


async def test_recovery_reject_keeps_unchanged(client: AsyncClient):
    h = await _auth(client, "reject@e.com")
    goal = (await client.post(SAVINGS, json={
        "name": "Monthly", "kind": "monthly_target", "original_amount": "50000", "original_currency": "INR"}, headers=h)).json()
    resp = await client.post(f"{SAVINGS}/{goal['id']}/recovery", json={"choice": "keep_unchanged"}, headers=h)
    assert resp.status_code == 200
    assert resp.json()["recovery_mode"] == "keep_unchanged"
    assert resp.json()["carried_deficit"] == "0.0000"


async def test_custom_goal_state(client: AsyncClient):
    h = await _auth(client, "goal@e.com")
    goal = (await client.post(SAVINGS, json={
        "name": "RTX 6080", "kind": "custom_goal", "original_amount": "85000",
        "original_currency": "INR", "target_date": FUTURE}, headers=h)).json()
    state = await client.get(f"{SAVINGS}/{goal['id']}/state", headers=h)
    assert state.status_code == 200
    assert "progress" in state.json()["state"] and state.json()["explanation"]["headline"]


async def test_income_timing_window_persists(client: AsyncClient):
    h = await _auth(client, "timing@e.com")
    # income source carries an expected_time_window
    src = await client.post("/api/v1/income-sources", json={
        "label": "Dad allowance", "source_type": "gift", "kind": "one_time",
        "original_amount": "15000", "original_currency": "INR", "expected_date": FUTURE,
        "expected_time_window": "afternoon"}, headers=h)
    assert src.status_code == 201, src.text
    assert src.json()["expected_time_window"] == "afternoon"
    # receivable carries one too
    rec = await client.post("/api/v1/receivables", json={
        "title": "Rahul loan", "source_name": "Rahul", "source_type": "friend", "kind": "one_time",
        "original_amount": "5000", "original_currency": "INR", "expected_date": FUTURE,
        "expected_time_window": "evening"}, headers=h)
    assert rec.status_code == 201, rec.text
    assert rec.json()["expected_time_window"] == "evening"


async def test_dependencies_endpoint(client: AsyncClient):
    h = await _auth(client, "dep@e.com")
    resp = await client.get("/api/v1/advisor/dependencies", headers=h)
    assert resp.status_code == 200
    assert "dependencies" in resp.json() and "explanations" in resp.json()
