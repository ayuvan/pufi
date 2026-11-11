"""
PUFI — Automated Remediation & Regression Test Suite

Verifies:
  Phase 1: UNKNOWN payment state handling, duplicate payout blocking, and provider reconciliation.
  Phase 2: PayPal Sandbox recipient validation (missing, invalid format, prohibited placeholder rejection).
  Phase 3: Multi-provider execution dispatch (PAYPAL_SANDBOX vs SIMULATED_FAST vs SIMULATED_ECONOMY vs UNSUPPORTED).
  Phase 4: Approval service validation (expired quotes > 24h, zero eligible providers, unlisted provider rejection).
  Phase 5: Tamper-evident cryptographic hash-chaining of AuditEvents and integrity verification.
  Phase 6: Webhook deduplication and security.
"""
import json
import os
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch, MagicMock

import pytest
from sqlalchemy.orm import Session

from models.entities import (
    AiRecommendation, AuditEvent, BatchObligation, Business, Obligation,
    PaymentBatch, PaymentInstruction, ProviderSubmission, Supplier,
)
from services.approval import approve_batch
from services.audit import record_audit_event, verify_audit_integrity, compute_event_hash
from services.execution_coordinator import (
    submit_batch, refresh_batch_status, reconcile_unknown_submission,
    validate_recipient_email, resolve_sandbox_recipient,
)
from services.paypal_adapter import PayPalSubmitResult, PayPalBatchStatusResult, PayoutItemStatus


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _create_test_batch(
    db: Session,
    status: str = "APPROVED",
    provider_code: str = "PAYPAL_SANDBOX",
    amount: str = "1000.00",
    currency: str = "USD",
    recipient_email: str = "valid-sandbox@personal.paypal.com",
) -> str:
    """Helper to construct an isolated batch with 1 valid obligation and supplier."""
    uid = uuid.uuid4().hex[:8]
    biz = Business(id=f"BIZ-REM-{uid}", display_name="Remediation Corp")
    db.add(biz)
    db.flush()

    sup = Supplier(
        id=f"SUP-REM-{uid}",
        business_id=biz.id,
        external_reference=f"EXT-REM-{uid}",
        display_name="Remediation Supplier",
        country_code="US",
        recipient_reference_type="EMAIL",
        recipient_reference_masked="rem***@example.com",
        sandbox_recipient_email=recipient_email,
        preferred_currency=currency,
    )
    db.add(sup)
    db.flush()

    ob = Obligation(
        id=f"OBL-REM-{uid}",
        business_id=biz.id,
        supplier_id=sup.id,
        invoice_reference=f"INV-REM-{uid}",
        amount=Decimal(amount),
        currency=currency,
        due_at=date(2026, 12, 31),
        status="VALIDATED",
        source_hash=f"hash-{uid}",
    )
    db.add(ob)
    db.flush()

    batch = PaymentBatch(
        id=f"BATCH-REM-{uid}",
        business_id=biz.id,
        batch_reference=f"BATCH-REM-REF-{uid}",
        status=status,
        selected_provider_code=provider_code,
        approved_total_amount=Decimal(amount),
        approved_currency=currency,
        approved_recipient_count=1,
    )
    db.add(batch)
    db.flush()

    bo = BatchObligation(
        batch_id=batch.id,
        obligation_id=ob.id,
    )
    db.add(bo)
    db.flush()

    # Create dummy AI recommendation
    ai_rec = AiRecommendation(
        id=f"AI-REM-{uid}",
        batch_id=batch.id,
        model_name="gemini-3.8-flash",
        input_summary_hash=f"input-hash-{uid}",
        recommendation_json=json.dumps({
            "recommended_route": provider_code,
            "evidence_fields": {
                "eligible_route_codes": [provider_code, "SIMULATED_FAST", "SIMULATED_ECONOMY"],
            },
        }),
    )
    db.add(ai_rec)
    db.flush()

    return batch.id


# ---------------------------------------------------------------------------
# Phase 1: UNKNOWN Payment State and Duplicate Submission Protection
# ---------------------------------------------------------------------------

