"""
PUFI — Execution Coordinator (Remediated Architecture).

Orchestrates:
  submit_batch()                — validates parameters & recipients, creates PaymentInstructions,
                                  dispatches to selected provider (PayPal Sandbox or Simulated rails),
                                  records submission idempotency record BEFORE API call.
  refresh_batch_status()        — queries provider for updated batch/item statuses and reconciles UNKNOWN / SUBMITTED states.
  reconcile_unknown_submission()— explicit reconciliation workflow for payments in ambiguous states.

FINANCIAL RULES:
  - sender_batch_id is persisted BEFORE any external API call.
  - On timeout, submission status = UNKNOWN; batch status = UNKNOWN.
  - Resubmission of UNKNOWN payment is strictly BLOCKED until verified/reconciled.
  - Recipient email configuration is strictly validated; placeholder example.com addresses are rejected.
  - Multi-provider execution dispatch routes through registered providers (PayPal Sandbox vs Simulated).
  - All audit events are hash-chained for tamper-evident integrity.
"""
from __future__ import annotations

import json
import logging
import os
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from models.entities import (
    ActiveBatchSubmission, AuditEvent, BatchObligation, Obligation, PaymentBatch,
    PaymentInstruction, ProviderSubmission, Supplier,
)
from services.audit import record_audit_event
from services.paypal_adapter import (
    PayoutItem, PayPalBatchStatusResult, is_configured,
    submit_payout, get_batch_status, query_payout_by_sender_batch_id,
)
from services.simulated_adapter import submit_simulated_payout, SimulatedPayoutResult

logger = logging.getLogger("pufi.execution")

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# ---------------------------------------------------------------------------
# PayPal item status → PUFI status mapping
# ---------------------------------------------------------------------------

