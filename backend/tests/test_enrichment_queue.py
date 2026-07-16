"""The catch-up queue: park what the model missed, run it when it's back.

Two things this must never do, and most of the file is about them:
  - never break or slow a user's request (they already have their answer)
  - never leak a user's words to the developer (counts only, always)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.enrichment_job import (
    KIND_DIARY_FOLLOWUP,
    STATUS_DONE,
    STATUS_PENDING,
    STATUS_SKIPPED,
    EnrichmentJob,
)
from app.services import enrichment_service, mail_service

DIARY = "/api/v1/diary"
DEV = "/api/v1/dev/enrichment"


async def _auth(client: AsyncClient, email: str) -> dict[str, str]:
    await client.post("/api/v1/auth/register", json={"email": email, "password": "Password123", "full_name": "Marin"})
    tokens = (await client.post("/api/v1/auth/login", json={"email": email, "password": "Password123"})).json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def _dev_auth(client: AsyncClient) -> dict[str, str]:
    # The allow-list email gets developer access (see deps.is_developer).
    return await _auth(client, "advary2006@gmail.com")


# --- what gets parked, and what doesn't -----------------------------------


async def test_a_note_the_rules_cannot_read_is_parked_for_the_model(client: AsyncClient, db_session):
    # Tests run with OLLAMA_ENABLED off (conftest pins it), which is exactly the
    # "no model reachable" case this queue exists for.
    headers = await _auth(client, "park1@example.com")
    resp = await client.post(DIARY, headers=headers, json={"text": "spent the afternoon at the barber"})
    assert resp.status_code == 201
    assert resp.json()["question"] is None  # the rules had nothing — the user waits on nothing

    jobs = (await db_session.execute(select(EnrichmentJob))).scalars().all()
    assert len(jobs) == 1
    assert jobs[0].kind == KIND_DIARY_FOLLOWUP
    assert jobs[0].status == STATUS_PENDING


async def test_a_note_the_rules_answered_is_not_parked(client: AsyncClient, db_session):
    # The rules found the question. There is nothing for a model to catch up on,
    # and queueing it would mean work whose result gets thrown away.
    headers = await _auth(client, "park2@example.com")
    resp = await client.post(DIARY, headers=headers, json={"text": "bought fruits today"})
    assert resp.json()["question"] == "Which fruits?"

    jobs = (await db_session.execute(select(EnrichmentJob))).scalars().all()
    assert jobs == []


async def test_an_entry_we_have_asked_enough_about_is_closed_not_parked(client: AsyncClient, db_session):
    """"No question because we've asked our fill" and "no question because
    nothing could see one" are different answers. The cap is final — no model
    can ever get past it — so parking it would queue a job guaranteed to do
    nothing, and leaving it open would keep a finished entry open forever."""
    headers = await _auth(client, "capped@example.com")
    created = (await client.post(DIARY, headers=headers, json={"text": "bought fruits at the market"})).json()
    entry_id = created["entry"]["id"]

    for question, answer in [
        ("Which fruits?", "apples, mangoes and some juice"),
        ("Which juice?", "orange juice"),
        ("Roughly what did that come to?", "about 300"),
    ]:
        last = await client.post(f"{DIARY}/{entry_id}/answer", headers=headers,
                                 json={"question": question, "answer": answer})

    assert last.json()["question"] is None
    assert last.json()["entry"]["closed"] is True  # done, not waiting on anything

    # And nothing was queued for a model that could never add to it.
    jobs = (await db_session.execute(select(EnrichmentJob))).scalars().all()
    assert jobs == []


async def test_an_entry_still_worth_asking_about_stays_open_and_parked(client: AsyncClient, db_session):
    # The other side of the same coin: under the cap, with no model to look,
    # the entry stays open and gets parked for later.
    headers = await _auth(client, "notcapped@example.com")
    created = (await client.post(DIARY, headers=headers, json={"text": "spent the afternoon at the barber"})).json()
    assert created["entry"]["closed"] is False

    jobs = (await db_session.execute(select(EnrichmentJob))).scalars().all()
    assert len(jobs) == 1


async def test_parking_never_reaches_the_user(client: AsyncClient, monkeypatch):
    # The note is what matters. If the queue itself breaks, the user must still
    # get a clean 201 and their entry — this is a bonus, never a gate.
    async def boom(*args, **kwargs):
        raise RuntimeError("queue is on fire")

    monkeypatch.setattr(enrichment_service, "enqueue_diary_followup", boom)
    headers = await _auth(client, "park3@example.com")
    resp = await client.post(DIARY, headers=headers, json={"text": "spent the afternoon at the barber"})
    assert resp.status_code == 201
    assert resp.json()["entry"]["text"] == "spent the afternoon at the barber"


# --- draining --------------------------------------------------------------


async def test_draining_without_a_model_does_nothing_rather_than_failing_everything(client, db_session):
    headers = await _auth(client, "drain1@example.com")
    await client.post(DIARY, headers=headers, json={"text": "spent the afternoon at the barber"})

    result = await enrichment_service.drain(db_session)
    assert result["ran"] is False
    assert result["pending"] == 1  # still parked, not burned through as failures


async def test_a_drained_job_puts_the_question_on_the_entry(client: AsyncClient, db_session, monkeypatch):
    headers = await _auth(client, "drain2@example.com")
    created = (await client.post(DIARY, headers=headers, json={"text": "spent the afternoon at the barber"})).json()
    entry_id = created["entry"]["id"]

    # The model comes up.
    monkeypatch.setattr(enrichment_service, "model_available", lambda: True)

    async def fake_complete(messages):
        return "How long were you at the barber?"

    monkeypatch.setattr(enrichment_service.ollama_service, "complete", fake_complete)

    result = await enrichment_service.drain(db_session)
    assert result["ran"] is True
    assert result["done"] == 1
    assert result["pending"] == 0

    # And the user finds it waiting next time they look.
    entries = (await client.get(DIARY, headers=headers)).json()
    assert entries[0]["pending_question"] == "How long were you at the barber?"
    assert entries[0]["id"] == entry_id


async def test_a_model_with_nothing_to_add_is_not_retried_forever(client, db_session, monkeypatch):
    headers = await _auth(client, "drain3@example.com")
    await client.post(DIARY, headers=headers, json={"text": "spent the afternoon at the barber"})

    monkeypatch.setattr(enrichment_service, "model_available", lambda: True)

    async def says_nothing(messages):
        return "NONE"

    monkeypatch.setattr(enrichment_service.ollama_service, "complete", says_nothing)

    result = await enrichment_service.drain(db_session)
    assert result["skipped"] == 1
    assert result["pending"] == 0  # a real answer ("nothing to ask"), not a failure


async def test_a_users_choice_to_wave_off_beats_a_stale_job(client: AsyncClient, db_session, monkeypatch):
    headers = await _auth(client, "drain4@example.com")
    entry_id = (await client.post(DIARY, headers=headers, json={"text": "spent the afternoon at the barber"})).json()["entry"]["id"]
    await client.post(f"{DIARY}/{entry_id}/close", headers=headers)

    monkeypatch.setattr(enrichment_service, "model_available", lambda: True)

    async def never_called(messages):
        raise AssertionError("the model must not be asked about a closed entry")

    monkeypatch.setattr(enrichment_service.ollama_service, "complete", never_called)

    result = await enrichment_service.drain(db_session)
    assert result["skipped"] == 1


async def test_a_deleted_entry_is_dropped_from_the_queue_not_resurrected(client, db_session, monkeypatch):
    headers = await _auth(client, "drain5@example.com")
    entry_id = (await client.post(DIARY, headers=headers, json={"text": "spent the afternoon at the barber"})).json()["entry"]["id"]
    await client.delete(f"{DIARY}/{entry_id}", headers=headers)

    monkeypatch.setattr(enrichment_service, "model_available", lambda: True)
    result = await enrichment_service.drain(db_session)
    assert result["skipped"] == 1


async def test_one_bad_job_does_not_stop_the_drain(client: AsyncClient, db_session, monkeypatch):
    headers = await _auth(client, "drain6@example.com")
    for _ in range(3):
        await client.post(DIARY, headers=headers, json={"text": "spent the afternoon at the barber"})

    monkeypatch.setattr(enrichment_service, "model_available", lambda: True)
    calls = {"n": 0}

    async def flaky(messages):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("model hiccup")
        return "How long were you at the barber?"

    monkeypatch.setattr(enrichment_service.ollama_service, "complete", flaky)

    result = await enrichment_service.drain(db_session)
    assert result["processed"] == 3
    assert result["done"] == 2  # the other two still landed


async def test_a_job_that_keeps_failing_eventually_stops(db_session, client, monkeypatch):
    headers = await _auth(client, "drain7@example.com")
    await client.post(DIARY, headers=headers, json={"text": "spent the afternoon at the barber"})

    monkeypatch.setattr(enrichment_service, "model_available", lambda: True)

    async def always_broken(messages):
        raise RuntimeError("still broken")

    monkeypatch.setattr(enrichment_service.ollama_service, "complete", always_broken)

    for _ in range(enrichment_service.MAX_ATTEMPTS + 2):
        await enrichment_service.drain(db_session)

    job = (await db_session.execute(select(EnrichmentJob))).scalars().first()
    await db_session.refresh(job)
    assert job.attempts <= enrichment_service.MAX_ATTEMPTS  # not ground forever


# --- the developer view ----------------------------------------------------


async def test_the_developer_summary_is_counts_only(client: AsyncClient):
    """The privacy guarantee, pinned. A developer looking at the queue must not
    be able to read what a beta tester wrote in their diary."""
    user = await _auth(client, "private@example.com")
    await client.post(DIARY, headers=user, json={"text": "my deepest darkest secret about mangoes"})

    dev = await _dev_auth(client)
    resp = await client.get(DEV, headers=dev)
    assert resp.status_code == 200
    body = resp.json()
    assert body["pending"] == 1

    # Nothing the user wrote, and no way to identify them, anywhere in it.
    blob = str(body).lower()
    assert "secret" not in blob
    assert "mango" not in blob
    assert "private@example.com" not in blob


async def test_the_summary_says_whether_this_deployment_can_mail(client: AsyncClient, monkeypatch):
    """"Did my env vars take?" must be answerable at a glance. Otherwise the
    only way to find out is to wait a day for a mail that may never come."""
    dev = await _dev_auth(client)

    body = (await client.get(DEV, headers=dev)).json()
    assert body["mail_configured"] is False  # nothing configured in tests

    monkeypatch.setattr(mail_service, "configured", lambda: True)
    body = (await client.get(DEV, headers=dev)).json()
    assert body["mail_configured"] is True


async def test_the_summary_reports_mail_status_without_leaking_the_credentials(client, monkeypatch):
    # A bool, never the settings themselves. A developer screen that echoes the
    # host's secrets back out is a worse problem than the one it solves.
    monkeypatch.setattr(mail_service, "configured", lambda: True)
    monkeypatch.setattr(mail_service.app_settings, "SMTP_PASSWORD", "supersecretapppassword")
    monkeypatch.setattr(mail_service.app_settings, "SMTP_USERNAME", "sender@example.com")

    dev = await _dev_auth(client)
    blob = str((await client.get(DEV, headers=dev)).json()).lower()
    assert "supersecret" not in blob
    assert "sender@example.com" not in blob
    assert "smtp" not in blob


async def test_the_queue_is_developer_only(client: AsyncClient):
    normal = await _auth(client, "notadev@example.com")
    assert (await client.get(DEV, headers=normal)).status_code == 403
    assert (await client.post(f"{DEV}/drain", headers=normal)).status_code == 403


async def test_the_queue_requires_auth(client: AsyncClient):
    assert (await client.get(DEV)).status_code == 401
    assert (await client.post(f"{DEV}/drain")).status_code == 401


async def test_drain_over_http_is_safe_with_no_model(client: AsyncClient):
    dev = await _dev_auth(client)
    resp = await client.post(f"{DEV}/drain", headers=dev)
    assert resp.status_code == 200
    assert resp.json()["ran"] is False


# --- the developer mail ----------------------------------------------------


def test_mail_is_off_unless_configured():
    # The default everywhere including tests: no SMTP settings, no mail.
    assert mail_service.configured() is False


async def test_an_unconfigured_digest_is_a_no_op(db_session):
    assert await mail_service.maybe_send_backlog_digest(db_session, 5) is False


async def test_the_digest_never_fires_on_an_empty_backlog(db_session, monkeypatch):
    monkeypatch.setattr(mail_service, "configured", lambda: True)
    assert await mail_service.maybe_send_backlog_digest(db_session, 0) is False


async def test_the_digest_is_a_count_and_nothing_else(db_session, monkeypatch):
    """The mail body is built from an int. There is no parameter that could
    carry a diary entry even by mistake."""
    monkeypatch.setattr(mail_service, "configured", lambda: True)
    sent: dict[str, str] = {}

    async def capture(subject, body):
        sent["subject"], sent["body"] = subject, body
        return True

    monkeypatch.setattr(mail_service, "send", capture)

    assert await mail_service.maybe_send_backlog_digest(db_session, 7) is True
    assert "7 things waiting" in sent["subject"]
    assert "7 things" in sent["body"]
    assert "count only" in sent["body"]


async def test_the_digest_is_rate_limited_to_once_a_day(db_session, monkeypatch):
    monkeypatch.setattr(mail_service, "configured", lambda: True)
    calls = {"n": 0}

    async def counting(subject, body):
        calls["n"] += 1
        return True

    monkeypatch.setattr(mail_service, "send", counting)

    assert await mail_service.maybe_send_backlog_digest(db_session, 3) is True
    # Every note written today must not become a separate mail.
    for _ in range(5):
        assert await mail_service.maybe_send_backlog_digest(db_session, 4) is False
    assert calls["n"] == 1


async def test_the_digest_comes_round_again_the_next_day(db_session, monkeypatch):
    monkeypatch.setattr(mail_service, "configured", lambda: True)
    monkeypatch.setattr(mail_service, "send", lambda subject, body: _true())

    async def _true():
        return True

    assert await mail_service.maybe_send_backlog_digest(db_session, 3) is True

    # Wind the clock back past the window.
    yesterday = datetime.now(timezone.utc) - timedelta(hours=mail_service.DIGEST_MIN_INTERVAL_HOURS + 1)
    await mail_service._mark_sent(db_session, yesterday)

    assert await mail_service.maybe_send_backlog_digest(db_session, 3) is True


async def test_a_failing_mail_server_never_becomes_a_mail_loop(db_session, monkeypatch):
    # The rate limit is marked BEFORE sending on purpose: a half-broken SMTP
    # must not turn into a mail per request. Missing one digest is nothing.
    monkeypatch.setattr(mail_service, "configured", lambda: True)
    calls = {"n": 0}

    async def failing(subject, body):
        calls["n"] += 1
        return False

    monkeypatch.setattr(mail_service, "send", failing)

    assert await mail_service.maybe_send_backlog_digest(db_session, 3) is False
    assert await mail_service.maybe_send_backlog_digest(db_session, 3) is False
    assert calls["n"] == 1


async def test_a_broken_mail_server_never_breaks_a_diary_write(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(mail_service, "configured", lambda: True)

    def explode(*args, **kwargs):
        raise RuntimeError("smtp is down")

    monkeypatch.setattr(mail_service, "_send_blocking", explode)

    headers = await _auth(client, "mailbroken@example.com")
    resp = await client.post(DIARY, headers=headers, json={"text": "bought fruits"})
    assert resp.status_code == 201
