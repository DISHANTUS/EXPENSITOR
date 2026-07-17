"""Transaction capture — parse a bank SMS into a candidate the user confirms.

Never creates an expense here: SMS parsing has false positives, so this returns
a candidate and the app records it only once the user taps a reason. See
sms_parser for why rejection is aggressive.
"""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.intelligence.companion import receipt_parser, sms_parser
from app.schemas.transactions import (
    ReceiptCandidate,
    ReceiptParseIn,
    ReceiptParseOut,
    SmsParseIn,
    SmsParseOut,
    TxnCandidate,
)
from app.services import reason_suggestion_service

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.post("/parse-sms", response_model=SmsParseOut, summary="Read a bank SMS into a candidate")
async def parse_sms(data: SmsParseIn, db: DbSession, current_user: CurrentUser) -> SmsParseOut:
    parsed = sms_parser.parse(data.text)
    if parsed is None:
        return SmsParseOut(candidate=None)

    reasons: list[str] = []
    if parsed["kind"] == "expense":
        # The user's own learned reasons, ranked for this amount — so the
        # "what for?" prompt is one tap. Never another user's, never invented.
        rows = await reason_suggestion_service.suggest(
            db, current_user.id, amount=Decimal(parsed["amount"]), limit=5
        )
        reasons = [r["reason"] for r in rows]

    return SmsParseOut(candidate=TxnCandidate(**parsed, reasons=reasons))


@router.post("/parse-receipt", response_model=ReceiptParseOut, summary="Read a receipt's OCR text into a candidate")
async def parse_receipt(data: ReceiptParseIn, db: DbSession, current_user: CurrentUser) -> ReceiptParseOut:
    parsed = receipt_parser.parse(data.text)
    if parsed is None:
        return ReceiptParseOut(candidate=None)

    reasons: list[str] = []
    if parsed.get("total"):
        rows = await reason_suggestion_service.suggest(
            db, current_user.id, amount=Decimal(parsed["total"]), limit=5
        )
        reasons = [r["reason"] for r in rows]

    return ReceiptParseOut(candidate=ReceiptCandidate(**parsed, reasons=reasons))
