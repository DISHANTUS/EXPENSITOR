"""Currency reference + conversion endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.currency import ConvertRequest, ConvertResponse, CurrencyRead
from app.services import currency_service
from app.services.exceptions import CurrencyNotFoundError, RateNotAvailableError

router = APIRouter(tags=["currency"])


@router.get("/currencies", response_model=list[CurrencyRead], summary="List supported currencies")
async def list_currencies(current_user: CurrentUser, db: DbSession) -> list[CurrencyRead]:
    rows = await currency_service.list_currencies(db)
    return [CurrencyRead.model_validate(row) for row in rows]


@router.get("/currencies/{code}", response_model=CurrencyRead, summary="Get a currency")
async def get_currency(code: str, current_user: CurrentUser, db: DbSession) -> CurrencyRead:
    try:
        row = await currency_service.get_currency(db, code)
    except CurrencyNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return CurrencyRead.model_validate(row)


@router.post("/currency/convert", response_model=ConvertResponse, summary="Convert an amount")
async def convert(data: ConvertRequest, current_user: CurrentUser, db: DbSession) -> ConvertResponse:
    try:
        result = await currency_service.convert(db, data.amount, data.from_currency, data.to_currency)
    except CurrencyNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported currency: {exc.code}",
        ) from exc
    except RateNotAvailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return ConvertResponse.model_validate(result)
