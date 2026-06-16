"""Endpoint/DB tests for Phase E: record, derive, effectiveness, adaptive, review."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PlannedExpense, User
from app.models.enums import PlannedExpenseStatus

pytestmark = pytest.mark.asyncio


async def _auth(client: AsyncClient, email: str) -> dict[str, str]:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123"})
    tokens = (await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123"})).json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def _report(client, h, **kw):
    return await client.post("/api/v1/outcomes", json=kw, headers=h)


async def test_report_and_list(client: AsyncClient):
    h = await _auth(client, "o1@e.com")
    r = await _report(client, h, kind="plan", subject_type="budget_session", outcome="success")
    assert r.status_code == 201
    items = (await client.get("/api/v1/outcomes", headers=h)).json()["items"]
    assert any(i["kind"] == "plan" and i["outcome"] == "success" for i in items)


async def test_circumstance_classified_on_report(client: AsyncClient):
    h = await _auth(client, "o2@e.com")
    r = (await _report(client, h, kind="recommendation", subject_type="recommendation_lever",
                       lever_key="reduce_food", outcome="failed", outcome_reason="a hospital visit")).json()
    assert r["circumstance"] == "medical"


async def test_effectiveness_separates_circumstance_E7(client: AsyncClient):
    h = await _auth(client, "o3@e.com")
    for _ in range(3):
        await _report(client, h, kind="recommendation", subject_type="recommendation_lever",
                      lever_key="reduce_food", outcome="success")
    for _ in range(2):
        await _report(client, h, kind="recommendation", subject_type="recommendation_lever",
                      lever_key="reduce_food", outcome="failed", outcome_reason="family wedding travel")
    eff = (await client.get("/api/v1/outcomes/effectiveness", headers=h)).json()["levers"]["reduce_food"]
    assert eff["success_count"] == 3 and eff["circumstance_count"] == 2 and eff["failure_count"] == 0
    assert eff["conclusion"] == "works_but_circumstances_interfere"


async def test_ineffective_lever_flagged_failing(client: AsyncClient):
    h = await _auth(client, "o4@e.com")
    for _ in range(3):
        await _report(client, h, kind="recommendation", subject_type="recommendation_lever",
                      lever_key="move_date", outcome="failed")
    plan = (await client.get("/api/v1/advisor/adaptive-plan", headers=h)).json()
    assert "move_date" in plan["strategies_that_fail"]


async def test_adaptive_and_learning_endpoints(client: AsyncClient):
    h = await _auth(client, "o5@e.com")
    assert (await client.get("/api/v1/advisor/adaptive-plan", headers=h)).status_code == 200
    lr = (await client.get("/api/v1/advisor/learning-review?period=monthly", headers=h)).json()
    assert "do_differently" in lr and "what_worked" in lr


async def test_planned_expense_outcome_derived(client: AsyncClient, db_session: AsyncSession):
    h = await _auth(client, "o6@e.com")
    uid = await db_session.scalar(select(User.id).where(User.email == "o6@e.com"))
    db_session.add(PlannedExpense(
        user_id=uid, title="Old plan", planned_date=date.today() - timedelta(days=40),
        original_amount=Decimal("1000"), original_currency="INR", exchange_rate=Decimal("1"),
        converted_amount=Decimal("1000"), base_currency="INR", status=PlannedExpenseStatus.completed))
    await db_session.commit()
    items = (await client.get("/api/v1/outcomes", headers=h)).json()["items"]   # GET triggers lazy sync
    assert any(i["kind"] == "plan" and i["subject_type"] == "planned_expense" and i["outcome"] == "success"
               for i in items)