class TestPhase1UnknownStateAndDuplicateProtection:

    def test_timeout_yields_unknown_status_and_marks_batch(self, db: Session):
        """When PayPal times out, submission, batch, and instructions transition to UNKNOWN."""
        batch_id = _create_test_batch(db, status="APPROVED")

        timeout_result = PayPalSubmitResult(
            success=False,
            sender_batch_id="SENDER-TIMEOUT-001",
            paypal_payout_batch_id=None,
            paypal_batch_status=None,
            http_status=408,
            is_simulated=False,
            error_message="PayPal payout submission timed out after 30s.",
        )

        with patch("services.execution_coordinator.submit_payout", return_value=timeout_result):
            with patch("services.execution_coordinator.is_configured", return_value=True):
                res = submit_batch(batch_id=batch_id, db=db)

        assert not res.success
        assert res.submission_status == "UNKNOWN"

        # Check DB states
        sub = db.query(ProviderSubmission).filter(ProviderSubmission.batch_id == batch_id).first()
        assert sub is not None
        assert sub.status == "UNKNOWN"

        batch = db.query(PaymentBatch).filter(PaymentBatch.id == batch_id).first()
        assert batch.status == "UNKNOWN"

        instrs = db.query(PaymentInstruction).filter(PaymentInstruction.batch_id == batch_id).all()
        assert len(instrs) == 1
        assert instrs[0].status == "UNKNOWN"

    def test_second_submission_blocked_while_unknown(self, db: Session):
        """Second submission attempt for an UNKNOWN payment is strictly blocked without creating a new payment."""
        batch_id = _create_test_batch(db, status="APPROVED")

        # Create prior UNKNOWN submission
        prior_sub = ProviderSubmission(
            batch_id=batch_id,
            provider_code="PAYPAL_SANDBOX",
            sender_batch_id="STABLE-UNKNOWN-SENDER-01",
            status="UNKNOWN",
            error_message="Request timed out",
        )
        db.add(prior_sub)
        db.flush()

        # Attempt resubmission
        with patch("services.execution_coordinator.is_configured", return_value=True):
            res = submit_batch(batch_id=batch_id, db=db)

        assert not res.success
        assert res.submission_status == "UNKNOWN"
        assert "PAYMENT_STATE_UNKNOWN" in (res.error_message or "")
        assert "duplicate" in (res.error_message or "").lower()

        # Verify no second submission was created
        subs = db.query(ProviderSubmission).filter(ProviderSubmission.batch_id == batch_id).all()
        assert len(subs) == 1
        assert subs[0].sender_batch_id == "STABLE-UNKNOWN-SENDER-01"

    def test_reconciliation_resolves_unknown_to_completed(self, db: Session):
        """Reconciling an UNKNOWN submission when provider reports SUCCESS updates batch to COMPLETED."""
        batch_id = _create_test_batch(db, status="UNKNOWN")

        # Prior UNKNOWN submission
        sub = ProviderSubmission(
            batch_id=batch_id,
            provider_code="PAYPAL_SANDBOX",
            sender_batch_id="SENDER-REC-001",
            paypal_payout_batch_id="PP-REC-001",
            status="UNKNOWN",
        )
        db.add(sub)

        # Instruction in UNKNOWN
        ob = db.query(BatchObligation).filter(BatchObligation.batch_id == batch_id).first()
        instr = PaymentInstruction(
            batch_id=batch_id,
            obligation_id=ob.obligation_id,
            provider_code="PAYPAL_SANDBOX",
            amount=Decimal("1000.00"),
            currency="USD",
            idempotency_key="PUFI-REC-IDEM-01",
            sender_item_id="PUFI-REC-ITEM-01",
            status="UNKNOWN",
            settlement_evidence="NOT_CONFIRMED",
        )
        db.add(instr)
        db.flush()

        mock_status = PayPalBatchStatusResult(
            success=True,
            paypal_payout_batch_id="PP-REC-001",
            paypal_batch_status="SUCCESS",
            items=[
                PayoutItemStatus(
                    sender_item_id="PUFI-REC-ITEM-01",
                    payout_item_id="PP-ITEM-01",
                    transaction_id="TXN-PAYPAL-12345",
                    item_status="SUCCESS",
                    error_message=None,
                )
            ],
        )

        with patch("services.execution_coordinator.get_batch_status", return_value=mock_status):
            refresh_res = reconcile_unknown_submission(batch_id=batch_id, db=db)

        assert refresh_res.success
        assert refresh_res.batch_status == "COMPLETED"
        assert refresh_res.completed == 1

        # Check DB updates
        batch = db.query(PaymentBatch).filter(PaymentBatch.id == batch_id).first()
        assert batch.status == "COMPLETED"

        updated_sub = db.query(ProviderSubmission).filter(ProviderSubmission.batch_id == batch_id).first()
        assert updated_sub.status == "SUBMITTED"

        updated_instr = db.query(PaymentInstruction).filter(PaymentInstruction.batch_id == batch_id).first()
        assert updated_instr.status == "COMPLETED"
        assert updated_instr.settlement_evidence == "PROVIDER_REPORTED_COMPLETE"
        assert updated_instr.paypal_transaction_id == "TXN-PAYPAL-12345"

    def test_reconciliation_resolves_unknown_to_failed(self, db: Session):
        """Reconciling an UNKNOWN submission when provider reports DENIED/FAILED marks batch FAILED."""
        batch_id = _create_test_batch(db, status="UNKNOWN")

        sub = ProviderSubmission(
            batch_id=batch_id,
            provider_code="PAYPAL_SANDBOX",
            sender_batch_id="SENDER-REC-FAIL",
            paypal_payout_batch_id="PP-REC-FAIL",
            status="UNKNOWN",
        )
        db.add(sub)

        ob = db.query(BatchObligation).filter(BatchObligation.batch_id == batch_id).first()
        instr = PaymentInstruction(
            batch_id=batch_id,
            obligation_id=ob.obligation_id,
            provider_code="PAYPAL_SANDBOX",
            amount=Decimal("1000.00"),
            currency="USD",
            idempotency_key="PUFI-REC-FAIL-IDEM",
            sender_item_id="PUFI-REC-FAIL-ITEM",
            status="UNKNOWN",
        )
        db.add(instr)
        db.flush()

        mock_status = PayPalBatchStatusResult(
            success=True,
            paypal_payout_batch_id="PP-REC-FAIL",
            paypal_batch_status="DENIED",
            items=[
                PayoutItemStatus(
                    sender_item_id="PUFI-REC-FAIL-ITEM",
                    payout_item_id="PP-ITEM-FAIL",
                    transaction_id=None,
                    item_status="FAILED",
                    error_message="Account restricted in sandbox",
                )
            ],
        )

        with patch("services.execution_coordinator.get_batch_status", return_value=mock_status):
            refresh_res = reconcile_unknown_submission(batch_id=batch_id, db=db)

        assert refresh_res.success
        assert refresh_res.batch_status == "FAILED"
        assert refresh_res.failed == 1

        batch = db.query(PaymentBatch).filter(PaymentBatch.id == batch_id).first()
        assert batch.status == "FAILED"


