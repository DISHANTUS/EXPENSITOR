"""Disaster-recovery gate: create real data → export → wipe → restore → verify
login still works and the data survived. This is the release gate the backup
system exists for. Also checks the snapshot mechanics (FK order, reference-data
exclusion, type round-tripping)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base
from app.models import SavingsGoal, User
from app.services import backup_service

pytestmark = pytest.mark.asyncio

_EMAIL = "recover@example.com"
_PW = "Password123"


async def _seed_user_with_data(client: AsyncClient) -> dict[str, str]:
    await client.post("/api/v1/auth/register", json={"email": _EMAIL, "password": _PW})
    tok = (await client.post("/api/v1/auth/login", json={"email": _EMAIL, "password": _PW})).json()
    h = {"Authorization": f"Bearer {tok['access_token']}"}
    await client.patch("/api/v1/users/me/settings",
                       json={"base_currency": "INR", "timezone": "UTC", "display_name": "Aoi"}, headers=h)
    await client.post("/api/v1/income-sources", json={
        "label": "Salary", "source_type": "salary", "kind": "recurring",
        "original_amount": "60000", "original_currency": "INR", "recurrence_day": 1}, headers=h)
    await client.post("/api/v1/savings-goals", json={
        "name": "Japan Fund", "kind": "custom_goal", "original_amount": "300000",
        "original_currency": "INR", "target_date": "2027-12-01"}, headers=h)
    await client.post("/api/v1/receivables", json={
        "title": "Loan to Ravi", "source_name": "Ravi", "source_type": "friend", "kind": "one_time",
        "original_amount": "5000", "original_currency": "INR", "expected_date": "2026-12-10"}, headers=h)
    return h


async def _wipe_user(db: AsyncSession, user_id) -> None:
    """Delete just this user's rows (children before parents), so the shared test
    DB and its seed data are untouched."""
    for table in reversed(backup_service._tables()):
        if "user_id" in table.c:
            await db.execute(delete(table).where(table.c.user_id == user_id))
    await db.execute(delete(User.__table__).where(User.__table__.c.id == user_id))
    await db.commit()


async def test_disaster_recovery_roundtrip(client: AsyncClient, db_session: AsyncSession):
    await _seed_user_with_data(client)
    user_id = (await db_session.execute(select(User.id).where(User.email == _EMAIL))).scalar_one()

    # Snapshot the whole DB, then prove the export captured this user's data.
    snapshot = await backup_service.export_state(db_session)
    emails = {r["email"] for r in snapshot["tables"]["users"]}
    goals = {r["name"] for r in snapshot["tables"]["savings_goals"]}
    assert _EMAIL in emails
    assert "Japan Fund" in goals
    # Regenerable reference data is deliberately NOT in a user backup.
    assert "currencies" not in snapshot["tables"]
    assert "exchange_rates" not in snapshot["tables"]

    # Disaster: this user and everything they own is gone.
    await _wipe_user(db_session, user_id)
    gone = await client.post("/api/v1/auth/login", json={"email": _EMAIL, "password": _PW})
    assert gone.status_code in (400, 401)

    # Restore from the snapshot.
    inserted = await backup_service.import_state(db_session, snapshot)
    await db_session.commit()
    assert inserted["users"] >= 1
    assert inserted["savings_goals"] >= 1

    # The login works again with the ORIGINAL password (hash survived)…
    back = await client.post("/api/v1/auth/login", json={"email": _EMAIL, "password": _PW})
    assert back.status_code == 200
    h = {"Authorization": f"Bearer {back.json()['access_token']}"}

    # …and the data is all back.
    goals = (await client.get("/api/v1/savings-goals", headers=h)).json()
    assert any(g["name"] == "Japan Fund" for g in (goals if isinstance(goals, list) else goals.get("items", [])))
    recv = (await client.get("/api/v1/receivables", headers=h)).json()
    assert any(r["source_name"] == "Ravi" for r in (recv if isinstance(recv, list) else recv.get("items", [])))
    me = (await client.get("/api/v1/users/me/settings", headers=h)).json()
    assert me["base_currency"] == "INR" and me.get("display_name") == "Aoi"


async def test_import_is_idempotent(client: AsyncClient, db_session: AsyncSession):
    """Re-importing a snapshot into a DB that already has the rows inserts nothing."""
    await client.post("/api/v1/auth/register", json={"email": "idem@example.com", "password": _PW})
    snapshot = await backup_service.export_state(db_session)
    inserted = await backup_service.import_state(db_session, snapshot)
    await db_session.commit()
    assert sum(inserted.values()) == 0


async def test_tables_in_fk_dependency_order(db_session: AsyncSession):
    """users must be exported before any table that references it, so restore
    inserts parents first."""
    names = [t.name for t in backup_service._tables()]
    assert "users" in names
    assert names.index("users") < names.index("savings_goals")
    assert names.index("users") < names.index("user_settings")