_ITEM_STATUS_MAP: dict[str, tuple[str, str]] = {
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
# Recipient Validation & Resolution (Phase 2)
# ---------------------------------------------------------------------------

def validate_recipient_email(email: Optional[str]) -> tuple[bool, Optional[str]]:
    """
    Validates recipient email address.
    Rejects:
      - None / empty / whitespace
      - Malformed email strings
      - Prohibited placeholder addresses (e.g. ending in business.example.com or containing 'placeholder')
    """
    if not email or not email.strip():
        return False, "Recipient email address is missing or empty."
    email = email.strip()
    if not EMAIL_REGEX.match(email):
        return False, f"Recipient email {email!r} has invalid format."
    lower = email.lower()
    if lower.endswith("@business.example.com") or "placeholder" in lower or lower.startswith("sb-generic@"):
        return False, f"Prohibited placeholder recipient address: {email!r}. A valid Sandbox recipient account is required."
    return True, None


def resolve_sandbox_recipient(supplier: Optional[Supplier]) -> tuple[Optional[str], Optional[str]]:
    """
    Resolves and validates a recipient email for a supplier targeting PayPal Sandbox.
    Priority:
      1. Explicit supplier.sandbox_recipient_email if configured
      2. Environment variable PAYPAL_SANDBOX_RECIPIENT_EMAIL
      3. supplier.recipient_reference_masked IF it is a valid unmasked email (not containing asterisks)
    """
    if supplier is None:
        return None, "Obligation has no associated supplier."

    candidate: Optional[str] = None
    if getattr(supplier, "sandbox_recipient_email", None):
        candidate = supplier.sandbox_recipient_email.strip()
    elif os.getenv("PAYPAL_SANDBOX_RECIPIENT_EMAIL", "").strip():
        candidate = os.getenv("PAYPAL_SANDBOX_RECIPIENT_EMAIL", "").strip()
    elif supplier.recipient_reference_masked and "*" not in supplier.recipient_reference_masked:
        candidate = supplier.recipient_reference_masked.strip()

    valid, reason = validate_recipient_email(candidate)
    if not valid:
        return None, f"Supplier {supplier.external_reference} invalid recipient: {reason}"
    return candidate, None


# ---------------------------------------------------------------------------
# Submit batch (Phases 1, 2, 3)
# ---------------------------------------------------------------------------

def submit_batch(batch_id: str, db: Session, correlation_id: Optional[str] = None) -> SubmissionResult:
    """
    Submit an APPROVED batch to the selected provider (PayPal Sandbox or Simulated rails).

    Phases enforced:
      1. Safe state model & UNKNOWN payment timeout protection: duplicate resubmission blocked.
      2. Verified recipient configuration: rejects missing/invalid/placeholder recipients.
      3. Provider-specific execution dispatch: PayPal Sandbox vs Simulated rails.
      4. Cryptographic audit trail logging.
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

    if batch.status not in ("APPROVED", "UNKNOWN"):
        return SubmissionResult(
            success=False, batch_id=batch_id, sender_batch_id="",
            paypal_payout_batch_id=None, paypal_batch_status=None,
            submission_status="FAILED",
            submitted_at=now.isoformat(),
            is_simulated=not is_configured(), paypal_configured=is_configured(),
            error_message=f"Batch status is {batch.status!r}; only APPROVED batches can be submitted.",
            disclaimer=_disclaimer(),
        )

    # --- 2. Database-enforced concurrent lock guard (Phase 2) ---
    active_lock = db.query(ActiveBatchSubmission).filter(ActiveBatchSubmission.batch_id == batch_id).first()
    if active_lock:
        return SubmissionResult(
            success=False,
            batch_id=batch_id,
            sender_batch_id="",
            paypal_payout_batch_id=None,
            paypal_batch_status=None,
            submission_status="FAILED",
            submitted_at=now.isoformat(),
            is_simulated=not is_configured(),
            paypal_configured=is_configured(),
            error_message="CONCURRENT_SUBMISSION_CONFLICT: A submission is currently in progress for this batch.",
            disclaimer=_disclaimer(),
        )

    # --- 3. Duplicate submission & UNKNOWN state guard (Phase 1) ---
    existing = (
        db.query(ProviderSubmission)
        .filter(
            ProviderSubmission.batch_id == batch_id,
            ProviderSubmission.status.in_(["SUBMITTED", "PENDING", "UNKNOWN"]),
        )
        .order_by(ProviderSubmission.created_at.desc())
        .first()
    )
    if existing:
        if existing.status == "UNKNOWN":
            return SubmissionResult(
                success=False,
                batch_id=batch_id,
                sender_batch_id=existing.sender_batch_id,
                paypal_payout_batch_id=existing.paypal_payout_batch_id,
                paypal_batch_status=existing.paypal_batch_status,
                submission_status="UNKNOWN",
                submitted_at=(existing.submitted_at or now).isoformat(),
                is_simulated=not is_configured(),
                paypal_configured=is_configured(),
                error_message=(
                    "PAYMENT_STATE_UNKNOWN: A previous payout submission timed out. "
                    "The payment state is uncertain and duplicate submission is blocked. "
                    "Provider status verification or reconciliation is required before resubmitting."
                ),
                disclaimer=_disclaimer(),
            )
        return SubmissionResult(
            success=False,
            batch_id=batch_id,
            sender_batch_id=existing.sender_batch_id,
            paypal_payout_batch_id=existing.paypal_payout_batch_id,
            paypal_batch_status=existing.paypal_batch_status,
            submission_status=existing.status,
            submitted_at=(existing.submitted_at or now).isoformat(),
            is_simulated=not is_configured(),
            paypal_configured=is_configured(),
            error_message="Batch already has an active submission. Refresh status or wait for completion.",
            disclaimer=_disclaimer(),
        )

    # --- Check selected provider code (Phase 3) ---
    provider_code = batch.selected_provider_code or "PAYPAL_SANDBOX"
    if provider_code not in ("PAYPAL_SANDBOX", "SIMULATED_FAST", "SIMULATED_ECONOMY"):
        return SubmissionResult(
            success=False,
            batch_id=batch_id,
            sender_batch_id="",
            paypal_payout_batch_id=None,
            paypal_batch_status=None,
            submission_status="FAILED",
            submitted_at=now.isoformat(),
            is_simulated=False,
            paypal_configured=is_configured(),
            error_message=f"UNSUPPORTED_PROVIDER: Provider {provider_code!r} is not registered or supported for execution.",
            disclaimer=_disclaimer(),
        )

    # --- 4. Load obligations and build instructions ---
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

    instructions: list[PaymentInstruction] = []
    total_intended_amount = Decimal("0.00")
    primary_currency = "USD"

    for ob in obligations:
        ob_amount = Decimal(str(ob.amount))
        total_intended_amount += ob_amount
        primary_currency = ob.currency.upper()
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
            idem_key = f"PUFI-{batch_id[:8]}-{ob.id[-12:]}"
            sender_item_id = idem_key
            instr = PaymentInstruction(
                batch_id=batch_id,
                obligation_id=ob.id,
                provider_code=provider_code,
                amount=ob_amount,
                currency=ob.currency.upper(),
                idempotency_key=idem_key,
                sender_item_id=sender_item_id,
                status="APPROVED",
                settlement_evidence="NOT_CONFIRMED",
            )
            db.add(instr)
            instructions.append(instr)

    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        return SubmissionResult(
            success=False,
            batch_id=batch_id,
            sender_batch_id="",
            paypal_payout_batch_id=None,
            paypal_batch_status=None,
            submission_status="FAILED",
            submitted_at=now.isoformat(),
            is_simulated=not is_configured(),
            paypal_configured=is_configured(),
            error_message="CONCURRENT_SUBMISSION_CONFLICT: A submission is currently in progress for this batch.",
            disclaimer=_disclaimer(),
        )

    # --- 5. Generate stable sender_batch_id & Validate Recipients ---
    sender_batch_id = f"PUFI-{batch_id[:8]}-{uuid.uuid4().hex[:8]}"

    payout_items = []
    for instr in instructions:
        ob = next((o for o in obligations if o.id == instr.obligation_id), None)
        supplier: Optional[Supplier] = ob.supplier if ob else None

        if provider_code == "PAYPAL_SANDBOX":
            receiver_email, err = resolve_sandbox_recipient(supplier)
            if not receiver_email:
                return SubmissionResult(
                    success=False,
                    batch_id=batch_id,
                    sender_batch_id=sender_batch_id,
                    paypal_payout_batch_id=None,
                    paypal_batch_status=None,
                    submission_status="FAILED",
                    submitted_at=now.isoformat(),
                    is_simulated=False,
                    paypal_configured=is_configured(),
                    error_message=f"INVALID_RECIPIENT_CONFIGURATION: {err}",
                    disclaimer=_disclaimer(),
                )
        else:
            receiver_email = (
                supplier.recipient_reference_masked
                if supplier
                else f"sim-{instr.sender_item_id[-8:]}@example.sim"
            )

        payout_items.append(PayoutItem(
            sender_item_id=instr.sender_item_id,
            receiver_email=receiver_email,
            amount_value=str(instr.amount.quantize(Decimal("0.01"))),
            currency=instr.currency,
        ))

    # --- 6. TRANSACTION 1: Persist Durable Submission Intent & Active Lock (Phase 1 & 2) ---
    try:
        submission = ProviderSubmission(
            batch_id=batch_id,
            provider_code=provider_code,
            sender_batch_id=sender_batch_id,
            status="PENDING",
            intended_amount=total_intended_amount,
            currency=primary_currency,
            item_count=len(payout_items),
            created_at=now,
        )
        db.add(submission)
        db.flush()  # populate submission.id

        submission_id = submission.id
        active_submission = ActiveBatchSubmission(
            batch_id=batch_id,
            submission_id=submission_id,
            created_at=now,
        )
        db.add(active_submission)
        batch.status = "SUBMISSION_PENDING"
        db.flush()  # Immediately enforce PRIMARY KEY uniqueness constraint!

        record_audit_event(
            db=db,
            entity_type="BATCH",
            entity_id=batch_id,
            event_type="SUBMISSION_INTENT_COMMITTED",
            actor="SYSTEM",
            correlation_id=correlation_id,
            details_redacted=json.dumps({
                "submission_id": submission_id,
                "sender_batch_id": sender_batch_id,
                "provider_code": provider_code,
                "intended_amount": str(total_intended_amount),
                "currency": primary_currency,
                "item_count": len(payout_items),
            }),
        )

        db.commit()  # TRANSACTION 1 COMMITTED TO DISK BEFORE CALLING EXTERNAL API!
    except IntegrityError:
        db.rollback()
        return SubmissionResult(
            success=False,
            batch_id=batch_id,
            sender_batch_id=sender_batch_id,
            paypal_payout_batch_id=None,
            paypal_batch_status=None,
            submission_status="FAILED",
            submitted_at=now.isoformat(),
            is_simulated=not is_configured(),
            paypal_configured=is_configured(),
            error_message="CONCURRENT_SUBMISSION_CONFLICT: A submission is currently in progress for this batch.",
            disclaimer=_disclaimer(),
        )

    # --- 7. EXTERNAL NETWORK CALL (No database transaction held open!) ---
    submit_time = datetime.now(timezone.utc)

    if provider_code == "PAYPAL_SANDBOX":
        paypal_result = None
        network_exc_msg = None
        try:
            paypal_result = submit_payout(
                sender_batch_id=sender_batch_id,
                items=payout_items,
            )
        except Exception as exc:
            logger.exception("Unexpected exception during PayPal payout submission: %s", exc)
            network_exc_msg = str(exc)

        # --- 8. TRANSACTION 2: Record Provider Response ---
        submission = db.query(ProviderSubmission).filter(ProviderSubmission.id == submission_id).first()
        batch = db.query(PaymentBatch).filter(PaymentBatch.id == batch_id).first()
        instructions = db.query(PaymentInstruction).filter(PaymentInstruction.batch_id == batch_id).all()
        active_sub = db.query(ActiveBatchSubmission).filter(ActiveBatchSubmission.batch_id == batch_id).first()

        submission.submitted_at = submit_time
        submission.response_at = submit_time

        if paypal_result is not None and paypal_result.success:
            submission.status = "SUBMITTED"
            submission.paypal_payout_batch_id = paypal_result.paypal_payout_batch_id
            submission.paypal_batch_status = paypal_result.paypal_batch_status
            submission.response_summary = json.dumps({
                "paypal_payout_batch_id": paypal_result.paypal_payout_batch_id,
                "paypal_batch_status": paypal_result.paypal_batch_status,
                "http_status": paypal_result.http_status,
            })
            for instr in instructions:
                instr.status = "SUBMITTED"
                instr.updated_at = submit_time
            batch.status = "SUBMITTED"
            final_status = "SUBMITTED"

            if active_sub:
                db.delete(active_sub)

            record_audit_event(
                db=db,
                entity_type="BATCH",
                entity_id=batch_id,
                event_type="SUBMITTED",
                actor="SYSTEM",
                correlation_id=correlation_id,
                details_redacted=json.dumps({
                    "sender_batch_id": sender_batch_id,
                    "provider_code": provider_code,
                    "paypal_payout_batch_id": paypal_result.paypal_payout_batch_id,
                    "submission_status": final_status,
                    "is_simulated": paypal_result.is_simulated,
                    "paypal_configured": is_configured(),
                    "item_count": len(instructions),
                }),
            )
            db.commit()

            return SubmissionResult(
                success=True,
                batch_id=batch_id,
                sender_batch_id=sender_batch_id,
                paypal_payout_batch_id=paypal_result.paypal_payout_batch_id,
                paypal_batch_status=paypal_result.paypal_batch_status,
                submission_status=final_status,
                submitted_at=submit_time.isoformat(),
                is_simulated=paypal_result.is_simulated,
                paypal_configured=is_configured(),
                error_message=None,
                disclaimer=_disclaimer(),
            )

        elif (
            paypal_result is None
            or (
                paypal_result.error_message
                and (
                    "timed out" in paypal_result.error_message.lower()
                    or "timeout" in paypal_result.error_message.lower()
                )
            )
        ):
            # Uncertain outcome: do NOT assume rejection. Mark UNKNOWN.
            timeout_msg = (
                paypal_result.error_message
                if paypal_result and paypal_result.error_message
                else f"Network/Process timeout during provider communication: {network_exc_msg}"
            )
            submission.status = "UNKNOWN"
            submission.error_message = timeout_msg
            batch.status = "UNKNOWN"
            for instr in instructions:
                instr.status = "UNKNOWN"
                instr.updated_at = submit_time
            final_status = "UNKNOWN"

            if active_sub:
                db.delete(active_sub)

            record_audit_event(
                db=db,
                entity_type="BATCH",
                entity_id=batch_id,
                event_type="SUBMISSION_TIMEOUT_UNKNOWN",
                actor="SYSTEM",
                correlation_id=correlation_id,
                details_redacted=json.dumps({
                    "sender_batch_id": sender_batch_id,
                    "provider_code": provider_code,
                    "error_message": timeout_msg,
                    "submission_status": "UNKNOWN",
                }),
            )
            db.commit()

            return SubmissionResult(
                success=False,
                batch_id=batch_id,
                sender_batch_id=sender_batch_id,
                paypal_payout_batch_id=None,
                paypal_batch_status=None,
                submission_status="UNKNOWN",
                submitted_at=submit_time.isoformat(),
                is_simulated=not is_configured(),
                paypal_configured=is_configured(),
                error_message=timeout_msg,
                disclaimer=_disclaimer(),
            )

        elif paypal_result.is_simulated:
            submission.status = "PENDING"
            submission.error_message = paypal_result.error_message
            final_status = "FAILED"
            batch.status = "FAILED"
            if active_sub:
                db.delete(active_sub)
            record_audit_event(
                db=db,
                entity_type="BATCH",
                entity_id=batch_id,
                event_type="SUBMISSION_UNCONFIGURED_FAILED",
                actor="SYSTEM",
                correlation_id=correlation_id,
                details_redacted=json.dumps({"error": paypal_result.error_message}),
            )
            db.commit()

            return SubmissionResult(
                success=False,
                batch_id=batch_id,
                sender_batch_id=sender_batch_id,
                paypal_payout_batch_id=None,
                paypal_batch_status=None,
                submission_status="FAILED",
                submitted_at=submit_time.isoformat(),
                is_simulated=True,
                paypal_configured=False,
                error_message=paypal_result.error_message,
                disclaimer=_disclaimer(),
            )

        else:
            # Confirmed provider rejection (e.g. 400 Bad Request, unparseable payload)
            submission.status = "FAILED"
            submission.error_message = paypal_result.error_message
            batch.status = "FAILED"
            for instr in instructions:
                instr.status = "FAILED"
                instr.error_message = paypal_result.error_message
                instr.updated_at = submit_time
            final_status = "FAILED"

            if active_sub:
                db.delete(active_sub)

            record_audit_event(
                db=db,
                entity_type="BATCH",
                entity_id=batch_id,
                event_type="SUBMISSION_REJECTED",
                actor="SYSTEM",
                correlation_id=correlation_id,
                details_redacted=json.dumps({
                    "sender_batch_id": sender_batch_id,
                    "provider_code": provider_code,
                    "error_message": paypal_result.error_message,
                }),
            )
            db.commit()

            return SubmissionResult(
                success=False,
                batch_id=batch_id,
                sender_batch_id=sender_batch_id,
                paypal_payout_batch_id=None,
                paypal_batch_status=None,
                submission_status="FAILED",
                submitted_at=submit_time.isoformat(),
                is_simulated=paypal_result.is_simulated,
                paypal_configured=is_configured(),
                error_message=paypal_result.error_message,
                disclaimer=_disclaimer(),
            )

    else:
        # Simulated Rail Execution
        sim_result: SimulatedPayoutResult = submit_simulated_payout(
            provider_code=provider_code,
            sender_batch_id=sender_batch_id,
            items=payout_items,
        )

        submission = db.query(ProviderSubmission).filter(ProviderSubmission.id == submission_id).first()
        batch = db.query(PaymentBatch).filter(PaymentBatch.id == batch_id).first()
        instructions = db.query(PaymentInstruction).filter(PaymentInstruction.batch_id == batch_id).all()
        active_sub = db.query(ActiveBatchSubmission).filter(ActiveBatchSubmission.batch_id == batch_id).first()

        submission.submitted_at = submit_time
        submission.response_at = submit_time
        submission.status = "SUBMITTED"
        submission.paypal_payout_batch_id = sim_result.provider_batch_id
        submission.paypal_batch_status = sim_result.batch_status
        submission.response_summary = json.dumps({
            "provider_batch_id": sim_result.provider_batch_id,
            "provider_batch_status": sim_result.batch_status,
            "is_simulated": True,
        })

        for instr in instructions:
            if provider_code == "SIMULATED_FAST":
                instr.status = "COMPLETED"
                instr.settlement_evidence = "SIMULATED_IMMEDIATE_SETTLEMENT"
            else:
                instr.status = "SUBMITTED"
                instr.settlement_evidence = "SIMULATED_PENDING_SETTLEMENT"
            instr.updated_at = submit_time

        batch.status = "COMPLETED" if provider_code == "SIMULATED_FAST" else "SUBMITTED"
        final_status = "SUBMITTED"

        if active_sub:
            db.delete(active_sub)

        # Record hash-chained audit event (Phase 5)
        record_audit_event(
            db=db,
            entity_type="BATCH",
            entity_id=batch_id,
            event_type="SUBMITTED_SIMULATED",
            actor="SYSTEM",
            correlation_id=correlation_id,
            details_redacted=json.dumps({
                "sender_batch_id": sender_batch_id,
                "provider_code": provider_code,
                "provider_batch_id": sim_result.provider_batch_id,
                "submission_status": final_status,
                "is_simulated": True,
                "item_count": len(instructions),
            }),
        )
        db.commit()

        return SubmissionResult(
            success=True,
            batch_id=batch_id,
            sender_batch_id=sender_batch_id,
            paypal_payout_batch_id=sim_result.provider_batch_id,
            paypal_batch_status=sim_result.batch_status,
            submission_status=final_status,
            submitted_at=submit_time.isoformat(),
            is_simulated=True,
            paypal_configured=is_configured(),
            error_message=None,
            disclaimer=_disclaimer(),
        )


# ---------------------------------------------------------------------------
# Refresh batch status & Reconcile UNKNOWN payments (Phase 1)
# ---------------------------------------------------------------------------

def refresh_batch_status(
    batch_id: str,
    db: Session,
    correlation_id: Optional[str] = None,
) -> StatusRefreshResult:
    """
    Query provider for current batch and item statuses.
    Safely reconciles UNKNOWN / PENDING / SUBMITTED states.
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
        .filter(
            ProviderSubmission.batch_id == batch_id,
            ProviderSubmission.status.in_(["SUBMITTED", "UNKNOWN", "PENDING"]),
        )
        .order_by(ProviderSubmission.created_at.desc())
        .first()
    )
    if submission is None:
        # Fall back to any submission
        submission = (
            db.query(ProviderSubmission)
            .filter(ProviderSubmission.batch_id == batch_id)
            .order_by(ProviderSubmission.created_at.desc())
            .first()
        )

    if submission is None or not submission.paypal_payout_batch_id:
        # Priority 1.1 — Issue 1: Stranded PENDING submission recovery after process crash
        if submission and submission.status == "PENDING":
            return recover_stranded_submission(batch_id=batch_id, db=db, correlation_id=correlation_id)

        # Case B: Missing provider payout batch ID — payment remains UNKNOWN
        if submission and submission.status == "UNKNOWN":
            record_audit_event(
                db=db,
                entity_type="BATCH",
                entity_id=batch_id,
                event_type="RECONCILIATION_ATTEMPT_UNRESOLVED",
                actor="SYSTEM",
                correlation_id=correlation_id,
                details_redacted=json.dumps({
                    "reason": "Missing provider payout batch ID; payment remains UNKNOWN pending provider inquiry.",
                }),
            )
            db.commit()
        return StatusRefreshResult(
            success=False, batch_id=batch_id, batch_status=batch.status,
            paypal_batch_status=None, items_checked=0, completed=0,
            failed=0, pending=0, unknown=0, refreshed_at=now.isoformat(),
            error_message="No PayPal payout batch ID found. Payment remains UNKNOWN pending manual provider inquiry or webhook correlation.",
            disclaimer=_disclaimer(),
        )

    # Query PayPal or simulated status
    if submission.provider_code.startswith("SIMULATED"):
        # Simulated rails don't query external network
        batch_status = "COMPLETED" if submission.provider_code == "SIMULATED_FAST" else "SUBMITTED"
        return StatusRefreshResult(
            success=True, batch_id=batch_id, batch_status=batch_status,
            paypal_batch_status="SUCCESS", items_checked=1, completed=1,
            failed=0, pending=0, unknown=0, refreshed_at=now.isoformat(),
            error_message=None, disclaimer=_disclaimer(),
        )

    paypal_result: PayPalBatchStatusResult = get_batch_status(submission.paypal_payout_batch_id)

    if not paypal_result.success:
        return StatusRefreshResult(
            success=False, batch_id=batch_id, batch_status=batch.status,
            paypal_batch_status=None, items_checked=0, completed=0,
            failed=0, pending=0, unknown=0, refreshed_at=now.isoformat(),
            error_message=paypal_result.error_message, disclaimer=_disclaimer(),
        )

    # Update submission record
    was_unknown = submission.status == "UNKNOWN"
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
            # Enforce state precedence: do not regress COMPLETED unless refunded/reversed/returned
            if instr.status == "COMPLETED" and pp_status not in ("REFUNDED", "REVERSED", "RETURNED"):
                pass  # Keep COMPLETED
            else:
                instr.status = new_status
                instr.settlement_evidence = new_evidence
            instr.paypal_payout_item_id = item_status.payout_item_id
            instr.paypal_transaction_id = item_status.transaction_id
            instr.paypal_item_status = item_status.item_status
            instr.error_message = item_status.error_message
            instr.updated_at = now

        pp_upper = (item_status.item_status or "").upper()
        if pp_upper == "SUCCESS" or (instr and instr.status == "COMPLETED"):
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
        new_batch_status = "SUBMITTED"

    batch.status = new_batch_status
    if was_unknown and new_batch_status in ("COMPLETED", "FAILED", "PARTIALLY_COMPLETED", "SUBMITTED"):
        submission.status = "SUBMITTED" if new_batch_status != "FAILED" else "FAILED"

    # Clean up any lingering active lock if terminal or resolved
    if new_batch_status in ("COMPLETED", "FAILED", "PARTIALLY_COMPLETED", "SUBMITTED"):
        db.query(ActiveBatchSubmission).filter(ActiveBatchSubmission.batch_id == batch_id).delete()

    # Record hash-chained audit event (Phase 5)
    event_type = "RECONCILIATION_RESOLVED" if was_unknown else "STATUS_REFRESHED"
    record_audit_event(
        db=db,
        entity_type="BATCH",
        entity_id=batch_id,
        event_type=event_type,
        actor="SYSTEM",
        correlation_id=correlation_id,
        details_redacted=json.dumps({
            "paypal_batch_status": paypal_result.paypal_batch_status,
            "new_batch_status": new_batch_status,
            "was_unknown": was_unknown,
            "counts": counts,
        }),
    )
    db.commit()

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


