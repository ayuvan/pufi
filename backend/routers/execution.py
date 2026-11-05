"""
PUFI — Execution router (Day 4).

Endpoints:
  POST /api/v1/batches/{batch_id}/approve         — human approval
  POST /api/v1/batches/{batch_id}/submit          — PayPal Sandbox submission
  POST /api/v1/batches/{batch_id}/refresh-status  — poll PayPal for status updates
  GET  /api/v1/batches/{batch_id}/instructions    — list payment instructions
  GET  /api/v1/batches/{batch_id}/audit           — list audit events

SECURITY:
  - No PayPal credentials are returned in any response.
  - is_simulated and paypal_configured flags are always present in submission responses.
  - Approval requires explicit human action with confirmed financial values.
"""
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session, joinedload

from models.db import get_db
from models.entities import AuditEvent, Obligation, PaymentInstruction, ProviderSubmission
from schemas.execution import (
    ApproveRequest,
    ApprovalResponse,
    AuditEventOut,
    PaymentInstructionOut,
    StatusRefreshResponse,
    SubmissionResponse,
)
from services.approval import approve_batch
from services.execution_coordinator import refresh_status, submit_batch

logger = logging.getLogger("pufi.execution")

router = APIRouter()


# ===========================================================================
# POST /batches/{batch_id}/approve
# ===========================================================================

@router.post(
    "/batches/{batch_id}/approve",
    response_model=ApprovalResponse,
    summary="Approve a batch for PayPal Sandbox submission",
    description=(
        "Records explicit human approval of a batch. "
        "Requires a completed analysis (POST /analyze). "
        "Verifies confirmed_total matches obligation sum. "
        "AI recommendation is advisory only — approval is a human action."
    ),
)
def approve_batch_endpoint(
    batch_id: str,
    body: ApproveRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> ApprovalResponse:
    correlation_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))

    result = approve_batch(
        batch_id=batch_id,
        approver_id=body.approver_id,
        selected_provider=body.selected_provider,
        routing_strategy=body.routing_strategy,
        confirmed_total=body.confirmed_total,
        confirmed_currency=body.confirmed_currency,
        db=db,
        correlation_id=correlation_id,
    )

    if not result.success:
        raise HTTPException(
            status_code=422,
            detail={
                "error": result.error_code,
                "message": result.error_detail,
            },
        )

    # Commit within the endpoint (approval persists to DB)
    db.commit()

    return ApprovalResponse(
        batch_id=result.batch_id,
        status=result.status,
        approved_by=result.approved_by,
        approved_at=result.approved_at.isoformat() if result.approved_at else "",
        selected_provider=result.selected_provider,
        confirmed_total=result.confirmed_total,
        confirmed_currency=result.confirmed_currency,
        approved_recipient_count=result.approved_recipient_count,
        routing_strategy=result.routing_strategy,
        analysis_snapshot_id=result.analysis_snapshot_id,
        message="Batch approved. Submit when ready.",
    )


# ===========================================================================
# POST /batches/{batch_id}/submit
# ===========================================================================

@router.post(
    "/batches/{batch_id}/submit",
    response_model=SubmissionResponse,
    summary="Submit an APPROVED batch to PayPal Sandbox",
    description=(
        "Submits the batch to PayPal Sandbox. Requires APPROVED status. "
        "If PayPal credentials are not configured, returns is_simulated=True "
        "and paypal_configured=False. "
        "SANDBOX ONLY — no real money movement."
    ),
)
def submit_batch_endpoint(
    batch_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> SubmissionResponse:
    correlation_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))

    result = submit_batch(batch_id=batch_id, db=db, correlation_id=correlation_id)

    if not result.success and result.submission_status == "FAILED":
        # Don't rollback — ProviderSubmission record was already persisted
        # so the idempotency key is preserved for future retries
        raise HTTPException(
            status_code=422,
            detail={
                "error": "SUBMISSION_FAILED",
                "message": result.error_message,
                "is_simulated": result.is_simulated,
                "paypal_configured": result.paypal_configured,
            },
        )

    db.commit()

    return SubmissionResponse(
        batch_id=result.batch_id,
        sender_batch_id=result.sender_batch_id,
        paypal_payout_batch_id=result.paypal_payout_batch_id,
        paypal_batch_status=result.paypal_batch_status,
        submission_status=result.submission_status,
        submitted_at=result.submitted_at,
        is_simulated=result.is_simulated,
        paypal_configured=result.paypal_configured,
        disclaimer=result.disclaimer,
    )


