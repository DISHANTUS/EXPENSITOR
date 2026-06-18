"""Budget derivation tests (income − commitments − goals → monthly/weekly/daily)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def _auth(client: AsyncClient, email: str = "budget@example.com") -> dict[str, str]:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123"})
    tokens = (await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123"})).json()
    h = {"Authorization": f"Bearer {tokens['access_token']}"}
    await client.patch("/api/v1/users/me/settings", json={"timezone": "UTC", "monthly_income_estimate": "30000"}, headers=h)
    return h


async def test_budget_summary_and_apply(client: AsyncClient) -> None:
    h = await _auth(client)
    today = datetime.now(timezone.utc).date().isoformat()

    # A subscription commitment + a monthly savings target.
    await client.post(
        "/api/v1/recurring-rules",
        json={"rule_type": "subscription", "label": "Netflix", "original_amount": "500",
              "original_currency": "INR", "recurrence_day": 10, "start_date": today},
        headers=h,
    )
    await client.post(
        "/api/v1/savings-goals",
        json={"name": "Japan fund", "kind": "monthly_target", "original_amount": "1000",
              "original_currency": "INR"},
        headers=h,
    )

    s = (await client.get("/api/v1/budget/summary", headers=h)).json()
    assert s["monthly_income"] == "30000.0000"
    assert s["monthly_commitments"] == "500.0000"
    assert s["monthly_goal_contributions"] == "1000.0000"
    assert s["monthly_discretionary"] == "28500.0000"
    assert float(s["daily_budget"]) > 0

    # Apply writes monthly_threshold so the calendar's derived budget uses it.
    applied = (await client.post("/api/v1/budget/apply", headers=h)).json()
    assert applied["monthly_discretionary"] == "28500.0000"
    settings = (await client.get("/api/v1/users/me/settings", headers=h)).json()
    assert settings["monthly_threshold"] == "28500.0000"
