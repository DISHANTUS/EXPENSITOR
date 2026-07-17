"""Per-user product price learning: record confirmed receipt items, and tell the
user what they usually pay.

Two things guarded: the numbers are right (median, robust to one odd buy), and
it's strictly the user's OWN prices — one person's shopping never becomes
another's "usual".
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import item_price_service as svc

TODAY = date(2026, 7, 17)


async def _uid(client: AsyncClient, email: str = "price@example.com") -> tuple[uuid.UUID, dict[str, str]]:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123", "full_name": "P"})
    tokens = (await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123"})).json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    me = (await client.get("/api/v1/users/me", headers=headers)).json()
    return uuid.UUID(me["id"]), headers


# --- the maths --------------------------------------------------------------


async def test_no_history_has_no_usual_price(db_session, client):
    uid, _ = await _uid(client)
    assert await svc.typical(db_session, uid, "milk", today=TODAY) is None


async def test_one_observation_is_not_yet_a_usual(db_session, client):
    uid, _ = await _uid(client)
    await svc.record(db_session, uid, items=[{"name": "Milk 1L", "price": "58"}], currency="INR", observed_on=TODAY)
    # A single data point is a fact, not a "usual".
    assert await svc.typical(db_session, uid, "Milk 1L", today=TODAY) is None


async def test_the_usual_price_is_the_median_not_the_mean(db_session, client):
    uid, _ = await _uid(client)
    # An old bulk-buy at 200, then normal buys at 60, 58 and most-recently 55.
    # Median of [55,58,60,200] is 59 — the outlier doesn't move it; a mean would
    # be dragged to ~93.
    for p, d in [("200", 4), ("60", 3), ("58", 2), ("55", 1)]:
        await svc.record(db_session, uid, items=[{"name": "milk", "price": p}],
                         currency="INR", observed_on=TODAY - timedelta(days=d))
    info = await svc.typical(db_session, uid, "milk", today=TODAY)
    assert info["observations"] == 4
    assert info["typical_price"] == "59.00"
    assert info["last_price"] == "55.00"       # most recent observation


async def test_casing_and_spacing_fold_to_one_item(db_session, client):
    uid, _ = await _uid(client)
    for name in ("Milk 1L", "milk 1l", "  MILK  1L "):
        await svc.record(db_session, uid, items=[{"name": name, "price": "58"}], currency="INR", observed_on=TODAY)
    info = await svc.typical(db_session, uid, "milk 1l", today=TODAY)
    assert info is not None and info["observations"] == 3


async def test_junk_lines_are_not_stored_as_prices(db_session, client):
    uid, _ = await _uid(client)
    stored = await svc.record(db_session, uid, items=[
        {"name": "Milk", "price": "58"},
        {"name": "", "price": "10"},              # no name
        {"name": "x", "price": "10"},             # too short
        {"name": "Bread", "price": "0"},          # non-positive
        {"name": "Eggs", "price": "not a number"},
    ], currency="INR", observed_on=TODAY)
    assert stored == 1                            # only Milk


async def test_a_stale_price_is_not_counted_as_usual(db_session, client):
    uid, _ = await _uid(client)
    # Two observations, but both over a year ago.
    for d in (400, 420):
        await svc.record(db_session, uid, items=[{"name": "milk", "price": "58"}],
                         currency="INR", observed_on=TODAY - timedelta(days=d))
    assert await svc.typical(db_session, uid, "milk", today=TODAY) is None


# --- privacy: own prices only -----------------------------------------------


async def test_one_users_prices_never_become_anothers_usual(db_session, client):
    a, _ = await _uid(client, "price-a@example.com")
    b, _ = await _uid(client, "price-b@example.com")
    for d in (1, 2, 3):
        await svc.record(db_session, a, items=[{"name": "milk", "price": "58"}],
                         currency="INR", observed_on=TODAY - timedelta(days=d))
    # B never bought milk — must have no usual, however much A did.
    assert await svc.typical(db_session, b, "milk", today=TODAY) is None


# --- over HTTP: parse annotates, confirm records ----------------------------


async def test_recording_then_parsing_shows_the_usual_price(client: AsyncClient):
    """The loop: confirm a couple of receipts, then a new scan of the same item
    shows 'you usually pay X'."""
    _, headers = await _uid(client, "price-loop@example.com")
    today = date.today().isoformat()
    for _ in range(2):
        r = await client.post("/api/v1/transactions/record-items", headers=headers, json={
            "items": [{"name": "Milk 1L", "price": "58"}], "currency": "INR", "observed_on": today,
        })
        assert r.status_code == 200 and r.json()["stored"] == 1

    cand = (await client.post("/api/v1/transactions/parse-receipt", headers=headers,
                              json={"text": "FRESH MART\nMilk 1L 60.00\nTotal 60\n"})).json()["candidate"]
    milk = next(i for i in cand["items"] if i["name"] == "Milk 1L")
    assert milk["price"] == "60.00"              # this receipt
    assert milk["typical_price"] == "58.00"      # what they usually pay
    assert milk["observations"] == 2


async def test_record_items_requires_auth(client: AsyncClient):
    resp = await client.post("/api/v1/transactions/record-items",
                             json={"items": [{"name": "x", "price": "1"}], "currency": "INR"})
    assert resp.status_code == 401


async def test_parsing_alone_stores_no_prices(client: AsyncClient, db_session: AsyncSession):
    # Only a confirm records; a parse must not. (Same discipline as the expense.)
    uid, headers = await _uid(client, "price-noside@example.com")
    await client.post("/api/v1/transactions/parse-receipt", headers=headers,
                      json={"text": "Shop\nPen 20\nTotal 20\n"})
    from sqlalchemy import func, select
    from app.models.item_price import ItemPrice
    count = await db_session.scalar(select(func.count()).select_from(ItemPrice).where(ItemPrice.user_id == uid))
    assert count == 0
