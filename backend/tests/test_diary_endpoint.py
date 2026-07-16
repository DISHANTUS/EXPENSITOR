"""Diary endpoints over real HTTP (response_model drops undeclared fields)."""

from __future__ import annotations

from datetime import date, timedelta

from httpx import AsyncClient

DIARY = "/api/v1/diary"


async def _auth(client: AsyncClient, email: str) -> dict[str, str]:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123", "full_name": "Marin"})
    tokens = (await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123"})).json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def test_writing_a_note_saves_it_and_asks_the_first_question(client: AsyncClient):
    headers = await _auth(client, "diary1@example.com")
    resp = await client.post(DIARY, headers=headers, json={"text": "went to the market and bought fruits"})
    assert resp.status_code == 201, resp.text
    body = resp.json()
    # Every field must survive serialization — that's why this is at HTTP level.
    assert body["entry"]["text"] == "went to the market and bought fruits"
    assert body["entry"]["details"] == []
    assert body["entry"]["closed"] is False
    assert body["question"] == "Which fruits?"


async def test_the_whole_branch_runs_end_to_end(client: AsyncClient):
    """The scenario as described: fruits -> list them -> juice -> amount."""
    headers = await _auth(client, "diary-branch@example.com")
    created = (await client.post(DIARY, headers=headers, json={"text": "bought fruits at the market"})).json()
    entry_id, q1 = created["entry"]["id"], created["question"]
    assert q1 == "Which fruits?"

    step2 = await client.post(f"{DIARY}/{entry_id}/answer", headers=headers,
                              json={"question": q1, "answer": "apples, mangoes and some juice"})
    assert step2.status_code == 200
    assert step2.json()["question"] == "Which juice?"          # from their ANSWER
    assert len(step2.json()["entry"]["details"]) == 1

    step3 = await client.post(f"{DIARY}/{entry_id}/answer", headers=headers,
                              json={"question": "Which juice?", "answer": "orange juice"})
    assert step3.json()["question"] == "Roughly what did that come to?"

    step4 = await client.post(f"{DIARY}/{entry_id}/answer", headers=headers,
                              json={"question": "Roughly what did that come to?", "answer": "about 300"})
    # Nothing left to ask -> the entry closes itself rather than pestering.
    assert step4.json()["question"] is None
    assert step4.json()["entry"]["closed"] is True
    assert len(step4.json()["entry"]["details"]) == 3


async def test_a_note_with_nothing_to_ask_is_just_saved(client: AsyncClient):
    headers = await _auth(client, "diary-quiet@example.com")
    body = (await client.post(DIARY, headers=headers, json={"text": "felt tired after class"})).json()
    assert body["question"] is None  # silence is a normal outcome


async def test_answers_persist_and_are_read_back(client: AsyncClient):
    headers = await _auth(client, "diary-persist@example.com")
    created = (await client.post(DIARY, headers=headers, json={"text": "bought fruits"})).json()
    entry_id = created["entry"]["id"]
    await client.post(f"{DIARY}/{entry_id}/answer", headers=headers,
                      json={"question": "Which fruits?", "answer": "apples"})

    entries = (await client.get(DIARY, headers=headers)).json()
    assert len(entries) == 1
    # The JSONB list must actually round-trip — a mutated-then-rebound list can
    # be missed by the ORM's change tracking and silently lose the answer.
    assert entries[0]["details"] == [{"question": "Which fruits?", "answer": "apples"}]


async def test_the_user_can_always_wave_the_questions_off(client: AsyncClient):
    headers = await _auth(client, "diary-close@example.com")
    entry_id = (await client.post(DIARY, headers=headers, json={"text": "bought fruits"})).json()["entry"]["id"]
    resp = await client.post(f"{DIARY}/{entry_id}/close", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["closed"] is True


async def test_a_deleted_entry_disappears_from_the_diary_and_the_patterns(client: AsyncClient):
    headers = await _auth(client, "diary-delete@example.com")
    entry_id = (await client.post(DIARY, headers=headers, json={"text": "bought mango"})).json()["entry"]["id"]
    assert (await client.delete(f"{DIARY}/{entry_id}", headers=headers)).status_code == 204
    assert (await client.get(DIARY, headers=headers)).json() == []
    # Deleting must remove it from learning immediately, not just from the list.
    assert (await client.get(f"{DIARY}/patterns", headers=headers)).json()["entries"] == 0


async def test_one_users_diary_is_never_another_users(client: AsyncClient):
    a = await _auth(client, "diary-a@example.com")
    b = await _auth(client, "diary-b@example.com")
    entry_id = (await client.post(DIARY, headers=a, json={"text": "bought fruits"})).json()["entry"]["id"]

    assert (await client.get(DIARY, headers=b)).json() == []
    assert (await client.post(f"{DIARY}/{entry_id}/close", headers=b)).status_code == 404
    assert (await client.delete(f"{DIARY}/{entry_id}", headers=b)).status_code == 404


async def test_patterns_stay_quiet_until_there_is_enough_to_say(client: AsyncClient):
    headers = await _auth(client, "diary-patterns-quiet@example.com")
    await client.post(DIARY, headers=headers, json={"text": "bought mango"})
    body = (await client.get(f"{DIARY}/patterns", headers=headers)).json()
    assert body["ready"] is False
    assert body["observations"] == []
    assert body["ask"] is None


async def test_patterns_surface_once_the_evidence_is_there(client: AsyncClient):
    headers = await _auth(client, "diary-patterns@example.com")
    today = date.today()
    # Five separate days, all mentioning mango.
    for i in range(5):
        resp = await client.post(DIARY, headers=headers, json={
            "text": "bought mango", "entry_date": (today - timedelta(days=i * 7)).isoformat(),
        })
        assert resp.status_code == 201, resp.text

    body = (await client.get(f"{DIARY}/patterns", headers=headers)).json()
    assert body["ready"] is True
    assert body["entries"] == 5
    assert any(o["word"] == "mango" for o in body["observations"])
    assert body["ask"]["word"] == "mango"
    # Same weekday every time (7-day steps) -> the weekday pattern must show.
    assert any(o["kind"] == "weekday" for o in body["observations"])


async def test_diary_requires_auth(client: AsyncClient):
    assert (await client.get(DIARY)).status_code == 401
    assert (await client.post(DIARY, json={"text": "x"})).status_code == 401
    assert (await client.get(f"{DIARY}/patterns")).status_code == 401


async def test_an_empty_note_is_rejected(client: AsyncClient):
    headers = await _auth(client, "diary-empty@example.com")
    assert (await client.post(DIARY, headers=headers, json={"text": ""})).status_code == 422


async def test_an_unknown_field_is_rejected(client: AsyncClient):
    headers = await _auth(client, "diary-extra@example.com")
    assert (await client.post(DIARY, headers=headers, json={"text": "x", "mood": "happy"})).status_code == 422


async def test_answering_an_entry_that_does_not_exist_is_a_404(client: AsyncClient):
    headers = await _auth(client, "diary-404@example.com")
    resp = await client.post(f"{DIARY}/00000000-0000-0000-0000-000000000000/answer",
                             headers=headers, json={"question": "q", "answer": "a"})
    assert resp.status_code == 404
