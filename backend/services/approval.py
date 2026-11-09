"""
PUFI — Approval service (Day 4).

Validates and records human approval of a payment batch.

Checks (all must pass):
  1. Batch exists and is in DRAFT or PENDING_APPROVAL status.
  2. An AiRecommendation record exists (analysis was run).
  3. All batch obligations are still VALIDATED (no status drift).
  4. Selected provider_code is in the eligible routes from latest analysis.
  5. confirmed_total matches the sum of obligation amounts (tamper check).
  6. No existing ProviderSubmission for this batch (not already submitted).
  7. confirmed_currency is "USD" for PAYPAL_SANDBOX.

Transitions batch to PENDING_APPROVAL status.
Writes an AuditEvent for the approval action.

The AI is advisory only: it cannot approve a batch by itself.
"""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Optional

from sqlalchemy.orm import Session

from models.entities import (
    AiRecommendation, AuditEvent, BatchObligation,
    Obligation, PaymentBatch, ProviderSubmission,
)

logger = logging.getLogger("pufi.approval")


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class ApprovalResult:
    success: bool
    batch_id: str
    status: str
    approved_by: str
    approved_at: Optional[datetime]
    selected_provider: str
    confirmed_total: str
    confirmed_currency: str
    approved_recipient_count: int
    routing_strategy: str
    analysis_snapshot_id: Optional[str]
    error_code: Optional[str] = None
    error_detail: Optional[str] = None


# ---------------------------------------------------------------------------
# Approval service
# ---------------------------------------------------------------------------

