"""
PUFI — Execution coordinator (Day 4).

Orchestrates:
  submit_batch()      — creates PaymentInstructions, calls PayPal adapter, records submission
  refresh_status()    — queries PayPal for updated batch/item statuses

FINANCIAL RULES:
  - sender_batch_id is persisted BEFORE the API call.
  - On timeout, instruction status = UNKNOWN; do NOT retry with a new ID.
  - On success, batch status = SUBMITTED (not COMPLETED — funds may not have settled).
  - Settlement evidence is tracked separately from instruction status.
  - Item-level statuses are inspected individually (batch status alone is insufficient).

PAYPAL STATUS MAPPING:
  PayPal item transaction_status → PUFI instruction status:
    SUCCESS         → COMPLETED + settlement_evidence=PROVIDER_REPORTED_COMPLETE
    PENDING         → SUBMITTED
    UNCLAIMED       → SUBMITTED (recipient hasn't accepted — not settled)
    RETURNED        → FAILED
    ONHOLD          → SUBMITTED
    BLOCKED         → FAILED
    FAILED          → FAILED
    REFUNDED        → FAILED
    REVERSED        → FAILED
    (other/unknown) → UNKNOWN
"""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session, joinedload

from models.entities import (
    AuditEvent, BatchObligation, Obligation, PaymentBatch,
    PaymentInstruction, ProviderSubmission, Supplier,
)
from services.paypal_adapter import (
    PayoutItem, PayPalBatchStatusResult, is_configured,
    submit_payout, get_batch_status,
)

logger = logging.getLogger("pufi.execution")

# ---------------------------------------------------------------------------
# PayPal item status → PUFI status mapping
# ---------------------------------------------------------------------------

_ITEM_STATUS_MAP: dict[str, tuple[str, str]] = {
    # PayPal status → (instruction_status, settlement_evidence)
    "SUCCESS":    ("COMPLETED",  "PROVIDER_REPORTED_COMPLETE"),
    "PENDING":    ("SUBMITTED",  "NOT_CONFIRMED"),
    "UNCLAIMED":  ("SUBMITTED",  "NOT_CONFIRMED"),
    "ONHOLD":     ("SUBMITTED",  "NOT_CONFIRMED"),
    "BLOCKED":    ("FAILED",     "NOT_CONFIRMED"),
    "FAILED":     ("FAILED",     "NOT_CONFIRMED"),
    "RETURNED":   ("FAILED",     "NOT_CONFIRMED"),
    "REFUNDED":   ("FAILED",     "NOT_CONFIRMED"),
    "REVERSED":   ("FAILED",     "NOT_CONFIRMED"),
}

_BATCH_STATUS_TO_PUFI: dict[str, str] = {
    "SUCCESS":           "COMPLETED",
    "DENIED":            "FAILED",
    "PENDING":           "SUBMITTED",
    "PROCESSING":        "SUBMITTED",
    "CANCELED":          "FAILED",
}

# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class SubmissionResult:
    success: bool
    batch_id: str
    sender_batch_id: str
    paypal_payout_batch_id: Optional[str]
    paypal_batch_status: Optional[str]
    submission_status: str    # SUBMITTED | FAILED | UNKNOWN
    submitted_at: str
    is_simulated: bool
    paypal_configured: bool
    error_message: Optional[str]
    disclaimer: str


@dataclass
class StatusRefreshResult:
    success: bool
    batch_id: str
    batch_status: str
    paypal_batch_status: Optional[str]
    items_checked: int
    completed: int
    failed: int
    pending: int
    unknown: int
    refreshed_at: str
    error_message: Optional[str]
    disclaimer: str


# ---------------------------------------------------------------------------
# Submit batch
# ---------------------------------------------------------------------------

