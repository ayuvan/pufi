"""
PUFI — FX and cost calculation engine (Day 3).

DESIGN RULES:
  - All arithmetic uses Python Decimal. No float ever enters this module.
  - Every quote carries a source, timestamp, expiry, and is_simulated flag.
  - Spread is in basis points (100 bps = 1 pct).
  - Recipient amount is calculated AFTER fee deduction, then converted.
  - Quote expiry is enforced before any calculation.
  - Hard-coded demo rates are ALWAYS labelled SIMULATED.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import Optional


# ---------------------------------------------------------------------------
# Currency rounding table (ISO 4217 minor units)
# Source: ISO 4217 official list (subset relevant to this prototype)
# ---------------------------------------------------------------------------

CURRENCY_DECIMALS: dict[str, int] = {
    "USD": 2, "EUR": 2, "GBP": 2, "AUD": 2, "CAD": 2, "CHF": 2,
    "NZD": 2, "SGD": 2, "HKD": 2, "SEK": 2, "NOK": 2, "DKK": 2,
    "MXN": 2, "BRL": 2, "ZAR": 2, "PLN": 2, "CZK": 2, "HUF": 2,
    "RON": 2, "TRY": 2, "ILS": 2, "SAR": 2, "AED": 2, "MYR": 2,
    "THB": 2, "PHP": 2, "COP": 2, "CLP": 0,  # CLP has 0 minor units
    "JPY": 0, "KRW": 0, "IDR": 0, "TWD": 0,
    "CNY": 2, "INR": 2, "RUB": 2,
}


def currency_quantize(amount: Decimal, currency: str) -> Decimal:
    """Round amount to the correct decimal places for the given currency."""
    places = CURRENCY_DECIMALS.get(currency.upper(), 2)
    quant = Decimal(10) ** -places
    return amount.quantize(quant, rounding=ROUND_HALF_UP)


# ---------------------------------------------------------------------------
# Quote model
# ---------------------------------------------------------------------------

@dataclass
class FxQuoteData:
    """
    An in-memory FX quote.

    is_simulated=True means this is a synthetic/demo rate — always labelled SIMULATED.
    is_simulated=False means the rate was obtained from an external live/sandbox source.
    """
    base_currency: str
    quote_currency: str
    rate: Decimal              # quote_currency units per 1 base_currency unit
    spread_bps: Decimal        # spread in basis points (e.g. 50 → 0.50%)
    fee_amount: Decimal        # fixed fee in base_currency per transaction
    source: str
    quoted_at: datetime
    expires_at: datetime
    is_simulated: bool

    @property
    def label(self) -> str:
        return "SIMULATED" if self.is_simulated else "LIVE"

    def is_expired(self, as_of: Optional[datetime] = None) -> bool:
        """Return True if the quote has passed its expiry time."""
        now = as_of or datetime.now(timezone.utc)
        # Normalise naive datetimes to UTC for comparison
        exp = self.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        return now >= exp

    def effective_rate(self) -> Decimal:
        """
        Apply spread to the mid-rate.
        effective_rate = rate * (1 - spread_bps / 10000)
        A higher spread means the recipient gets fewer quote-currency units.
        """
        spread_factor = Decimal(1) - (self.spread_bps / Decimal(10000))
        return (self.rate * spread_factor).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)


# ---------------------------------------------------------------------------
# Cost result
# ---------------------------------------------------------------------------

@dataclass
class RouteCostResult:
    """
    Transparent cost breakdown for one provider route on one obligation.

    All monetary values are Decimal. None of these values represent
    actual money movement — they are estimates for planning purposes.
    """
    provider_code: str
    source_amount: Decimal
    source_currency: str
    provider_fee: Decimal          # fee charged by provider
    fx_spread_cost: Decimal        # cost of spread in source currency
    total_estimated_cost: Decimal  # provider_fee + fx_spread_cost
    converted_amount: Optional[Decimal]    # amount in quote_currency (None if same-currency)
    recipient_currency: str
    estimated_recipient_amount: Decimal    # what recipient receives (after fees + FX)
    quote_rate: Optional[Decimal]          # mid-rate used (None if same-currency)
    effective_rate: Optional[Decimal]      # rate after spread
    quote_label: str                       # "SIMULATED" | "LIVE" | "N/A"
    quote_source: str
    quoted_at: Optional[datetime]
    expires_at: Optional[datetime]
    is_simulated: bool
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Simulated FX quote store
# ---------------------------------------------------------------------------
# These are CLEARLY LABELLED synthetic rates for demo/prototype use.
# They must NEVER be presented to a user as live market rates.
# In production, these would be fetched from an authorised FX data provider.

_SIMULATED_QUOTE_TTL_HOURS = 1

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


SIMULATED_RATES: dict[tuple[str, str], Decimal] = {
    # Rates as of prototype creation — clearly synthetic
    ("USD", "EUR"): Decimal("0.92"),
    ("USD", "GBP"): Decimal("0.79"),
    ("USD", "INR"): Decimal("83.50"),
    ("USD", "JPY"): Decimal("149.00"),
    ("USD", "AUD"): Decimal("1.53"),
    ("USD", "CAD"): Decimal("1.36"),
    ("USD", "CHF"): Decimal("0.90"),
    ("USD", "SGD"): Decimal("1.34"),
    ("USD", "CNY"): Decimal("7.24"),
    ("USD", "MXN"): Decimal("17.10"),
    ("USD", "BRL"): Decimal("4.97"),
    ("USD", "ZAR"): Decimal("18.60"),
    ("EUR", "USD"): Decimal("1.09"),
    ("EUR", "GBP"): Decimal("0.86"),
    ("GBP", "USD"): Decimal("1.27"),
}

# Default spread for simulated routes: 50 bps (0.50%)
_DEFAULT_SIMULATED_SPREAD_BPS = Decimal("50")


def get_simulated_quote(
    base: str,
    quote: str,
    spread_bps: Optional[Decimal] = None,
    fee_amount: Optional[Decimal] = None,
) -> Optional[FxQuoteData]:
    """
    Return a clearly-labelled SIMULATED FX quote if the pair is configured.

    Returns None if the pair is not in the simulated rate table.
    Callers must check is_simulated=True before displaying.
    """
    base = base.upper()
    quote = quote.upper()
    if base == quote:
        return None  # same currency — no FX needed

    rate = SIMULATED_RATES.get((base, quote))
    if rate is None:
        return None

    now = _utcnow()
    return FxQuoteData(
        base_currency=base,
        quote_currency=quote,
        rate=rate,
        spread_bps=spread_bps if spread_bps is not None else _DEFAULT_SIMULATED_SPREAD_BPS,
        fee_amount=fee_amount if fee_amount is not None else Decimal("0"),
        source="PUFI_SIMULATED_DEMO",
        quoted_at=now,
        expires_at=now + timedelta(hours=_SIMULATED_QUOTE_TTL_HOURS),
        is_simulated=True,
    )


# ---------------------------------------------------------------------------
# Cost calculation
# ---------------------------------------------------------------------------

def calculate_route_cost(
    *,
    source_amount: Decimal,
    source_currency: str,
    recipient_currency: str,
    provider_code: str,
    provider_fee_flat: Decimal,
    provider_fee_bps: Decimal,
    quote: Optional[FxQuoteData],
    as_of: Optional[datetime] = None,
) -> RouteCostResult:
    """
    Calculate the transparent estimated cost for routing source_amount
    through a given provider.

    Parameters
    ----------
    source_amount       : Amount the business sends (Decimal, >0)
    source_currency     : ISO 4217 code of the source amount
    recipient_currency  : ISO 4217 code the recipient receives
    provider_code       : Provider identifier
    provider_fee_flat   : Fixed fee per transaction in source_currency
    provider_fee_bps    : Variable fee in basis points of source_amount
    quote               : FxQuoteData or None (required if currencies differ)
    as_of               : Optional datetime for expiry check (defaults to UTC now)

    Returns
    -------
    RouteCostResult with full cost breakdown. Adds warnings for expired quotes.
    """
    warnings: list[str] = []

    # --- Provider fee ---
    variable_fee = (source_amount * provider_fee_bps / Decimal(10000)).quantize(
        Decimal("0.000001"), rounding=ROUND_HALF_UP
    )
    provider_fee = currency_quantize(provider_fee_flat + variable_fee, source_currency)

    amount_after_fee = source_amount - provider_fee

    # --- FX conversion ---
    src = source_currency.upper()
    rcv = recipient_currency.upper()

    if src == rcv:
        # Same currency — no FX needed
        estimated_recipient = currency_quantize(amount_after_fee, rcv)
        return RouteCostResult(
            provider_code=provider_code,
            source_amount=source_amount,
            source_currency=src,
            provider_fee=provider_fee,
            fx_spread_cost=Decimal("0"),
            total_estimated_cost=provider_fee,
            converted_amount=None,
            recipient_currency=rcv,
            estimated_recipient_amount=estimated_recipient,
            quote_rate=None,
            effective_rate=None,
            quote_label="N/A",
            quote_source="N/A",
            quoted_at=None,
            expires_at=None,
            is_simulated=False,
            warnings=warnings,
        )

    # FX required
    if quote is None:
        warnings.append(
            f"No FX quote available for {src}/{rcv}. "
            f"Cannot estimate recipient amount."
        )
        return RouteCostResult(
            provider_code=provider_code,
            source_amount=source_amount,
            source_currency=src,
            provider_fee=provider_fee,
            fx_spread_cost=Decimal("0"),
            total_estimated_cost=provider_fee,
            converted_amount=None,
            recipient_currency=rcv,
            estimated_recipient_amount=Decimal("0"),
            quote_rate=None,
            effective_rate=None,
            quote_label="UNAVAILABLE",
            quote_source="NONE",
            quoted_at=None,
            expires_at=None,
            is_simulated=True,
            warnings=warnings,
        )

    if quote.is_expired(as_of):
        warnings.append(
            f"FX quote for {src}/{rcv} from {quote.source!r} "
            f"expired at {quote.expires_at.isoformat()}. "
            f"Estimate may be stale."
        )

    eff_rate = quote.effective_rate()

    # Spread cost in source currency:
    # spread_cost = amount_after_fee * (spread_bps / 10000)
    fx_spread_cost = currency_quantize(
        amount_after_fee * quote.spread_bps / Decimal(10000),
        src,
    )

    # Recipient receives amount_after_fee converted at effective rate
    converted = (amount_after_fee * eff_rate).quantize(
        Decimal("0.00000001"), rounding=ROUND_HALF_UP
    )
    estimated_recipient = currency_quantize(converted, rcv)

    total_cost = currency_quantize(provider_fee + fx_spread_cost, src)

    return RouteCostResult(
        provider_code=provider_code,
        source_amount=source_amount,
        source_currency=src,
        provider_fee=provider_fee,
        fx_spread_cost=fx_spread_cost,
        total_estimated_cost=total_cost,
        converted_amount=converted,
        recipient_currency=rcv,
        estimated_recipient_amount=estimated_recipient,
        quote_rate=quote.rate,
        effective_rate=eff_rate,
        quote_label=quote.label,
        quote_source=quote.source,
        quoted_at=quote.quoted_at,
        expires_at=quote.expires_at,
        is_simulated=quote.is_simulated,
        warnings=warnings,
    )
