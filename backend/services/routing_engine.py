"""
PUFI — Deterministic provider eligibility and routing engine (Day 3).

DESIGN PRINCIPLES:
  - Eligibility checks are hard constraints.  No amount of AI advice can
    override a failed eligibility check.
  - Every exclusion reason is an explicit code (not a vague message) so that
    the AI advisor and UI can reference it unambiguously.
  - Routing never modifies amounts.  It computes estimated costs only.
  - Funding snapshots are explicitly labelled SIMULATED for Day 3.
  - FX quotes are retrieved from fx_engine.get_simulated_quote() — always
    labelled SIMULATED.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from services.fx_engine import (
    RouteCostResult,
    calculate_route_cost,
    get_simulated_quote,
)
from services.provider_registry import ProviderCapability, enabled_providers, get_provider

logger = logging.getLogger("pufi.routing")


# ---------------------------------------------------------------------------
# Exclusion reason codes
# ---------------------------------------------------------------------------

REASON_PROVIDER_DISABLED = "PROVIDER_DISABLED"
REASON_CURRENCY_UNSUPPORTED = "CURRENCY_UNSUPPORTED"
REASON_RECIPIENT_TYPE_UNSUPPORTED = "RECIPIENT_TYPE_UNSUPPORTED"
REASON_AMOUNT_BELOW_MIN = "AMOUNT_BELOW_MIN"
REASON_AMOUNT_ABOVE_MAX = "AMOUNT_ABOVE_MAX"
REASON_INSUFFICIENT_FUNDING = "INSUFFICIENT_FUNDING"
REASON_NO_FX_QUOTE = "NO_FX_QUOTE"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class EligibilityResult:
    """
    Result of eligibility check for one provider against one obligation.

    eligible=True  → provider can be used; cost breakdown is populated.
    eligible=False → provider is excluded; exclusion_reasons lists why.
    """
    provider_code: str
    display_name: str
    environment: str
    is_simulated: bool
    eligible: bool
    exclusion_reasons: list[str] = field(default_factory=list)
    cost: Optional[RouteCostResult] = None


@dataclass
class ObligationContext:
    """
    Minimal view of an obligation needed by the routing engine.
    Caller builds this from the ORM object.
    """
    obligation_id: str
    source_amount: Decimal
    source_currency: str
    recipient_currency: str           # may be same as source_currency
    recipient_type: str               # "EMAIL" | "PHONE" | "PAYPAL_ID" etc.


@dataclass
class RoutingResult:
    """
    Result of routing one obligation across all providers.
    """
    obligation_id: str
    source_amount: Decimal
    source_currency: str
    recipient_currency: str
    eligible_routes: list[EligibilityResult]
    excluded_routes: list[EligibilityResult]
    recommended_provider_code: Optional[str]
    ranking_strategy: str
    # Funding map used (for audit transparency)
    funding_snapshot_label: str = "SIMULATED"


# ---------------------------------------------------------------------------
# Demo funding snapshots
# Labelled SIMULATED — for Day 3 prototype only.
# ---------------------------------------------------------------------------

# Outer key: provider_code, inner key: currency, value: available amount.
# In production this would come from real treasury/funding data.
DEMO_FUNDING_MAP: dict[str, dict[str, Decimal]] = {
    "PAYPAL_SANDBOX": {
        "USD": Decimal("100000.00"),
    },
    "SIMULATED_FAST": {
        "USD": Decimal("500000.00"),
        "EUR": Decimal("400000.00"),
        "GBP": Decimal("300000.00"),
        "AUD": Decimal("200000.00"),
        "CAD": Decimal("200000.00"),
        "SGD": Decimal("150000.00"),
    },
    "SIMULATED_ECONOMY": {
        "USD": Decimal("1000000.00"),
        "EUR": Decimal("800000.00"),
        "GBP": Decimal("600000.00"),
        "INR": Decimal("50000000.00"),
        "MXN": Decimal("5000000.00"),
        "BRL": Decimal("2000000.00"),
        "ZAR": Decimal("4000000.00"),
        "AUD": Decimal("400000.00"),
        "CAD": Decimal("400000.00"),
    },
}


# ---------------------------------------------------------------------------
# Eligibility check
# ---------------------------------------------------------------------------

def check_eligibility(
    obligation: ObligationContext,
    provider: ProviderCapability,
    funding_map: dict[str, dict[str, Decimal]] = DEMO_FUNDING_MAP,
) -> EligibilityResult:
    """
    Run all hard eligibility checks for one (obligation, provider) pair.

    Returns an EligibilityResult with eligible=True and a cost breakdown
    if the provider can process this obligation, otherwise eligible=False
    with explicit reason codes.

    AI cannot override this function.
    """
    reasons: list[str] = []

    # --- Check 1: provider must be enabled ---
    if not provider.enabled:
        reasons.append(REASON_PROVIDER_DISABLED)

    # --- Check 2: source currency must be supported ---
    src_currency = obligation.source_currency.upper()
    if src_currency not in provider.supported_currencies:
        reasons.append(REASON_CURRENCY_UNSUPPORTED)

    # --- Check 3: recipient type must be supported ---
    recipient_type = (obligation.recipient_type or "").upper()
    if recipient_type not in provider.supported_recipient_types:
        reasons.append(REASON_RECIPIENT_TYPE_UNSUPPORTED)

    # --- Check 4: amount bounds ---
    if obligation.source_amount < provider.min_amount:
        reasons.append(REASON_AMOUNT_BELOW_MIN)
    if obligation.source_amount > provider.max_amount:
        reasons.append(REASON_AMOUNT_ABOVE_MAX)

    # --- Check 5: funding availability ---
    provider_funding = funding_map.get(provider.provider_code, {})
    available = provider_funding.get(src_currency)
    if available is not None and available < obligation.source_amount:
        reasons.append(REASON_INSUFFICIENT_FUNDING)

    # --- Check 6: FX quote (only needed for cross-currency) ---
    rcv_currency = obligation.recipient_currency.upper()
    quote = None
    if src_currency != rcv_currency:
        quote = get_simulated_quote(src_currency, rcv_currency)
        if quote is None:
            reasons.append(REASON_NO_FX_QUOTE)

    if reasons:
        return EligibilityResult(
            provider_code=provider.provider_code,
            display_name=provider.display_name,
            environment=provider.environment,
            is_simulated=provider.is_simulated,
            eligible=False,
            exclusion_reasons=reasons,
            cost=None,
        )

    # All checks passed — calculate cost
    cost = calculate_route_cost(
        source_amount=obligation.source_amount,
        source_currency=src_currency,
        recipient_currency=rcv_currency,
        provider_code=provider.provider_code,
        provider_fee_flat=provider.fee_flat,
        provider_fee_bps=provider.fee_bps,
        quote=quote,
    )

    return EligibilityResult(
        provider_code=provider.provider_code,
        display_name=provider.display_name,
        environment=provider.environment,
        is_simulated=provider.is_simulated,
        eligible=True,
        exclusion_reasons=[],
        cost=cost,
    )


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------

def rank_routes(
    eligible: list[EligibilityResult],
    strategy: str = "LOWEST_COST",
) -> list[EligibilityResult]:
    """
    Sort eligible routes according to the given ranking strategy.

    Strategies:
      LOWEST_COST  — lowest total_estimated_cost first
      FASTEST      — lowest estimated_processing_hours first (then cost)
      BALANCED     — combined cost + speed score (cost*0.6 + speed*0.4)
    """
    if not eligible:
        return []

    strategy = strategy.upper()

    def _cost(r: EligibilityResult) -> Decimal:
        return r.cost.total_estimated_cost if r.cost else Decimal("999999")

    def _hours(r: EligibilityResult) -> int:
        p = get_provider(r.provider_code)
        return p.estimated_processing_hours if p else 999

    if strategy == "LOWEST_COST":
        return sorted(eligible, key=lambda r: (_cost(r), _hours(r)))

    if strategy == "FASTEST":
        return sorted(eligible, key=lambda r: (_hours(r), _cost(r)))

    if strategy == "BALANCED":
        # Normalise cost and hours to [0, 1] then weight 60% cost, 40% speed.
        # Guard against division by zero when all values are equal.
        costs = [float(_cost(r)) for r in eligible]
        hours = [float(_hours(r)) for r in eligible]

        cost_range = max(costs) - min(costs) if len(set(costs)) > 1 else 1.0
        hour_range = max(hours) - min(hours) if len(set(hours)) > 1 else 1.0

        def _balanced_score(r: EligibilityResult) -> float:
            norm_cost = (float(_cost(r)) - min(costs)) / cost_range
            norm_hours = (float(_hours(r)) - min(hours)) / hour_range
            return 0.6 * norm_cost + 0.4 * norm_hours

        return sorted(eligible, key=_balanced_score)

    # Unknown strategy — fall back to LOWEST_COST and log
    logger.warning("Unknown ranking strategy %r — falling back to LOWEST_COST", strategy)
    return sorted(eligible, key=lambda r: (_cost(r), _hours(r)))


# ---------------------------------------------------------------------------
# Main routing function
# ---------------------------------------------------------------------------

def route_obligation(
    obligation: ObligationContext,
    strategy: str = "LOWEST_COST",
    funding_map: dict[str, dict[str, Decimal]] = DEMO_FUNDING_MAP,
) -> RoutingResult:
    """
    Route one obligation across all enabled providers.

    Returns a RoutingResult containing:
      - eligible_routes  : ranked list of eligible providers with cost estimates
      - excluded_routes  : providers with reason codes
      - recommended_provider_code : top of the ranked list (or None)
    """
    all_results: list[EligibilityResult] = []

    for provider in enabled_providers():
        result = check_eligibility(obligation, provider, funding_map)
        all_results.append(result)
        if result.eligible:
            logger.debug(
                "Obligation %s — provider %s ELIGIBLE cost=%s",
                obligation.obligation_id,
                provider.provider_code,
                result.cost.total_estimated_cost if result.cost else "N/A",
            )
        else:
            logger.debug(
                "Obligation %s — provider %s EXCLUDED reasons=%s",
                obligation.obligation_id,
                provider.provider_code,
                result.exclusion_reasons,
            )

    eligible = [r for r in all_results if r.eligible]
    excluded = [r for r in all_results if not r.eligible]

    ranked = rank_routes(eligible, strategy)

    recommended = ranked[0].provider_code if ranked else None

    return RoutingResult(
        obligation_id=obligation.obligation_id,
        source_amount=obligation.source_amount,
        source_currency=obligation.source_currency,
        recipient_currency=obligation.recipient_currency,
        eligible_routes=ranked,
        excluded_routes=excluded,
        recommended_provider_code=recommended,
        ranking_strategy=strategy.upper(),
        funding_snapshot_label="SIMULATED",
    )