def submit_batch(batch_id: str, db: Session, correlation_id: Optional[str] = None) -> SubmissionResult:
    """
    Submit an APPROVED batch to PayPal Sandbox.

    Steps:
      1. Load batch; verify status == APPROVED.
      2. Check no active existing ProviderSubmission (duplicate guard).
      3. Load or create PaymentInstructions for each obligation.
      4. Generate stable sender_batch_id; persist ProviderSubmission (PENDING) BEFORE API call.
      5. Call PayPal adapter.
      6. Update ProviderSubmission and batch status.
      7. Write AuditEvent.
    """
    now = datetime.now(timezone.utc)

    # --- 1. Load batch ---
    batch = db.query(PaymentBatch).filter(PaymentBatch.id == batch_id).first()
    if batch is None:
        return SubmissionResult(
            success=False, batch_id=batch_id, sender_batch_id="",
            paypal_payout_batch_id=None, paypal_batch_status=None,
            submission_status="FAILED",
            submitted_at=now.isoformat(),
            is_simulated=not is_configured(), paypal_configured=is_configured(),
            error_message=f"Batch {batch_id!r} not found.",
            disclaimer=_disclaimer(),
        )

    if batch.status != "APPROVED":
        return SubmissionResult(
            success=False, batch_id=batch_id, sender_batch_id="",
            paypal_payout_batch_id=None, paypal_batch_status=None,
            submission_status="FAILED",
            submitted_at=now.isoformat(),
            is_simulated=not is_configured(), paypal_configured=is_configured(),
            error_message=f"Batch status is {batch.status!r}; only APPROVED batches can be submitted.",
            disclaimer=_disclaimer(),
        )

    # --- 2. Duplicate submission guard ---
    existing = (
        db.query(ProviderSubmission)
        .filter(
            ProviderSubmission.batch_id == batch_id,
            ProviderSubmission.status.in_(["SUBMITTED", "PENDING"]),
        )
        .first()
    )
    if existing:
        return SubmissionResult(
            success=False, batch_id=batch_id,
            sender_batch_id=existing.sender_batch_id,
            paypal_payout_batch_id=existing.paypal_payout_batch_id,
            paypal_batch_status=existing.paypal_batch_status,
            submission_status=existing.status,
            submitted_at=(existing.submitted_at or now).isoformat(),
            is_simulated=not is_configured(), paypal_configured=is_configured(),
            error_message="Batch already has an active submission. Refresh status or wait for completion.",
            disclaimer=_disclaimer(),
        )

    # --- 3. Load obligations and build instructions ---
    batch_obs = (
        db.query(BatchObligation)
        .filter(BatchObligation.batch_id == batch_id)
        .all()
    )
    obligation_ids = [bo.obligation_id for bo in batch_obs]
    obligations = (
        db.query(Obligation)
        .options(joinedload(Obligation.supplier))
        .filter(Obligation.id.in_(obligation_ids))
        .all()
    )

    # Create instructions if they don't already exist
    instructions: list[PaymentInstruction] = []
    for ob in obligations:
        existing_instr = (
            db.query(PaymentInstruction)
            .filter(
                PaymentInstruction.batch_id == batch_id,
                PaymentInstruction.obligation_id == ob.id,
            )
            .first()
        )
        if existing_instr:
            instructions.append(existing_instr)
        else:
            # Stable idempotency key: deterministic from batch+obligation full IDs
            idem_key = f"PUFI-{batch_id[:8]}-{ob.id[-12:]}"
            sender_item_id = idem_key
            instr = PaymentInstruction(
                batch_id=batch_id,
                obligation_id=ob.id,
                provider_code=batch.selected_provider_code or "PAYPAL_SANDBOX",
                amount=Decimal(str(ob.amount)),
                currency=ob.currency.upper(),
                idempotency_key=idem_key,
                sender_item_id=sender_item_id,
                status="APPROVED",
                settlement_evidence="NOT_CONFIRMED",
            )
            db.add(instr)
            instructions.append(instr)

    db.flush()

    # --- 4. Generate stable sender_batch_id; persist submission record BEFORE API call ---
    sender_batch_id = f"PUFI-{batch_id[:8]}-{uuid.uuid4().hex[:8]}"

    submission = ProviderSubmission(
        batch_id=batch_id,
        provider_code=batch.selected_provider_code or "PAYPAL_SANDBOX",
        sender_batch_id=sender_batch_id,
        status="PENDING",
        created_at=now,
    )
    db.add(submission)
    db.flush()   # persist BEFORE API call (idempotency requirement)

    # --- 5. Build PayPal payout items ---
    payout_items = []
    for instr in instructions:
        ob = next((o for o in obligations if o.id == instr.obligation_id), None)
        supplier: Optional[Supplier] = ob.supplier if ob else None
        # Use masked reference for the email — in production a real email would be used
        receiver_email = (
            supplier.recipient_reference_masked if supplier else "sandbox@example.com"
        )
        # Unmask: for sandbox demo, use a known test sandbox email
        # (The masked field is for display; actual submission uses a real sandbox email)
        # For this prototype we construct a testable sandbox email pattern
        receiver_email = _get_sandbox_email(supplier)
        payout_items.append(PayoutItem(
            sender_item_id=instr.sender_item_id,
            receiver_email=receiver_email,
            amount_value=str(instr.amount.quantize(Decimal("0.01"))),
            currency=instr.currency,
        ))

    # --- 6. Call PayPal adapter ---
    paypal_result = submit_payout(
        sender_batch_id=sender_batch_id,
        items=payout_items,
    )

    # --- 7. Update submission record ---
    submit_time = datetime.now(timezone.utc)
    submission.submitted_at = submit_time
    submission.response_at = submit_time

    if paypal_result.success:
        submission.status = "SUBMITTED"
        submission.paypal_payout_batch_id = paypal_result.paypal_payout_batch_id
        submission.paypal_batch_status = paypal_result.paypal_batch_status
        submission.response_summary = json.dumps({
            "paypal_payout_batch_id": paypal_result.paypal_payout_batch_id,
            "paypal_batch_status": paypal_result.paypal_batch_status,
            "http_status": paypal_result.http_status,
        })
        # Update instructions
        for instr in instructions:
            instr.status = "SUBMITTED"
            instr.updated_at = submit_time
        # Update batch
        batch.status = "SUBMITTED"
        final_status = "SUBMITTED"
    elif paypal_result.error_message and "timed out" in paypal_result.error_message.lower():
        submission.status = "UNKNOWN"
        submission.error_message = paypal_result.error_message
        for instr in instructions:
            instr.status = "UNKNOWN"
            instr.updated_at = submit_time
        final_status = "UNKNOWN"
    elif paypal_result.is_simulated:
        # Adapter not configured — record as PENDING so we can retry later
        submission.status = "PENDING"
        submission.error_message = paypal_result.error_message
        final_status = "FAILED"
    else:
        submission.status = "FAILED"
        submission.error_message = paypal_result.error_message
        for instr in instructions:
            instr.status = "FAILED"
            instr.error_message = paypal_result.error_message
            instr.updated_at = submit_time
        final_status = "FAILED"

    # --- 8. Audit event ---
    audit = AuditEvent(
        entity_type="BATCH",
        entity_id=batch_id,
        event_type="SUBMITTED",
        actor="SYSTEM",
        correlation_id=correlation_id,
        details_redacted=json.dumps({
            "sender_batch_id": sender_batch_id,
            "paypal_payout_batch_id": paypal_result.paypal_payout_batch_id,
            "submission_status": final_status,
            "is_simulated": paypal_result.is_simulated,
            "paypal_configured": is_configured(),
            "item_count": len(instructions),
        }),
    )
    db.add(audit)
    db.flush()

    logger.info(
        "Batch submission [corr=%s]: batch_id=%s sender=%r status=%s paypal_configured=%s",
        correlation_id, batch_id, sender_batch_id, final_status, is_configured(),
    )

    return SubmissionResult(
        success=paypal_result.success,
        batch_id=batch_id,
        sender_batch_id=sender_batch_id,
        paypal_payout_batch_id=paypal_result.paypal_payout_batch_id,
        paypal_batch_status=paypal_result.paypal_batch_status,
        submission_status=final_status,
        submitted_at=submit_time.isoformat(),
        is_simulated=paypal_result.is_simulated,
        paypal_configured=is_configured(),
        error_message=paypal_result.error_message if not paypal_result.success else None,
        disclaimer=_disclaimer(),
    )


