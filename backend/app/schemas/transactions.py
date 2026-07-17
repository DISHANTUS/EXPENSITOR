"""Transaction-capture schemas (SMS -> candidate the user confirms)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SmsParseIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=2000)


class TxnCandidate(BaseModel):
    """A parsed-but-unconfirmed transaction. The app shows it as
    'you spent ₹50 — what for?'; nothing is recorded until the user taps a
    reason. `reasons` are the user's OWN learned reasons, ranked for this amount.
    """

    kind: str                       # expense | income
    direction: str                  # debit | credit
    amount: str
    merchant: str | None = None
    is_upi: bool = False
    suggested_reason: str | None = None
    reasons: list[str] = []         # learned chips (own history), most likely first
    raw: str


class ReceiptParseIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=8000)   # raw OCR text off the phone


class ReceiptItem(BaseModel):
    name: str
    price: str


class ReceiptCandidate(BaseModel):
    """A parsed-but-unconfirmed receipt. `total` is the expense to record;
    `items` are per-line prices, the raw material for learning YOUR product
    costs. All null/empty fields just mean OCR wasn't sure — the user edits."""

    merchant: str | None = None
    total: str | None = None
    date: str | None = None
    items: list[ReceiptItem] = []
    item_count: int = 0
    reasons: list[str] = []       # learned reasons ranked for the total


class ReceiptParseOut(BaseModel):
    candidate: ReceiptCandidate | None = None


class SmsParseOut(BaseModel):
    """`candidate` is null when the SMS wasn't a transaction we act on — most
    texts aren't, and saying so is better than inventing one."""

    candidate: TxnCandidate | None = None
