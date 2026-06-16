"""Security primitives: password hashing (bcrypt), JWT creation/decoding, and
opaque-token hashing for refresh-token storage. All pure and unit-testable."""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import bcrypt
from jose import jwt

from app.core.config import settings

TokenType = Literal["access", "refresh"]


# --- Passwords ---------------------------------------------------------------

def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt (per-hash random salt)."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Constant-time verification of a password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        # Malformed stored hash -> treat as a non-match rather than crashing.
        return False


# --- JWT ---------------------------------------------------------------------

def _create_token(subject: str | uuid.UUID, token_type: TokenType, expires_delta: timedelta) -> tuple[str, datetime]:
    now = datetime.now(timezone.utc)
    expire = now + expires_delta
    payload: dict[str, Any] = {
        "sub": str(subject),
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "jti": uuid.uuid4().hex,
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return token, expire


def create_access_token(subject: str | uuid.UUID) -> str:
    token, _ = _create_token(
        subject, "access", timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return token


def create_refresh_token(subject: str | uuid.UUID) -> tuple[str, datetime]:
    """Return (token, expires_at). The caller persists a hash of the token."""
    return _create_token(
        subject, "refresh", timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    )


def decode_token(token: str) -> dict[str, Any]:
    """Decode and verify a JWT. Raises jose.JWTError on any failure."""
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])


# --- Opaque token hashing (for refresh-token storage) ------------------------

def hash_token(token: str) -> str:
    """SHA-256 hex digest used to store refresh tokens (never store the token)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def access_token_ttl_seconds() -> int:
    return settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