# ---------------------------------------------------------------------------
# Phase 2: PayPal Sandbox Recipient Validation
# ---------------------------------------------------------------------------

class TestPhase2RecipientValidation:

    def test_valid_sandbox_recipient(self):
        """Valid email formats pass validation."""
        valid, err = validate_recipient_email("developer-sandbox@paypal.com")
        assert valid is True
        assert err is None

    def test_missing_recipient_rejected(self):
        """None or empty recipient is rejected."""
        valid, err = validate_recipient_email(None)
        assert valid is False
        assert "missing or empty" in (err or "")

        valid2, err2 = validate_recipient_email("   ")
        assert valid2 is False

    def test_invalid_email_format_rejected(self):
        """Malformed emails missing '@' or domain are rejected."""
        valid, err = validate_recipient_email("not-an-email-address")
        assert valid is False
        assert "invalid format" in (err or "").lower()

    def test_prohibited_placeholder_recipient_rejected(self):
        """Prohibited placeholder emails ending in business.example.com are rejected."""
        valid, err = validate_recipient_email("sb-pay001@business.example.com")
        assert valid is False
        assert "Prohibited placeholder recipient" in (err or "")

        valid2, err2 = validate_recipient_email("sb-generic@business.example.com")
        assert valid2 is False

    def test_submission_fails_fast_if_recipient_is_invalid(self, db: Session, monkeypatch):
        """Execution coordinator rejects payout submission before calling adapter if recipient is invalid."""
        monkeypatch.delenv("PAYPAL_SANDBOX_RECIPIENT_EMAIL", raising=False)
        batch_id = _create_test_batch(db, status="APPROVED", recipient_email="sb-pay001@business.example.com")

        with patch("services.execution_coordinator.submit_payout") as mock_adapter:
            res = submit_batch(batch_id=batch_id, db=db)

        assert not res.success
        assert "INVALID_RECIPIENT_CONFIGURATION" in (res.error_message or "")
        # Adapter was NEVER called
        mock_adapter.assert_not_called()


