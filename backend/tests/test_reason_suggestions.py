"""Learned reason suggestions: rank the user's own past reasons for a spend.

The two things that matter here — every chip is the user's OWN past wording
(never invented, never another user's), and the ranking actually surfaces the
right one — so that's what this file guards.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.expense import Expense
from app.services import reason_suggestion_service as svc

SUGGEST = "/api/v1/expenses/reason-suggestions"
TODAY = date(2026, 7, 16)  # a Thursday


async def _spend(db: AsyncSession, user_id, *, amount, day, desc, category_id=None):
    db.add(Expense(
        user_id=user_id, original_amount=Decimal(amount), original_currency="INR",
        exchange_rate=Decimal("1"), converted_amount=Decimal(amount), base_currency="INR",
        expense_date=day, description=desc, category_id=category_id,
    ))


async def _reasons(db, user_id, **kw):
    return [r["reason"] for r in await svc.suggest(db, user_id, **kw)]


# --- cold start --------------------------------------------------------------


async def test_no_history_gives_no_suggestions(db_session, client):
    # A blank box is honest. Inventing reasons for a brand-new user is not.
    uid = await _new_user(client)
    assert await svc.suggest(db_session, uid, amount=Decimal("50"), on_date=TODAY) == []


async def test_a_one_off_reason_is_not_offered_as_a_habit(db_session, client):
    uid = await _new_user(client)
    await _spend(db_session, uid, amount="50", day=TODAY - timedelta(days=1), desc="one time thing")
    await db_session.commit()
    # Used once -> below the min-uses bar -> not a learned chip.
    assert await _reasons(db_session, uid, amount=Decimal("50"), on_date=TODAY) == []


# --- the core loop -----------------------------------------------------------


async def test_a_reason_used_before_comes_back_as_a_suggestion(db_session, client):
    # The whole point: type "chai" twice and it's offered next time.
    uid = await _new_user(client)
    for d in (2, 1):
        await _spend(db_session, uid, amount="50", day=TODAY - timedelta(days=d), desc="chai")
    await db_session.commit()
    assert "chai" in await _reasons(db_session, uid, amount=Decimal("50"), on_date=TODAY)


async def test_the_reason_usually_given_for_this_amount_ranks_first(db_session, client):
    uid = await _new_user(client)
    # "chai" is the ₹50 reason; "groceries" is the ₹2000 reason. Both used plenty.
    for d in range(3, 15):
        await _spend(db_session, uid, amount="50", day=TODAY - timedelta(days=d), desc="chai")
    for d in (4, 8, 12):
        await _spend(db_session, uid, amount="2000", day=TODAY - timedelta(days=d), desc="groceries")
    await db_session.commit()

    # Spending ~₹50 -> chai on top; ~₹2000 -> groceries on top. Same history,
    # different spend, different best guess.
    assert (await _reasons(db_session, uid, amount=Decimal("55"), on_date=TODAY))[0] == "chai"
    assert (await _reasons(db_session, uid, amount=Decimal("1900"), on_date=TODAY))[0] == "groceries"


async def test_casing_and_spacing_fold_into_one_reason(db_session, client):
    uid = await _new_user(client)
    for desc in ("Chai", "chai ", "  CHAI"):
        await _spend(db_session, uid, amount="50", day=TODAY - timedelta(days=2), desc=desc)
    await db_session.commit()
    out = await svc.suggest(db_session, uid, amount=Decimal("50"), on_date=TODAY)
    chai = [r for r in out if r["reason"].strip().lower() == "chai"]
    assert len(chai) == 1 and chai[0]["uses"] == 3   # three writes, one chip


async def test_a_stale_reason_yields_to_a_fresh_one(db_session, client):
    uid = await _new_user(client)
    # "old habit" used a lot, but months ago. "new habit" used recently.
    for d in range(90, 110):
        await _spend(db_session, uid, amount="100", day=TODAY - timedelta(days=d), desc="old habit")
    for d in (1, 2, 3, 4):
        await _spend(db_session, uid, amount="100", day=TODAY - timedelta(days=d), desc="new habit")
    await db_session.commit()
    out = await _reasons(db_session, uid, amount=Decimal("100"), on_date=TODAY)
    assert out and out[0] == "new habit"


async def test_weekday_rhythm_is_picked_up(db_session, client):
    uid = await _new_user(client)
    # "market" every Thursday; "misc" scattered on other days. Same amount.
    for w in range(1, 7):
        await _spend(db_session, uid, amount="300", day=TODAY - timedelta(days=7 * w), desc="market")
    for d in (2, 4, 6, 9, 11):  # non-Thursdays
        await _spend(db_session, uid, amount="300", day=TODAY - timedelta(days=d), desc="misc")
    await db_session.commit()
    # On a Thursday, "market" should be offered (weekday fit lifts it).
    assert "market" in await _reasons(db_session, uid, amount=Decimal("300"), on_date=TODAY)


# --- privacy: only ever the user's own words ---------------------------------


async def test_one_users_reasons_never_leak_to_another(client: AsyncClient, db_session):
    a = await _new_user(client, "reason-a@example.com")
    b = await _new_user(client, "reason-b@example.com")
    for d in (1, 2, 3):
        await _spend(db_session, a, amount="50", day=TODAY - timedelta(days=d), desc="a-secret-reason")
    await db_session.commit()

    # B has no history and must see nothing — A's reasons are A's alone.
    assert await svc.suggest(db_session, b, amount=Decimal("50"), on_date=TODAY) == []


async def test_a_deleted_expenses_reason_stops_being_suggested(db_session, client):
    uid = await _new_user(client)
    for d in (1, 2, 3):
        await _spend(db_session, uid, amount="50", day=TODAY - timedelta(days=d), desc="temporary")
    await db_session.commit()
    assert "temporary" in await _reasons(db_session, uid, amount=Decimal("50"), on_date=TODAY)

    from sqlalchemy import update
    from datetime import datetime, timezone
    await db_session.execute(
        update(Expense).where(Expense.user_id == uid).values(deleted_at=datetime.now(timezone.utc))
    )
    await db_session.commit()
    assert "temporary" not in await _reasons(db_session, uid, amount=Decimal("50"), on_date=TODAY)


# --- over HTTP ---------------------------------------------------------------


async def test_the_endpoint_returns_learned_reasons(client: AsyncClient, db_session):
    uid = await _new_user(client, "reason-http@example.com", return_headers=True)
    headers = uid[1]
    for d in (1, 2, 3):
        await _spend(db_session, uid[0], amount="120", day=date.today() - timedelta(days=d), desc="lunch")
    await db_session.commit()

    resp = await client.get(SUGGEST, headers=headers, params={"amount": "120"})
    assert resp.status_code == 200
    body = resp.json()
    assert any(r["reason"] == "lunch" for r in body)
    # Fields survive serialization (response_model drops undeclared ones).
    assert all({"reason", "uses", "last_used"} <= set(r) for r in body)


async def test_the_endpoint_requires_auth(client: AsyncClient):
    assert (await client.get(SUGGEST)).status_code == 401


async def test_a_new_user_endpoint_returns_empty_not_an_error(client: AsyncClient):
    _, headers = await _new_user(client, "reason-empty@example.com", return_headers=True)
    resp = await client.get(SUGGEST, headers=headers, params={"amount": "50"})
    assert resp.status_code == 200
    assert resp.json() == []


# --- helpers -----------------------------------------------------------------


async def _new_user(client: AsyncClient, email: str = "reason@example.com", *, return_headers: bool = False):
    await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123", "full_name": "R"})
    tokens = (await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123"})).json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    me = (await client.get("/api/v1/users/me", headers=headers)).json()
    uid = uuid.UUID(me["id"])
    return (uid, headers) if return_headers else uid