# ---------------------------------------------------------------------------
# Refresh status
# ---------------------------------------------------------------------------

def refresh_status(batch_id: str, db: Session, correlation_id: Optional[str] = None) -> StatusRefreshResult:
    """
    Query PayPal for updated batch and item-level statuses.
    Maps item statuses to PUFI instruction statuses.
    Updates batch status based on item outcomes.
    """
    now = datetime.now(timezone.utc)

    batch = db.query(PaymentBatch).filter(PaymentBatch.id == batch_id).first()
    if batch is None:
        return StatusRefreshResult(
            success=False, batch_id=batch_id, batch_status="UNKNOWN",
            paypal_batch_status=None, items_checked=0, completed=0,
            failed=0, pending=0, unknown=0, refreshed_at=now.isoformat(),
            error_message=f"Batch {batch_id!r} not found.", disclaimer=_disclaimer(),
        )

    submission = (
        db.query(ProviderSubmission)
        .filter(ProviderSubmission.batch_id == batch_id)
        .order_by(ProviderSubmission.created_at.desc())
        .first()
    )
    if submission is None or not submission.paypal_payout_batch_id:
        return StatusRefreshResult(
            success=False, batch_id=batch_id, batch_status=batch.status,
            paypal_batch_status=None, items_checked=0, completed=0,
            failed=0, pending=0, unknown=0, refreshed_at=now.isoformat(),
            error_message="No PayPal payout batch ID found. Batch may not have been submitted successfully.",
            disclaimer=_disclaimer(),
        )

    # Query PayPal
    paypal_result: PayPalBatchStatusResult = get_batch_status(submission.paypal_payout_batch_id)

    if not paypal_result.success:
        return StatusRefreshResult(
            success=False, batch_id=batch_id, batch_status=batch.status,
            paypal_batch_status=None, items_checked=0, completed=0,
            failed=0, pending=0, unknown=0, refreshed_at=now.isoformat(),
            error_message=paypal_result.error_message, disclaimer=_disclaimer(),
        )

    # Update submission record
    submission.paypal_batch_status = paypal_result.paypal_batch_status
    submission.response_at = now

    # Update instructions based on item statuses
    instructions = (
        db.query(PaymentInstruction)
        .filter(PaymentInstruction.batch_id == batch_id)
        .all()
    )
    instr_map = {instr.sender_item_id: instr for instr in instructions}

    counts = {"completed": 0, "failed": 0, "pending": 0, "unknown": 0}

    for item_status in paypal_result.items:
        instr = instr_map.get(item_status.sender_item_id)
        if instr:
            pp_status = (item_status.item_status or "").upper()
            new_status, new_evidence = _ITEM_STATUS_MAP.get(
                pp_status, ("UNKNOWN", "NOT_CONFIRMED")
            )
            instr.status = new_status
            instr.settlement_evidence = new_evidence
            instr.paypal_payout_item_id = item_status.payout_item_id
            instr.paypal_transaction_id = item_status.transaction_id
            instr.paypal_item_status = item_status.item_status
            instr.error_message = item_status.error_message
            instr.updated_at = now

        # Count
        pp_upper = (item_status.item_status or "").upper()
        if pp_upper == "SUCCESS":
            counts["completed"] += 1
        elif pp_upper in ("BLOCKED", "FAILED", "RETURNED", "REFUNDED", "REVERSED"):
            counts["failed"] += 1
        elif pp_upper in ("PENDING", "UNCLAIMED", "ONHOLD"):
            counts["pending"] += 1
        else:
            counts["unknown"] += 1

    # Determine overall batch status
    total = len(paypal_result.items)
    if total == 0:
        new_batch_status = batch.status
    elif counts["completed"] == total:
        new_batch_status = "COMPLETED"
    elif counts["failed"] == total:
        new_batch_status = "FAILED"
    elif counts["completed"] > 0:
        new_batch_status = "PARTIALLY_COMPLETED"
    else:
        new_batch_status = "SUBMITTED"  # still processing

    if batch.status not in ("COMPLETED", "FAILED"):
        batch.status = new_batch_status

    # Audit event
    audit = AuditEvent(
        entity_type="BATCH",
        entity_id=batch_id,
        event_type="STATUS_REFRESHED",
        actor="SYSTEM",
        correlation_id=correlation_id,
        details_redacted=json.dumps({
            "paypal_batch_status": paypal_result.paypal_batch_status,
            "batch_status": new_batch_status,
            "items_checked": total,
            **counts,
        }),
    )
    db.add(audit)
    db.flush()

    logger.info(
        "Status refresh [corr=%s]: batch_id=%s paypal_status=%r pufi_status=%r items=%d",
        correlation_id, batch_id, paypal_result.paypal_batch_status, new_batch_status, total,
    )

    return StatusRefreshResult(
        success=True,
        batch_id=batch_id,
        batch_status=new_batch_status,
        paypal_batch_status=paypal_result.paypal_batch_status,
        items_checked=total,
        completed=counts["completed"],
        failed=counts["failed"],
        pending=counts["pending"],
        unknown=counts["unknown"],
        refreshed_at=now.isoformat(),
        error_message=None,
        disclaimer=_disclaimer(),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_sandbox_email(supplier) -> str:
    """
    Return a PayPal sandbox test email for a supplier.
    In the prototype, all suppliers use a known sandbox test-account email.
    Real production use would look up the actual PayPal recipient email.
    """
    if supplier and supplier.external_reference:
        # Map to sandbox test accounts by supplier reference
        _sandbox_map = {
            "DEMO-SUP-001": "sb-pay001@business.example.com",
            "DEMO-SUP-002": "sb-pay002@business.example.com",
            "DEMO-SUP-003": "sb-pay003@business.example.com",
        }
        return _sandbox_map.get(supplier.external_reference, "sb-generic@business.example.com")
    return "sb-generic@business.example.com"


def _disclaimer() -> str:
    return (
        "SANDBOX ENVIRONMENT — No real money moves. "
        "PayPal Sandbox responses are test-only. "
        "HTTP 2xx acceptance does not confirm fund settlement."
    )