# ===========================================================================
# POST /batches/{batch_id}/refresh-status
# ===========================================================================

@router.post(
    "/batches/{batch_id}/refresh-status",
    response_model=StatusRefreshResponse,
    summary="Refresh batch and item statuses from PayPal",
    description=(
        "Polls PayPal Sandbox for current batch and item statuses. "
        "Maps item statuses to PUFI instruction statuses. "
        "IMPORTANT: PayPal Sandbox HTTP acceptance ≠ fund settlement."
    ),
)
def refresh_status_endpoint(
    batch_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> StatusRefreshResponse:
    correlation_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))

    result = refresh_status(batch_id=batch_id, db=db, correlation_id=correlation_id)

    if not result.success:
        db.rollback()
        raise HTTPException(
            status_code=422,
            detail={
                "error": "STATUS_REFRESH_FAILED",
                "message": result.error_message,
            },
        )

    db.commit()

    return StatusRefreshResponse(
        batch_id=result.batch_id,
        batch_status=result.batch_status,
        paypal_batch_status=result.paypal_batch_status,
        items_checked=result.items_checked,
        completed=result.completed,
        failed=result.failed,
        pending=result.pending,
        unknown=result.unknown,
        refreshed_at=result.refreshed_at,
        disclaimer=result.disclaimer,
    )


# ===========================================================================
# GET /batches/{batch_id}/instructions
# ===========================================================================

@router.get(
    "/batches/{batch_id}/instructions",
    response_model=list[PaymentInstructionOut],
    summary="List payment instructions for a batch",
)
def list_instructions(
    batch_id: str,
    db: Session = Depends(get_db),
) -> list[PaymentInstructionOut]:
    instructions = (
        db.query(PaymentInstruction)
        .options(
            joinedload(PaymentInstruction.obligation).joinedload(Obligation.supplier)
        )
        .filter(PaymentInstruction.batch_id == batch_id)
        .order_by(PaymentInstruction.created_at)
        .all()
    )

    results = []
    for instr in instructions:
        ob = instr.obligation
        supplier = ob.supplier if ob else None
        masked = supplier.recipient_reference_masked if supplier else "***"
        results.append(
            PaymentInstructionOut(
                id=instr.id,
                obligation_id=instr.obligation_id,
                provider_code=instr.provider_code,
                amount=str(instr.amount),
                currency=instr.currency,
                idempotency_key=instr.idempotency_key,
                status=instr.status,
                settlement_evidence=instr.settlement_evidence,
                paypal_payout_item_id=instr.paypal_payout_item_id,
                paypal_transaction_id=instr.paypal_transaction_id,
                paypal_item_status=instr.paypal_item_status,
                error_message=instr.error_message,
                recipient_masked=masked,
                created_at=instr.created_at.isoformat(),
                updated_at=instr.updated_at.isoformat(),
            )
        )
    return results


# ===========================================================================
# GET /batches/{batch_id}/audit
# ===========================================================================

@router.get(
    "/batches/{batch_id}/audit",
    response_model=list[AuditEventOut],
    summary="List audit events for a batch",
)
def list_audit_events(
    batch_id: str,
    db: Session = Depends(get_db),
) -> list[AuditEventOut]:
    events = (
        db.query(AuditEvent)
        .filter(
            AuditEvent.entity_type == "BATCH",
            AuditEvent.entity_id == batch_id,
        )
        .order_by(AuditEvent.created_at)
        .all()
    )
    return [
        AuditEventOut(
            id=ev.id,
            entity_type=ev.entity_type,
            entity_id=ev.entity_id,
            event_type=ev.event_type,
            actor=ev.actor,
            correlation_id=ev.correlation_id,
            details_redacted=ev.details_redacted,
            created_at=ev.created_at.isoformat(),
        )
        for ev in events
    ]