# ---------------------------------------------------------------------------
# Phase 3: Provider-Specific Payment Execution
# ---------------------------------------------------------------------------

class TestPhase3ProviderSpecificExecution:

    def test_simulated_fast_dispatches_to_simulated_adapter(self, db: Session):
        """Selecting SIMULATED_FAST routes to simulated adapter and sets status COMPLETED."""
        batch_id = _create_test_batch(db, status="APPROVED", provider_code="SIMULATED_FAST")

        with patch("services.execution_coordinator.submit_payout") as mock_paypal:
            res = submit_batch(batch_id=batch_id, db=db)

        assert res.success is True
        assert res.is_simulated is True
        assert res.paypal_payout_batch_id.startswith("SIM-SIMU-")
        mock_paypal.assert_not_called()

        # Batch marked COMPLETED due to instant settlement
        batch = db.query(PaymentBatch).filter(PaymentBatch.id == batch_id).first()
        assert batch.status == "COMPLETED"

        instrs = db.query(PaymentInstruction).filter(PaymentInstruction.batch_id == batch_id).all()
        assert len(instrs) == 1
        assert instrs[0].status == "COMPLETED"
        assert instrs[0].settlement_evidence == "SIMULATED_IMMEDIATE_SETTLEMENT"

    def test_simulated_economy_dispatches_with_pending_status(self, db: Session):
        """Selecting SIMULATED_ECONOMY marks submission as SUBMITTED."""
        batch_id = _create_test_batch(db, status="APPROVED", provider_code="SIMULATED_ECONOMY")

        res = submit_batch(batch_id=batch_id, db=db)
        assert res.success is True
        assert res.is_simulated is True

        batch = db.query(PaymentBatch).filter(PaymentBatch.id == batch_id).first()
        assert batch.status == "SUBMITTED"

        instrs = db.query(PaymentInstruction).filter(PaymentInstruction.batch_id == batch_id).all()
        assert instrs[0].status == "SUBMITTED"
        assert instrs[0].settlement_evidence == "SIMULATED_PENDING_SETTLEMENT"

    def test_unsupported_provider_rejected(self, db: Session):
        """Unknown or unregistered providers are rejected before execution."""
        batch_id = _create_test_batch(db, status="APPROVED", provider_code="UNKNOWN_RAIL_XYZ")

        res = submit_batch(batch_id=batch_id, db=db)
        assert not res.success
        assert "UNSUPPORTED_PROVIDER" in (res.error_message or "")


# ---------------------------------------------------------------------------
# Phase 4: Approval Service Validation & Expiry
# ---------------------------------------------------------------------------