def reconcile_unknown_submission(
    batch_id: str,
    db: Session,
    correlation_id: Optional[str] = None,
) -> StatusRefreshResult:
    """
    Explicit reconciliation endpoint/service method for UNKNOWN payment states.
    Audits the reconciliation attempt and checks provider-side status.
    """
    logger.info("Initiating reconciliation for payment batch %s", batch_id)
    record_audit_event(
        db=db,
        entity_type="BATCH",
        entity_id=batch_id,
        event_type="RECONCILIATION_ATTEMPT",
        actor="SYSTEM",
        correlation_id=correlation_id,
        details_redacted=json.dumps({"action": "reconcile_unknown_submission"}),
    )
    return refresh_batch_status(batch_id=batch_id, db=db, correlation_id=correlation_id)


def recover_stranded_submission(
    batch_id: str,
    db: Session,
    correlation_id: Optional[str] = None,
) -> StatusRefreshResult:
    """
    Recover stranded PENDING submissions after process crash/termination (Priority 1.1 — Issue 1).

    Orchestrates safe recovery for a batch where Transaction 1 committed a ProviderSubmission
    with status PENDING and ActiveBatchSubmission, but the process terminated before Transaction 2.

    Rules:
      1. Uses persisted sender_batch_id as the original provider correlation identifier.
      2. Never generates a new sender_batch_id merely because the response was lost.
      3. Never blindly re-submits the payout (financial safety: could double-pay if original reached provider).
      4. Inquires with provider adapter to determine if outcome can be established.
      5. If provider cannot confirm (PayPal lacks read-only query by sender_batch_id):
         - Preserves submission record, timestamps, and original sender_batch_id.
         - Transitions ProviderSubmission.status to UNKNOWN.
         - Transitions PaymentBatch.status to UNKNOWN.
         - Transitions all PaymentInstruction records to UNKNOWN.
         - Cleans up ActiveBatchSubmission lock (so batch is not locked in crash state).
         - Records hash-chained STRANDED_SUBMISSION_RECOVERED audit event.
         - Database commit ensures recovery state is persistent.
    """
    now = datetime.now(timezone.utc)

    batch = db.query(PaymentBatch).filter(PaymentBatch.id == batch_id).first()
    if not batch:
        return StatusRefreshResult(
            success=False, batch_id=batch_id, batch_status="UNKNOWN",
            paypal_batch_status=None, items_checked=0, completed=0,
            failed=0, pending=0, unknown=0, refreshed_at=now.isoformat(),
            error_message=f"Batch {batch_id!r} not found.", disclaimer=_disclaimer(),
        )

    submission = (
        db.query(ProviderSubmission)
        .filter(
            ProviderSubmission.batch_id == batch_id,
            ProviderSubmission.status == "PENDING",
        )
        .order_by(ProviderSubmission.created_at.desc())
        .first()
    )
    if not submission:
        # Check if there is already an UNKNOWN or SUBMITTED submission
        return refresh_batch_status(batch_id=batch_id, db=db, correlation_id=correlation_id)

    original_sender_batch_id = submission.sender_batch_id
    provider_code = submission.provider_code

    # 1. Investigate whether provider can establish outcome using supported functionality
    provider_result = None
    if provider_code == "PAYPAL_SANDBOX":
        provider_result = query_payout_by_sender_batch_id(original_sender_batch_id)

    if provider_result is not None and provider_result.success and provider_result.paypal_payout_batch_id:
        # Provider established outcome! Record and update
        submission.status = "SUBMITTED"
        submission.paypal_payout_batch_id = provider_result.paypal_payout_batch_id
        submission.paypal_batch_status = provider_result.paypal_batch_status
        submission.response_at = now
        active_sub = db.query(ActiveBatchSubmission).filter(ActiveBatchSubmission.batch_id == batch_id).first()
        if active_sub:
            db.delete(active_sub)
        db.commit()
        return refresh_batch_status(batch_id=batch_id, db=db, correlation_id=correlation_id)

    # 2. Outcome cannot be established: preserve uncertainty, transition to UNKNOWN
    err_msg = (
        f"STRANDED_PENDING_RECOVERED: Process crashed while submission was PENDING. "
        f"Provider {provider_code} cannot confirm receipt using sender_batch_id={original_sender_batch_id!r}. "
        "Outcome is uncertain. Preserved original submission in UNKNOWN state pending manual reconciliation."
    )
    submission.status = "UNKNOWN"
    submission.error_message = err_msg
    submission.response_at = now

    batch.status = "UNKNOWN"

    instructions = db.query(PaymentInstruction).filter(PaymentInstruction.batch_id == batch_id).all()
    for instr in instructions:
        instr.status = "UNKNOWN"
        instr.updated_at = now

    # Remove active lock so system is not stuck in a crashed lock, while UNKNOWN status blocks resubmission
    active_sub = db.query(ActiveBatchSubmission).filter(ActiveBatchSubmission.batch_id == batch_id).first()
    if active_sub:
        db.delete(active_sub)

    # Record hash-chained audit event
    record_audit_event(
        db=db,
        entity_type="BATCH",
        entity_id=batch_id,
        event_type="STRANDED_SUBMISSION_RECOVERED",
        actor="SYSTEM",
        correlation_id=correlation_id,
        details_redacted=json.dumps({
            "batch_id": batch_id,
            "submission_id": submission.id,
            "sender_batch_id": original_sender_batch_id,
            "provider_code": provider_code,
            "previous_status": "PENDING",
            "new_status": "UNKNOWN",
            "reason": "Process crash detected before Transaction 2 completed",
        }),
    )
    db.commit()

    return StatusRefreshResult(
        success=False,
        batch_id=batch_id,
        batch_status="UNKNOWN",
        paypal_batch_status=None,
        items_checked=len(instructions),
        completed=0,
        failed=0,
        pending=0,
        unknown=len(instructions),
        refreshed_at=now.isoformat(),
        error_message=err_msg,
        disclaimer=_disclaimer(),
    )


