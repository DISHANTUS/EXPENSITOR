"""Currency reference data and stored-rate conversion (no external calls)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Currency, ExchangeRate
from app.services.exceptions import CurrencyNotFoundError, RateNotAvailableError


@dataclass
class ConversionResult:
    original_amount: Decimal
    converted_amount: Decimal
    exchange_rate: Decimal
    from_currency: str
    to_currency: str
    rate_date: date | None


def round_money(value: Decimal, digits: int) -> Decimal:
    """Quantize a value to a currency's minor-unit precision (HALF_UP)."""
    quant = Decimal(1).scaleb(-digits)  # 10**-digits, e.g. digits=2 -> 0.01
    return value.quantize(quant, rounding=ROUND_HALF_UP)


async def list_currencies(db: AsyncSession) -> list[Currency]:
    result = await db.execute(select(Currency).order_by(Currency.code))
    return list(result.scalars().all())


async def get_currency(db: AsyncSession, code: str) -> Currency:
    currency = await db.get(Currency, code.upper())
    if currency is None:
        raise CurrencyNotFoundError(code.upper())
    return currency


async def _latest_rate_map(db: AsyncSession) -> tuple[dict[tuple[str, str], Decimal], date | None]:
    """All stored rates for the most recent rate_date, keyed by (base, quote)."""
    latest_date = await db.scalar(select(func.max(ExchangeRate.rate_date)))
    if latest_date is None:
        return {}, None
    result = await db.execute(select(ExchangeRate).where(ExchangeRate.rate_date == latest_date))
    rates = {(r.base_currency, r.quote_currency): r.rate for r in result.scalars().all()}
    return rates, latest_date


def _direct_or_inverse(rates: dict[tuple[str, str], Decimal], a: str, b: str) -> Decimal | None:
    if a == b:
        return Decimal(1)
    if (a, b) in rates:
        return rates[(a, b)]
    if (b, a) in rates:
        return Decimal(1) / rates[(b, a)]
    return None


def _resolve_rate(rates: dict[tuple[str, str], Decimal], frm: str, to: str) -> Decimal | None:
    """Resolve frm->to via direct, inverse, or a cross-rate through any pivot."""
    direct = _direct_or_inverse(rates, frm, to)
    if direct is not None:
        return direct
    pivots = {code for pair in rates for code in pair}
    for pivot in pivots:
        leg1 = _direct_or_inverse(rates, frm, pivot)
        leg2 = _direct_or_inverse(rates, pivot, to)
        if leg1 is not None and leg2 is not None:
            return leg1 * leg2
    return None


async def get_exchange_rate(db: AsyncSession, from_currency: str, to_currency: str) -> Decimal:
    frm, to = from_currency.upper(), to_currency.upper()
    rates, _ = await _latest_rate_map(db)
    rate = _resolve_rate(rates, frm, to)
    if rate is None:
        raise RateNotAvailableError(frm, to)
    return rate


async def convert_to_base(
    db: AsyncSession, amount: Decimal, original_currency: str, base_currency: str
) -> tuple[Decimal, Decimal]:
    """Return (exchange_rate, converted_amount) for an FX snapshot in base currency."""
    rate = await get_exchange_rate(db, original_currency, base_currency)
    base = await get_currency(db, base_currency)
    converted = round_money(amount * rate, base.decimal_digits)
    return rate, converted


async def convert(
    db: AsyncSession, amount: Decimal, from_currency: str, to_currency: str
) -> ConversionResult:
    frm, to = from_currency.upper(), to_currency.upper()
    await get_currency(db, frm)  # validates existence -> CurrencyNotFoundError
    to_currency_obj = await get_currency(db, to)
    rates, latest_date = await _latest_rate_map(db)
    rate = _resolve_rate(rates, frm, to)
    if rate is None:
        raise RateNotAvailableError(frm, to)
    converted = round_money(amount * rate, to_currency_obj.decimal_digits)
    return ConversionResult(
        original_amount=amount,
        converted_amount=converted,
        exchange_rate=rate,
        from_currency=frm,
        to_currency=to,
        rate_date=latest_date,
    )
