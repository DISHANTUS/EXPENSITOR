"""Calendar tests: day classification, markers, month grid, marker registry."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def _auth(client: AsyncClient, email: str = "cal@example.com") -> dict[str, str]:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123"})
    tokens = (await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123"})).json()
    h = {"Authorization": f"Bearer {tokens['access_token']}"}
    await client.patch("/api/v1/users/me/settings", json={"timezone": "UTC"}, headers=h)
    return h


def _today():
    return datetime.now(timezone.utc).date()


async def _add_expense(client, h, amount, day):
    return await client.post(
        "/api/v1/expenses",
        json={"original_amount": amount, "original_currency": "INR", "expense_date": day.isoformat()},
        headers=h,
    )


async def test_day_classification_saved_then_over(client: AsyncClient) -> None:
    h = await _auth(client)
    today = _today()
    await client.put(f"/api/v1/daily-plans/{today.isoformat()}", json={"planned_budget": "1000"}, headers=h)

    await _add_expense(client, h, "300", today)
    day = (await client.get(f"/api/v1/calendar/day/{today.isoformat()}", headers=h)).json()
    assert day["classification"] == "saved"
    assert "budget_saved" in day["markers"]
    assert day["remaining"] == "700.0000"

    await _add_expense(client, h, "800", today)  # total 1100 > 1000
    day = (await client.get(f"/api/v1/calendar/day/{today.isoformat()}", headers=h)).json()
    assert day["classification"] == "over"
    assert "budget_over" in day["markers"]


async def test_derived_budget_from_monthly_threshold(client: AsyncClient) -> None:
    h = await _auth(client, "cal2@example.com")
    await client.patch("/api/v1/users/me/settings", json={"monthly_threshold": "30000"}, headers=h)
    today = _today()
    day = (await client.get(f"/api/v1/calendar/day/{today.isoformat()}", headers=h)).json()
    # No explicit daily plan, so effective budget is derived (monthly/days_in_month).
    assert day["planned_budget"] is None
    assert day["effective_budget"] is not None


async def test_future_day_is_unclassified(client: AsyncClient) -> None:
    h = await _auth(client, "cal3@example.com")
    tomorrow = _today() + timedelta(days=1)
    await client.put(f"/api/v1/daily-plans/{tomorrow.isoformat()}", json={"planned_budget": "1000"}, headers=h)
    day = (await client.get(f"/api/v1/calendar/day/{tomorrow.isoformat()}", headers=h)).json()
    assert day["classification"] == "none"


async def test_month_grid_has_income_and_event_markers(client: AsyncClient) -> None:
    h = await _auth(client, "cal4@example.com")
    today = _today()
    await client.post(
        "/api/v1/incomes",
        json={"source_type": "salary", "original_amount": "5000", "original_currency": "INR",
              "received_date": today.isoformat()},
        headers=h,
    )
    await client.post(
        "/api/v1/planned-expenses",
        json={"title": "Dinner", "planned_date": today.isoformat(), "original_amount": "500",
              "original_currency": "INR", "occasion_type": "outing"},
        headers=h,
    )
    month = (await client.get(f"/api/v1/calendar/month?year={today.year}&month={today.month}", headers=h)).json()
    cell = next(c for c in month["days"] if c["date"] == today.isoformat())
    assert "income" in cell["markers"]
    assert "event" in cell["markers"]
    assert cell["event_count"] == 1


async def test_month_grid_materializes_recurring_and_lent_markers(client: AsyncClient) -> None:
    h = await _auth(client, "cal5@example.com")
    today = _today()
    # A subscription due on the 12th of this month.
    await client.post(
        "/api/v1/recurring-rules",
        json={"rule_type": "subscription", "label": "Netflix", "original_amount": "200",
              "original_currency": "INR", "recurrence_day": 12,
              "start_date": today.replace(day=1).isoformat()},
        headers=h,
    )
    # Lent money expected back on the 20th.
    due = today.replace(day=20)
    await client.post(
        "/api/v1/receivables",
        json={"title": "Loan to Ravi", "source_name": "Ravi", "source_type": "friend", "kind": "one_time",
              "original_amount": "3000", "original_currency": "INR", "expected_date": due.isoformat()},
        headers=h,
    )
    month = (await client.get(f"/api/v1/calendar/month?year={today.year}&month={today.month}", headers=h)).json()
    by_day = {c["date"]: c["markers"] for c in month["days"]}
    assert "subscription" in by_day[today.replace(day=12).isoformat()]
    assert "lent" in by_day[due.isoformat()]


async def test_marker_registry_is_complete(client: AsyncClient) -> None:
    # Public reference data — no auth needed.
    markers = (await client.get("/api/v1/calendar/marker-types")).json()
    keys = {m["key"] for m in markers}
    for expected in ("budget_over", "budget_saved", "income", "event", "lent", "subscription", "emi"):
        assert expected in keys
    sample = next(m for m in markers if m["key"] == "budget_over")
    assert sample["icon"] and sample["color"] and sample["category"] == "budget"