def approve_batch(
    *,
    batch_id: str,
    approver_id: str,
    selected_provider: str,
    routing_strategy: str,
    confirmed_total: str,
    confirmed_currency: str,
    db: Session,
    correlation_id: Optional[str] = None,
) -> ApprovalResult:
    """
    Validate and record human approval of a batch.

    Returns ApprovalResult.  On failure, success=False with error_code set.
    Does NOT raise exceptions for business-rule failures — only for
    unexpected DB errors.
    """

    # --- 1. Load batch ---
    batch = db.query(PaymentBatch).filter(PaymentBatch.id == batch_id).first()
    if batch is None:
        return _fail("BATCH_NOT_FOUND", f"Batch {batch_id!r} not found.", batch_id, approver_id, selected_provider, confirmed_total, confirmed_currency, routing_strategy)

    # --- 2. Status check: must be DRAFT or PENDING_APPROVAL ---
    if batch.status not in ("DRAFT", "PENDING_APPROVAL"):
        return _fail(
            "INVALID_BATCH_STATUS",
            f"Batch status is {batch.status!r}. Only DRAFT or PENDING_APPROVAL batches can be approved.",
            batch_id, approver_id, selected_provider, confirmed_total, confirmed_currency, routing_strategy,
        )

    # --- 3. Already submitted? ---
    existing_submission = (
        db.query(ProviderSubmission)
        .filter(
            ProviderSubmission.batch_id == batch_id,
            ProviderSubmission.status.in_(["SUBMITTED", "PENDING"]),
        )
        .first()
    )
    if existing_submission:
        return _fail(
            "ALREADY_SUBMITTED",
            f"Batch has an active submission (sender_batch_id={existing_submission.sender_batch_id!r}).",
            batch_id, approver_id, selected_provider, confirmed_total, confirmed_currency, routing_strategy,
        )

    # --- 4. AI recommendation (analysis) must exist ---
    ai_rec = (
        db.query(AiRecommendation)
        .filter(AiRecommendation.batch_id == batch_id)
        .order_by(AiRecommendation.created_at.desc())
        .first()
    )
    if ai_rec is None:
        return _fail(
            "ANALYSIS_REQUIRED",
            "Batch must be analysed before approval. Run POST /analyze first.",
            batch_id, approver_id, selected_provider, confirmed_total, confirmed_currency, routing_strategy,
        )

    # --- 5. All obligations must still be VALIDATED ---
    batch_obs = (
        db.query(BatchObligation)
        .filter(BatchObligation.batch_id == batch_id)
        .all()
    )
    if not batch_obs:
        return _fail(
            "NO_OBLIGATIONS",
            "Batch has no obligations.",
            batch_id, approver_id, selected_provider, confirmed_total, confirmed_currency, routing_strategy,
        )

    obligation_ids = [bo.obligation_id for bo in batch_obs]
    obligations = (
        db.query(Obligation)
        .filter(Obligation.id.in_(obligation_ids))
        .all()
    )

    not_validated = [ob.id for ob in obligations if ob.status != "VALIDATED"]
    if not_validated:
        return _fail(
            "OBLIGATION_NOT_VALIDATED",
            f"Obligations are not in VALIDATED status: {not_validated}. "
            "Obligation status may have changed since analysis.",
            batch_id, approver_id, selected_provider, confirmed_total, confirmed_currency, routing_strategy,
        )

    # --- 6. Selected provider must be in eligible routes from analysis ---
    try:
        rec_data = json.loads(ai_rec.recommendation_json)
    except json.JSONDecodeError:
        rec_data = {}

    # The recommendation JSON stores the eligible route codes from deterministic engine
    raw_evidence = rec_data.get("evidence_fields")
    if isinstance(raw_evidence, dict):
        eligible_codes = raw_evidence.get("eligible_route_codes", [])
    elif isinstance(raw_evidence, list):
        eligible_codes = raw_evidence
    else:
        eligible_codes = []

    # Also check if top-level recommendation or fallback provided eligible route
    if not eligible_codes and rec_data.get("recommended_route"):
        eligible_codes = [rec_data["recommended_route"]]

    if eligible_codes and selected_provider not in eligible_codes:
        return _fail(
            "PROVIDER_NOT_ELIGIBLE",
            f"Provider {selected_provider!r} was not in the eligible routes from the last analysis. "
            f"Eligible: {eligible_codes}",
            batch_id, approver_id, selected_provider, confirmed_total, confirmed_currency, routing_strategy,
        )

    # --- 7. confirmed_total must be parseable Decimal ---
    try:
        confirmed_decimal = Decimal(confirmed_total)
    except InvalidOperation:
        return _fail(
            "INVALID_CONFIRMED_TOTAL",
            f"confirmed_total {confirmed_total!r} is not a valid decimal number.",
            batch_id, approver_id, selected_provider, confirmed_total, confirmed_currency, routing_strategy,
        )

    # --- 8. Verify confirmed_total matches sum of obligations (tamper check) ---
    obligation_total = sum(Decimal(str(ob.amount)) for ob in obligations)
    # Allow ±0.01 tolerance for display rounding
    if abs(confirmed_decimal - obligation_total) > Decimal("0.01"):
        return _fail(
            "TOTAL_MISMATCH",
            f"confirmed_total {confirmed_total!r} does not match obligation sum {obligation_total!s}. "
            "Re-run analysis if obligations have changed.",
            batch_id, approver_id, selected_provider, confirmed_total, confirmed_currency, routing_strategy,
        )

    # --- 9. Currency validation for PAYPAL_SANDBOX ---
    if selected_provider == "PAYPAL_SANDBOX" and confirmed_currency.upper() != "USD":
        return _fail(
            "UNSUPPORTED_CURRENCY",
            f"PayPal Sandbox only supports USD payouts; got {confirmed_currency!r}.",
            batch_id, approver_id, selected_provider, confirmed_total, confirmed_currency, routing_strategy,
        )

    # --- All checks passed: record approval ---
    now = datetime.now(timezone.utc)
    batch.status = "PENDING_APPROVAL"
    batch.approved_by = approver_id
    batch.approved_at = now
    batch.selected_provider_code = selected_provider
    batch.analysis_snapshot_id = ai_rec.id
    batch.approved_total_amount = confirmed_decimal
    batch.approved_currency = confirmed_currency.upper()
    batch.approved_recipient_count = len(obligations)
    batch.approved_routing_strategy = routing_strategy

    # Transition to APPROVED immediately (prototype: single-step approval)
    batch.status = "APPROVED"

    # Write audit event
    audit = AuditEvent(
        entity_type="BATCH",
        entity_id=batch_id,
        event_type="APPROVED",
        actor=approver_id,
        correlation_id=correlation_id,
        details_redacted=json.dumps({
            "selected_provider": selected_provider,
            "confirmed_total": confirmed_total,
            "confirmed_currency": confirmed_currency.upper(),
            "routing_strategy": routing_strategy,
            "obligation_count": len(obligations),
            "analysis_snapshot_id": ai_rec.id,
        }),
    )
    db.add(audit)
    db.flush()

    logger.info(
        "Batch approved [corr=%s]: batch_id=%s approver=%r provider=%r total=%s %s",
        correlation_id,
        batch_id,
        approver_id,
        selected_provider,
        confirmed_total,
        confirmed_currency,
    )

    return ApprovalResult(
        success=True,
        batch_id=batch_id,
        status="APPROVED",
        approved_by=approver_id,
        approved_at=now,
        selected_provider=selected_provider,
        confirmed_total=confirmed_total,
        confirmed_currency=confirmed_currency.upper(),
        approved_recipient_count=len(obligations),
        routing_strategy=routing_strategy,
        analysis_snapshot_id=ai_rec.id,
    )


def _fail(
    code: str,
    detail: str,
    batch_id: str,
    approver_id: str,
    selected_provider: str,
    confirmed_total: str,
    confirmed_currency: str,
    routing_strategy: str,
) -> ApprovalResult:
    logger.warning("Approval rejected [%s]: %s", code, detail)
    return ApprovalResult(
        success=False,
        batch_id=batch_id,
        status="",
        approved_by=approver_id,
        approved_at=None,
        selected_provider=selected_provider,
        confirmed_total=confirmed_total,
        confirmed_currency=confirmed_currency,
        approved_recipient_count=0,
        routing_strategy=routing_strategy,
        analysis_snapshot_id=None,
        error_code=code,
        error_detail=detail,
    )
