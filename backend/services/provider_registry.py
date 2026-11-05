"""
PUFI — Provider capability registry (Day 3).

This module defines the static configuration of payment providers available
to the routing engine. No live API calls are made here — this is a
configuration store.

IMPORTANT DISCLOSURES:
  - PAYPAL_SANDBOX: capabilities declared based on official PayPal Payouts API
    documentation.  USD only.  INR payout NOT assumed (not verified as
    supported by PayPal India sandbox).  Payouts API access is account-gated.
  - SIMULATED_FAST and SIMULATED_ECONOMY are entirely synthetic providers.
    They are not real payment rails.  All estimates are for demonstration only.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional


@dataclass(frozen=True)
class FeeModel:
    """
    Provider fee structure.

    fee_flat_usd  : Fixed per-transaction fee expressed in source currency.
    fee_bps       : Variable fee in basis points (1 bps = 0.01%).
                    E.g. fee_bps=200 means 2% of source_amount.
    """
    fee_flat: Decimal   # in source currency units
    fee_bps: Decimal    # basis points


@dataclass(frozen=True)
class ProviderCapability:
    """
    Static descriptor for one payment provider.

    All fields are intentionally immutable (frozen=True) so the registry
    cannot be mutated at runtime.
    """
    provider_code: str
    display_name: str
    environment: str                       # "SANDBOX" | "SIMULATED"
    supported_currencies: frozenset[str]   # ISO 4217 source-currency codes
    supported_recipient_types: frozenset[str]  # "EMAIL" | "PHONE" | "PAYPAL_ID"
    min_amount: Decimal                    # minimum source amount
    max_amount: Decimal                    # maximum source amount
    fee_model: FeeModel
    estimated_processing_hours: int        # indicative; labelled as estimate
    enabled: bool
    last_verified_at: str                  # ISO date — when capability was last confirmed
    notes: str                             # disclosure of assumptions

    @property
    def is_simulated(self) -> bool:
        return self.environment == "SIMULATED"

    @property
    def fee_flat(self) -> Decimal:
        return self.fee_model.fee_flat

    @property
    def fee_bps(self) -> Decimal:
        return self.fee_model.fee_bps


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

PROVIDER_REGISTRY: dict[str, ProviderCapability] = {
    "PAYPAL_SANDBOX": ProviderCapability(
        provider_code="PAYPAL_SANDBOX",
        display_name="PayPal Payouts (Sandbox)",
        environment="SANDBOX",
        # Only USD is documented and verified for PayPal Payouts.
        # INR payout through PayPal India is NOT assumed or supported here.
        # Ref: https://developer.paypal.com/docs/payouts/
        supported_currencies=frozenset({"USD"}),
        # Recipient must have a PayPal account.
        # Phone-based payouts require additional KYC outside sandbox scope.
        supported_recipient_types=frozenset({"EMAIL", "PAYPAL_ID"}),
        min_amount=Decimal("1.00"),
        max_amount=Decimal("10000.00"),
        fee_model=FeeModel(
            # PayPal Payouts fee: typically $0.25 per payout + ~2% (varies by country/volume).
            # Using documented illustrative values; actual fees are account-tier dependent.
            # Source: PayPal Payouts pricing documentation (sandbox tier).
            fee_flat=Decimal("0.25"),
            fee_bps=Decimal("200"),   # 2.00% — upper bound estimate
        ),
        estimated_processing_hours=24,
        enabled=True,
        last_verified_at="2026-11-05",
        notes=(
            "PayPal Sandbox environment only. "
            "Payouts API access requires explicit account approval. "
            "USD payouts only — USD→INR is NOT verified. "
            "Recipient must hold a PayPal account. "
            "Fees are estimates based on published documentation; "
            "actual fees depend on volume and agreement."
        ),
    ),

    "SIMULATED_FAST": ProviderCapability(
        provider_code="SIMULATED_FAST",
        display_name="FastPay Simulated [SIMULATED]",
        environment="SIMULATED",
        supported_currencies=frozenset({"USD", "EUR", "GBP", "AUD", "CAD", "SGD"}),
        supported_recipient_types=frozenset({"EMAIL", "PHONE"}),
        min_amount=Decimal("10.00"),
        max_amount=Decimal("50000.00"),
        fee_model=FeeModel(
            fee_flat=Decimal("0.50"),
            fee_bps=Decimal("150"),   # 1.50%
        ),
        estimated_processing_hours=4,
        enabled=True,
        last_verified_at="2026-11-05",
        notes=(
            "[SIMULATED] Fully synthetic provider — not a real payment rail. "
            "All results are illustrative only. "
            "Processing-time and fee assumptions are fixed demo values. "
            "Do not use for real financial decisions."
        ),
    ),

    "SIMULATED_ECONOMY": ProviderCapability(
        provider_code="SIMULATED_ECONOMY",
        display_name="EconomyTransfer Simulated [SIMULATED]",
        environment="SIMULATED",
        supported_currencies=frozenset(
            {"USD", "EUR", "GBP", "INR", "MXN", "BRL", "ZAR", "AUD", "CAD"}
        ),
        supported_recipient_types=frozenset({"EMAIL", "PHONE"}),
        min_amount=Decimal("5.00"),
        max_amount=Decimal("25000.00"),
        fee_model=FeeModel(
            fee_flat=Decimal("0.00"),
            fee_bps=Decimal("100"),   # 1.00%
        ),
        estimated_processing_hours=48,
        enabled=True,
        last_verified_at="2026-11-05",
        notes=(
            "[SIMULATED] Fully synthetic provider — not a real payment rail. "
            "Lower fees, slower processing. "
            "All results are illustrative only. "
            "Do not use for real financial decisions."
        ),
    ),
}


def get_provider(code: str) -> Optional[ProviderCapability]:
    """Return the ProviderCapability for a given code, or None."""
    return PROVIDER_REGISTRY.get(code)


def all_providers() -> list[ProviderCapability]:
    """Return all registered providers in insertion order."""
    return list(PROVIDER_REGISTRY.values())


def enabled_providers() -> list[ProviderCapability]:
    """Return only providers with enabled=True."""
    return [p for p in PROVIDER_REGISTRY.values() if p.enabled]