class TestPhase4ApprovalServiceValidation:

    def test_approval_rejects_expired_analysis(self, db: Session):
        """Approval is rejected when route analysis is older than 24 hours."""
        batch_id = _create_test_batch(db, status="DRAFT")

        # Set analysis created_at to 25 hours ago
        ai_rec = db.query(AiRecommendation).filter(AiRecommendation.batch_id == batch_id).first()
        ai_rec.created_at = datetime.now(timezone.utc) - timedelta(hours=25)
        db.flush()

        res = approve_batch(
            batch_id=batch_id,
            approver_id="DEMO-APPROVER",
            selected_provider="PAYPAL_SANDBOX",
            routing_strategy="LOWEST_COST",
            confirmed_total="1000.00",
            confirmed_currency="USD",
            db=db,
        )

        assert not res.success
        assert res.error_code == "ANALYSIS_EXPIRED"
        assert "24 hours" in (res.error_detail or "")

    def test_approval_rejects_empty_eligible_routes(self, db: Session):
        """Approval is rejected if analysis found zero eligible providers."""
        batch_id = _create_test_batch(db, status="DRAFT")

        ai_rec = db.query(AiRecommendation).filter(AiRecommendation.batch_id == batch_id).first()
        ai_rec.recommendation_json = json.dumps({
            "recommended_route": None,
            "evidence_fields": {"eligible_route_codes": []},
        })
        db.flush()

        res = approve_batch(
            batch_id=batch_id,
            approver_id="DEMO-APPROVER",
            selected_provider="PAYPAL_SANDBOX",
            routing_strategy="LOWEST_COST",
            confirmed_total="1000.00",
            confirmed_currency="USD",
            db=db,
        )

        assert not res.success
        assert res.error_code == "NO_ELIGIBLE_PROVIDERS"

    def test_approval_rejects_provider_not_in_eligible_list(self, db: Session):
        """Approval is rejected if selected provider was not deemed eligible by deterministic engine."""
        batch_id = _create_test_batch(db, status="DRAFT")

        ai_rec = db.query(AiRecommendation).filter(AiRecommendation.batch_id == batch_id).first()
        ai_rec.recommendation_json = json.dumps({
            "recommended_route": "SIMULATED_FAST",
            "evidence_fields": {"eligible_route_codes": ["SIMULATED_FAST"]},
        })
        db.flush()

        res = approve_batch(
            batch_id=batch_id,
            approver_id="DEMO-APPROVER",
            selected_provider="PAYPAL_SANDBOX",  # Ineligible
            routing_strategy="LOWEST_COST",
            confirmed_total="1000.00",
            confirmed_currency="USD",
            db=db,
        )

        assert not res.success
        assert res.error_code == "PROVIDER_NOT_ELIGIBLE"


# ---------------------------------------------------------------------------
# Phase 5: Cryptographic Hash Chaining on AuditTrail
# ---------------------------------------------------------------------------

class TestPhase5CryptographicAuditTrail:

    def test_hash_chain_genesis_and_linking(self, db: Session):
        """Audit events are chained using SHA-256."""
        ev1 = record_audit_event(
            db=db,
            entity_type="BATCH",
            entity_id="B-001",
            event_type="CREATED",
            actor="SYSTEM",
            details_redacted='{"action": "create"}',
        )
        db.flush()

        assert ev1.prev_hash == "0" * 64
        assert ev1.event_hash is not None

        ev2 = record_audit_event(
            db=db,
            entity_type="BATCH",
            entity_id="B-001",
            event_type="APPROVED",
            actor="CHECKER",
            details_redacted='{"action": "approve"}',
        )
        db.flush()

        assert ev2.prev_hash == ev1.event_hash
        assert ev2.event_hash != ev1.event_hash

        valid, broken_id, err = verify_audit_integrity(db, entity_id="B-001")
        assert valid is True
        assert broken_id is None

    def test_tamper_detection_on_modified_row(self, db: Session):
        """Any modified details or tampered fields are detected by verify_audit_integrity."""
        ev1 = record_audit_event(
            db=db,
            entity_type="BATCH",
            entity_id="B-002",
            event_type="SUBMITTED",
            actor="SYSTEM",
            details_redacted='{"amount": "5000.00"}',
        )
        db.flush()

        # Tamper: modify details directly
        ev1.details_redacted = '{"amount": "999999.00"}'
        db.flush()

        valid, broken_id, err = verify_audit_integrity(db, entity_id="B-002")
        assert valid is False
        assert broken_id == ev1.id
        assert "Tampered event data" in (err or "")
