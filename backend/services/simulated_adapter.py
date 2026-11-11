"""
PUFI Simulated Provider Adapter

Implements Phase 3 of Master Remediation:
- Isolates simulated payment rails (SIMULATED_FAST, SIMULATED_ECONOMY) behind a standard provider adapter interface.
- Produces normalized execution responses with explicit [SIMULATED] labels.
- Emulates realistic provider responses without calling any external network service.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from services.paypal_adapter import PayoutItem

logger = logging.getLogger("pufi.simulated_adapter")


@dataclass
class SimulatedItemOutcome:
    sender_item_id: str
    payout_item_id: str
    transaction_id: str
    item_status: str  # "SUCCESS" | "PENDING" | "FAILED"
    amount: str
    currency: str
    error_message: Optional[str] = None


@dataclass
class SimulatedPayoutResult:
    success: bool
    provider_code: str
    sender_batch_id: str
    provider_batch_id: str
    batch_status: str  # "SUCCESS" | "PENDING" | "FAILED"
    http_status: int = 200
    is_simulated: bool = True
    error_message: Optional[str] = None
    items: list[SimulatedItemOutcome] = field(default_factory=list)


def submit_simulated_payout(
    provider_code: str,
    sender_batch_id: str,
    items: list[PayoutItem],
) -> SimulatedPayoutResult:
    """
    Executes a simulated payout batch for registered simulated providers.

    Rules:
    - Never makes an external HTTP or network call.
    - Always sets is_simulated=True.
    - SIMULATED_FAST emulates real-time settlement rails (e.g. instant FPS/ACH).
    - SIMULATED_ECONOMY emulates deferred/batch settlement rails (e.g. standard wire/ACH).
    """
    logger.info(
        "Executing SIMULATED payout: provider=%s sender_batch_id=%s items=%d",
        provider_code,
        sender_batch_id,
        len(items),
    )

    if provider_code not in ("SIMULATED_FAST", "SIMULATED_ECONOMY"):
        return SimulatedPayoutResult(
            success=False,
            provider_code=provider_code,
            sender_batch_id=sender_batch_id,
            provider_batch_id="",
            batch_status="FAILED",
            http_status=400,
            is_simulated=True,
            error_message=f"Unknown or unsupported simulated provider: {provider_code!r}",
        )

    sim_batch_id = f"SIM-{provider_code[:4]}-{uuid.uuid4().hex[:12].upper()}"

    item_outcomes: list[SimulatedItemOutcome] = []
    for item in items:
        # Determine status based on simulated rail speed
        if provider_code == "SIMULATED_FAST":
            status = "SUCCESS"
            txn_id = f"TXN-FAST-{uuid.uuid4().hex[:10].upper()}"
        else:
            status = "PENDING"  # Economy rail requires clearing window
            txn_id = f"TXN-ECON-{uuid.uuid4().hex[:10].upper()}"

        item_outcomes.append(
            SimulatedItemOutcome(
                sender_item_id=item.sender_item_id,
                payout_item_id=f"ITEM-{uuid.uuid4().hex[:8].upper()}",
                transaction_id=txn_id,
                item_status=status,
                amount=item.amount_value,
                currency=item.currency,
            )
        )

    batch_status = "SUCCESS" if provider_code == "SIMULATED_FAST" else "PENDING"

    return SimulatedPayoutResult(
        success=True,
        provider_code=provider_code,
        sender_batch_id=sender_batch_id,
        provider_batch_id=sim_batch_id,
        batch_status=batch_status,
        http_status=201,
        is_simulated=True,
        items=item_outcomes,
    )
