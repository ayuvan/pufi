"""
PUFI — Pydantic schemas for Day 4 approval, submission, and execution tracking.

Design rules:
  - Monetary amounts are strings to preserve Decimal precision.
  - is_simulated / paypal_configured flags must always be present in
    submission responses so the UI can display correct labels.
  - No internal DB column names or ORM types leak here.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ===========================================================================
# Approval
# ===========================================================================

class ApproveRequest(BaseModel):
    """
    Request body for POST /batches/{batch_id}/approve.

    The confirmed_total and confirmed_currency must match the values in the
    most recent analysis snapshot; mismatches are rejected to prevent
    approval of a batch that has changed since analysis.
    """
    approver_id: str = Field(..., description="Approver identifier (e.g. 'DEMO_USER')")
    selected_provider: str = Field(
        ...,
        description="Provider code from eligible routes (e.g. 'PAYPAL_SANDBOX')",
    )
    routing_strategy: str = Field(
        ...,
        description="Strategy used: LOWEST_COST | FASTEST | BALANCED",
    )
    confirmed_total: str = Field(
        ...,
        description="Total obligation amount as a string (must match analysis snapshot)",
    )
    confirmed_currency: str = Field(
        ...,
        description="Currency code (e.g. 'USD')",
    )


class ApprovalResponse(BaseModel):
    """Response from POST /batches/{batch_id}/approve."""
    batch_id: str
    status: str
    approved_by: str
    approved_at: str
    selected_provider: str
    confirmed_total: str
    confirmed_currency: str
    approved_recipient_count: int
    routing_strategy: str
    analysis_snapshot_id: Optional[str]
    message: str


# ===========================================================================
# Submission
# ===========================================================================

class SubmissionResponse(BaseModel):
    """Response from POST /batches/{batch_id}/submit."""
    batch_id: str
    sender_batch_id: str
    paypal_payout_batch_id: Optional[str] = None
    paypal_batch_status: Optional[str] = None
    submission_status: str   # SUBMITTED | FAILED | UNKNOWN
    submitted_at: str
    is_simulated: bool       # False for a real PayPal Sandbox call
    paypal_configured: bool
    disclaimer: str


# ===========================================================================
# Status refresh
# ===========================================================================

class StatusRefreshResponse(BaseModel):
    """Response from POST /batches/{batch_id}/refresh-status."""
    batch_id: str
    batch_status: str
    paypal_batch_status: Optional[str] = None
    items_checked: int
    completed: int
    failed: int
    pending: int
    unknown: int
    refreshed_at: str
    disclaimer: str


# ===========================================================================
# Payment instruction detail
# ===========================================================================

class PaymentInstructionOut(BaseModel):
    """One payment instruction as returned by GET /batches/{batch_id}/instructions."""
    id: str
    obligation_id: str
    provider_code: str
    amount: str                   # Decimal string
    currency: str
    idempotency_key: str
    status: str
    settlement_evidence: str
    paypal_payout_item_id: Optional[str] = None
    paypal_transaction_id: Optional[str] = None
    paypal_item_status: Optional[str] = None
    error_message: Optional[str] = None
    recipient_masked: str         # masked reference from supplier
    created_at: str
    updated_at: str


# ===========================================================================
# Audit event
# ===========================================================================

class AuditEventOut(BaseModel):
    """One audit event as returned by GET /batches/{batch_id}/audit."""
    id: str
    entity_type: str
    entity_id: str
    event_type: str
    actor: str
    correlation_id: Optional[str] = None
    details_redacted: Optional[str] = None
    created_at: str
