"""Shared schema helpers (pagination envelope)."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """Offset-based pagination envelope."""

    items: list[T]
    total: int
    limit: int
    offset: int
