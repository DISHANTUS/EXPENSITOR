"""Developer alerts. Counts only — never anyone's data.

The one rule this module exists to enforce: **no user content leaves the
server.** The developer is told HOW MANY things are waiting, never what anyone
wrote. Beta testers handed over a private diary and their money; nobody agreed
to have it forwarded to an inbox. The API here physically cannot carry a diary
entry — it takes an int.

Entirely optional. With no SMTP settings configured this is a no-op that returns
False, which is the normal state in development and in tests. It must never be
able to break a request: every caller treats a failure as "no mail today".

There is no scheduler in this app, so the digest is triggered by the work
arriving and rate-limited to once a day via a system flag. That means it only
fires when something actually happened — which is the whole point ("mail me so
I know to turn my backend on").
"""

from __future__ import annotations

import asyncio
import logging
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings as app_settings
from app.models.system_flag import SystemFlag

logger = logging.getLogger(__name__)

DIGEST_FLAG_KEY = "dev_digest_last_sent"
DIGEST_MIN_INTERVAL_HOURS = 20  # "once a day", with slack so a slightly early run still counts


def configured() -> bool:
    return bool(
        app_settings.SMTP_HOST
        and app_settings.SMTP_USERNAME
        and app_settings.SMTP_PASSWORD
        and app_settings.DEVELOPER_EMAILS
    )


def _send_blocking(subject: str, body: str, recipients: list[str]) -> None:
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = app_settings.SMTP_FROM or app_settings.SMTP_USERNAME
    message["To"] = ", ".join(recipients)
    message.set_content(body)

    with smtplib.SMTP(app_settings.SMTP_HOST, app_settings.SMTP_PORT, timeout=20) as smtp:
        smtp.starttls()
        smtp.login(app_settings.SMTP_USERNAME, app_settings.SMTP_PASSWORD)
        smtp.send_message(message)


async def send(subject: str, body: str) -> bool:
    """Fire one mail. Returns whether it went. Never raises — a mail failure is
    never worth an error on a user's screen."""
    if not configured():
        return False
    try:
        # smtplib is blocking; keep it off the event loop.
        await asyncio.to_thread(_send_blocking, subject, body, list(app_settings.DEVELOPER_EMAILS))
        return True
    except Exception as exc:  # noqa: BLE001 — mail is best-effort, always
        logger.warning("developer mail failed: %s", exc)
        return False


async def _last_sent(db: AsyncSession) -> datetime | None:
    flag = await db.scalar(select(SystemFlag).where(SystemFlag.key == DIGEST_FLAG_KEY))
    raw = (flag.value or {}).get("at") if flag else None
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw))
    except ValueError:
        return None


async def _mark_sent(db: AsyncSession, when: datetime) -> None:
    flag = await db.scalar(select(SystemFlag).where(SystemFlag.key == DIGEST_FLAG_KEY))
    if flag is None:
        db.add(SystemFlag(key=DIGEST_FLAG_KEY, value={"at": when.isoformat()}))
    else:
        flag.value = {"at": when.isoformat()}
    await db.commit()


async def notify_backlog_if_due() -> None:
    """Background-task entry point: check the backlog and mail the developer if
    a digest is due.

    Runs AFTER the response, on its own session — SMTP is slow and blocking, and
    a user writing a diary note must never wait on the developer's inbox. Opens
    nothing at all when mail isn't configured, which is the default in dev and
    in every test.
    """
    if not configured():
        return
    try:
        # Imported here: this is the only place the service needs a session of
        # its own, and a module-level import would make mail_service a
        # dependency of everything that touches the database.
        from app.core.database import AsyncSessionLocal
        from app.services import enrichment_service

        async with AsyncSessionLocal() as db:
            await maybe_send_backlog_digest(db, await enrichment_service.pending_count(db))
    except Exception as exc:  # noqa: BLE001 — a background alert must never surface
        logger.warning("backlog digest check failed: %s", exc)


async def maybe_send_backlog_digest(db: AsyncSession, pending: int) -> bool:
    """Tell the developer there's work waiting — at most once a day, and only
    ever a number.

    `pending` is an int on purpose. There is no parameter here that could carry
    a user's words even by accident."""
    if pending <= 0 or not configured():
        return False

    now = datetime.now(timezone.utc)
    last = await _last_sent(db)
    if last is not None and now - last < timedelta(hours=DIGEST_MIN_INTERVAL_HOURS):
        return False

    # Mark BEFORE sending: a send that half-succeeds must not turn into a mail
    # every single request. Missing one digest is nothing; a mail loop is not.
    await _mark_sent(db, now)

    thing = "thing" if pending == 1 else "things"
    sent = await send(
        subject=f"Advary: {pending} {thing} waiting for the model",
        body=(
            f"{pending} {thing} are parked for the local model to look at.\n\n"
            "Turn the Ollama bridge on and drain the queue when you get a chance.\n"
            "No rush — the app is answering everyone normally from the rules in the "
            "meantime, and nothing is lost while it waits.\n\n"
            "(This mail is a count only. It never contains anything anyone wrote.)"
        ),
    )
    return sent
