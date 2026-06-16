"""Business logic for authentication: registration, login, and refresh-token
lifecycle (issue, rotate, revoke). All logic is here so routers stay thin."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from jose import JWTError
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    access_token_ttl_seconds,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.models import RefreshToken, User
from app.services.exceptions import (
    EmailAlreadyExistsError,
    InvalidCredentialsError,
    InvalidTokenError,
)
from app.services.settings_service import build_default_settings

# Pre-computed hash used to equalize timing when an email is unknown, so that
# response time does not reveal whether an account exists.
_DUMMY_PASSWORD_HASH = hash_password("expensitor-timing-equalizer")

TokenTriple = tuple[str, str, int]  # (access_token, refresh_token, expires_in)


def _normalize_email(email: str) -> str:
    return email.strip().lower()


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def register_user(
    db: AsyncSession, *, email: str, password: str, full_name: str | None = None
) -> User:
    normalized = _normalize_email(email)
    if await get_user_by_email(db, normalized) is not None:
        raise EmailAlreadyExistsError

    user = User(email=normalized, password_hash=hash_password(password), full_name=full_name)
    db.add(user)
    await db.flush()  # populate user.id

    db.add(build_default_settings(user.id))
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User:
    user = await get_user_by_email(db, _normalize_email(email))
    if user is None:
        verify_password(password, _DUMMY_PASSWORD_HASH)  # equalize timing
        raise InvalidCredentialsError
    if not verify_password(password, user.password_hash):
        raise InvalidCredentialsError
    if not user.is_active:
        raise InvalidCredentialsError
    return user


async def _persist_refresh_token(db: AsyncSession, user_id: uuid.UUID, raw_token: str, expires_at: datetime) -> None:
    db.add(
        RefreshToken(
            user_id=user_id,
            token_hash=hash_token(raw_token),
            expires_at=expires_at,
        )
    )


async def issue_token_pair(db: AsyncSession, user: User) -> TokenTriple:
    access = create_access_token(user.id)
    refresh, expires_at = create_refresh_token(user.id)
    await _persist_refresh_token(db, user.id, refresh, expires_at)
    await db.commit()
    return access, refresh, access_token_ttl_seconds()


async def _revoke_all_user_tokens(db: AsyncSession, user_id: uuid.UUID, now: datetime) -> None:
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now)
    )


async def rotate_refresh_token(db: AsyncSession, raw_token: str) -> TokenTriple:
    """Validate + rotate a refresh token. Implements reuse detection: replaying a
    revoked token revokes all of that user's sessions."""
    try:
        payload = decode_token(raw_token)
    except JWTError as exc:
        raise InvalidTokenError from exc
    if payload.get("type") != "refresh":
        raise InvalidTokenError

    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw_token))
    )
    token_row = result.scalar_one_or_none()
    if token_row is None:
        raise InvalidTokenError

    now = datetime.now(timezone.utc)

    if token_row.revoked_at is not None:
        # Replay of an already-rotated/revoked token -> revoke everything.
        await _revoke_all_user_tokens(db, token_row.user_id, now)
        await db.commit()
        raise InvalidTokenError

    if token_row.expires_at <= now:
        raise InvalidTokenError

    user = await db.get(User, token_row.user_id)
    if user is None or not user.is_active:
        raise InvalidTokenError

    # Rotate: revoke the presented token, issue a fresh pair.
    token_row.revoked_at = now
    access = create_access_token(user.id)
    new_refresh, expires_at = create_refresh_token(user.id)
    await _persist_refresh_token(db, user.id, new_refresh, expires_at)
    await db.commit()
    return access, new_refresh, access_token_ttl_seconds()


async def revoke_refresh_token(db: AsyncSession, raw_token: str) -> None:
    """Revoke a single refresh token (logout). Idempotent: unknown/already-revoked
    tokens are a no-op."""
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw_token))
    )
    token_row = result.scalar_one_or_none()
    if token_row is not None and token_row.revoked_at is None:
        token_row.revoked_at = datetime.now(timezone.utc)
        await db.commit()