def resolve_unresolved_submission(
    batch_id: str,
    resolution: str,
    db: Session,
    confirmed_payout_batch_id: Optional[str] = None,
    operator_id: str = "FINANCE_OPERATOR",
    notes: Optional[str] = None,
    correlation_id: Optional[str] = None,
) -> StatusRefreshResult:
    """
    Documented, controlled method for handling a submission that was committed but
    whose outcome required manual human investigation (Priority 1.1 — Issue 1, Requirement 9).

    Supported resolutions:
      - 'CONFIRM_NEVER_SENT':
          Operator verified via provider dashboard / direct bank logs that PayPal / provider
          never received the payout request. Marks the stranded submission as FAILED (with note),
          resets batch to 'APPROVED' (or instructions to 'APPROVED') so it can be safely re-evaluated
          or re-submitted under human supervision.
      - 'CONFIRM_SUBMITTED':
          Operator verified via provider dashboard that the payout WAS accepted, and provides
          confirmed_payout_batch_id. Links the provider ID, marks submission 'SUBMITTED', and
          refreshes status from provider.
    """
    now = datetime.now(timezone.utc)
    batch = db.query(PaymentBatch).filter(PaymentBatch.id == batch_id).first()
    if not batch:
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
    if not submission:
        return StatusRefreshResult(
            success=False, batch_id=batch_id, batch_status=batch.status,
            paypal_batch_status=None, items_checked=0, completed=0,
            failed=0, pending=0, unknown=0, refreshed_at=now.isoformat(),
            error_message="No submission record found for batch.", disclaimer=_disclaimer(),
        )

    if resolution == "CONFIRM_NEVER_SENT":
        submission.status = "FAILED"
        submission.error_message = (
            f"MANUALLY_RESOLVED_NEVER_SENT by {operator_id}: "
            f"{notes or 'Confirmed provider never received payout.'}"
        )
        submission.response_at = now
        batch.status = "APPROVED"
        instructions = db.query(PaymentInstruction).filter(PaymentInstruction.batch_id == batch_id).all()
        for instr in instructions:
            instr.status = "APPROVED"
            instr.updated_at = now

        active_sub = db.query(ActiveBatchSubmission).filter(ActiveBatchSubmission.batch_id == batch_id).first()
        if active_sub:
            db.delete(active_sub)

        record_audit_event(
            db=db,
            entity_type="BATCH",
            entity_id=batch_id,
            event_type="MANUAL_RECONCILIATION_RESOLVED",
            actor=operator_id,
            correlation_id=correlation_id,
            details_redacted=json.dumps({
                "resolution": "CONFIRM_NEVER_SENT",
                "operator_id": operator_id,
                "notes": notes,
                "batch_id": batch_id,
                "sender_batch_id": submission.sender_batch_id,
            }),
        )
        db.commit()

        return StatusRefreshResult(
            success=True,
            batch_id=batch_id,
            batch_status="APPROVED",
            paypal_batch_status=None,
            items_checked=len(instructions),
            completed=0,
            failed=0,
            pending=0,
            unknown=0,
            refreshed_at=now.isoformat(),
            error_message=None,
            disclaimer=_disclaimer(),
        )

    elif resolution == "CONFIRM_SUBMITTED":
        if not confirmed_payout_batch_id:
            return StatusRefreshResult(
                success=False, batch_id=batch_id, batch_status=batch.status,
                paypal_batch_status=None, items_checked=0, completed=0,
                failed=0, pending=0, unknown=0, refreshed_at=now.isoformat(),
                error_message="confirmed_payout_batch_id is required for CONFIRM_SUBMITTED resolution.",
                disclaimer=_disclaimer(),
            )
        submission.paypal_payout_batch_id = confirmed_payout_batch_id
        submission.status = "SUBMITTED"
        submission.response_at = now

        active_sub = db.query(ActiveBatchSubmission).filter(ActiveBatchSubmission.batch_id == batch_id).first()
        if active_sub:
            db.delete(active_sub)

        record_audit_event(
            db=db,
            entity_type="BATCH",
            entity_id=batch_id,
            event_type="MANUAL_RECONCILIATION_RESOLVED",
            actor=operator_id,
            correlation_id=correlation_id,
            details_redacted=json.dumps({
                "resolution": "CONFIRM_SUBMITTED",
                "operator_id": operator_id,
                "confirmed_payout_batch_id": confirmed_payout_batch_id,
                "notes": notes,
                "sender_batch_id": submission.sender_batch_id,
            }),
        )
        db.commit()

        return refresh_batch_status(batch_id=batch_id, db=db, correlation_id=correlation_id)

    else:
        return StatusRefreshResult(
            success=False, batch_id=batch_id, batch_status=batch.status,
            paypal_batch_status=None, items_checked=0, completed=0,
            failed=0, pending=0, unknown=0, refreshed_at=now.isoformat(),
            error_message=f"Invalid resolution code: {resolution!r}. Allowed: CONFIRM_NEVER_SENT, CONFIRM_SUBMITTED",
            disclaimer=_disclaimer(),
        )


def _disclaimer() -> str:
    return (
        "SANDBOX ENVIRONMENT — No real money moves. "
        "PayPal Sandbox responses are test-only. "
        "HTTP 2xx acceptance does not confirm fund settlement."
    )


# Backwards compatibility alias
refresh_status = refresh_batch_status

