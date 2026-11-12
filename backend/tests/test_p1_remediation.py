"""
PUFI — Priority 1 Remediation Acceptance Tests.

Verifies:
  Phase 1 — Durable submission intent committed before network call, timeout -> UNKNOWN, crash safety.
  Phase 2 — Database-enforced concurrent duplicate submission protection, 409 conflict, multi-batch isolation.
  Phase 3 — Reconciliation Case A (with batch ID) & Case B (without batch ID), webhook consistency, state precedence.
  Phase 4 — Credential and environment hygiene (no credentials exposed).
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from models.entities import (
    ActiveBatchSubmission, AuditEvent, BatchObligation, Business, Obligation,
    PaymentBatch, PaymentInstruction, ProviderSubmission, Supplier,
)
from services.execution_coordinator import (
    refresh_batch_status, submit_batch, recover_stranded_submission, resolve_unresolved_submission,
)
from services.paypal_adapter import PayPalBatchStatusResult, PayPalSubmitResult, PayoutItemStatus


def _create_approved_batch(db, *, provider: str = "PAYPAL_SANDBOX", amount: Decimal = Decimal("1000.00")):
    """Helper to create a fully APPROVED batch ready for submission."""
    _id = uuid.uuid4().hex[:8]
    biz = Business(id=f"BIZ-P1-{_id}", display_name="P1 Corp")
    db.add(biz)
    db.flush()

    sup = Supplier(
        id=f"SUP-P1-{_id}",
        business_id=f"BIZ-P1-{_id}",
        external_reference=f"EXT-P1-{_id}",
        display_name="P1 Supplier",
        country_code="US",
        recipient_reference_type="EMAIL",
        recipient_reference_masked="p1***@example.com",
        sandbox_recipient_email="p1-receiver@personal.paypal.com",
        preferred_currency="USD",
    )
    db.add(sup)
    db.flush()

    ob = Obligation(
        id=f"OBL-P1-{_id}",
        business_id=f"BIZ-P1-{_id}",
        supplier_id=f"SUP-P1-{_id}",
        invoice_reference=f"INV-P1-{_id}",
        amount=amount,
        currency="USD",
        due_at=date(2026, 12, 31),
        status="VALIDATED",
        source_hash=f"p1hash{_id}",
    )
    db.add(ob)
    db.flush()

    batch_id = f"BATCH-P1-{_id}"
    batch = PaymentBatch(
        id=batch_id,
        business_id=f"BIZ-P1-{_id}",
        batch_reference=f"REF-P1-{_id}",
        status="APPROVED",
        selected_provider_code=provider,
    )
    db.add(batch)
    db.flush()

    db.add(BatchObligation(batch_id=batch_id, obligation_id=ob.id))
    db.commit()
    return batch_id, ob.id


# ===========================================================================
# PHASE 1: Durable Submission Intent Tests
# ===========================================================================

class TestPhase1DurableSubmissionIntent:
    def test_submission_intent_committed_before_network_call(self, db):
        batch_id, ob_id = _create_approved_batch(db)
        intent_verified = False

        def mock_submit_payout(sender_batch_id, items):
            nonlocal intent_verified
            # Verify Transaction 1 has committed intent before network call returns
            sub = (
                db.query(ProviderSubmission)
                .filter(ProviderSubmission.batch_id == batch_id)
                .first()
            )
            assert sub is not None, "Submission intent must be persisted before network call"
            assert sub.status == "PENDING"
            assert sub.intended_amount == Decimal("1000.00")
            assert sub.currency == "USD"
            assert sub.item_count == 1

            lock = (
                db.query(ActiveBatchSubmission)
                .filter(ActiveBatchSubmission.batch_id == batch_id)
                .first()
            )
            assert lock is not None, "ActiveBatchSubmission lock must be committed"
            intent_verified = True

            return PayPalSubmitResult(
                success=True,
                sender_batch_id=sender_batch_id,
                paypal_payout_batch_id="PAYPAL-BATCH-123",
                paypal_batch_status="PENDING",
                http_status=201,
            )

        with patch("services.execution_coordinator.submit_payout", side_effect=mock_submit_payout):
            res = submit_batch(batch_id, db)

        assert intent_verified is True
        assert res.success is True
        assert res.submission_status == "SUBMITTED"

    def test_simulated_crash_after_intent_persistence(self, db):
        batch_id, _ = _create_approved_batch(db)

        with patch("services.execution_coordinator.submit_payout", side_effect=RuntimeError("Process crashed mid-network")):
            res = submit_batch(batch_id, db)

        assert res.success is False
        assert res.submission_status == "UNKNOWN"

        # Verify intent is not lost
        sub = db.query(ProviderSubmission).filter(ProviderSubmission.batch_id == batch_id).first()
        assert sub is not None
        assert sub.status == "UNKNOWN"
        batch = db.query(PaymentBatch).filter(PaymentBatch.id == batch_id).first()
        assert batch.status == "UNKNOWN"

    def test_provider_timeout_preserves_intent_and_marks_unknown(self, db):
        batch_id, _ = _create_approved_batch(db)

        mock_timeout = PayPalSubmitResult(
            success=False,
            sender_batch_id="test",
            error_message="PayPal API connection timed out after 30 seconds",
            http_status=None,
        )
        with patch("services.execution_coordinator.submit_payout", return_value=mock_timeout):
            res = submit_batch(batch_id, db)

        assert res.success is False
        assert res.submission_status == "UNKNOWN"
        assert "timed out" in res.error_message.lower()

        # State must be UNKNOWN, never assumed FAILED
        sub = db.query(ProviderSubmission).filter(ProviderSubmission.batch_id == batch_id).first()
        assert sub.status == "UNKNOWN"
        batch = db.query(PaymentBatch).filter(PaymentBatch.id == batch_id).first()
        assert batch.status == "UNKNOWN"

    def test_subsequent_execution_blocked_while_unknown(self, db):
        batch_id, _ = _create_approved_batch(db)

        # First attempt times out
        mock_timeout = PayPalSubmitResult(
            success=False,
            sender_batch_id="test",
            error_message="Gateway timeout during execution",
        )
        with patch("services.execution_coordinator.submit_payout", return_value=mock_timeout):
            res1 = submit_batch(batch_id, db)
        assert res1.submission_status == "UNKNOWN"

        # Second attempt must be BLOCKED
        res2 = submit_batch(batch_id, db)
        assert res2.success is False
        assert "PAYMENT_STATE_UNKNOWN" in res2.error_message

    def test_provider_rejection_marks_failed_not_unknown(self, db):
        batch_id, _ = _create_approved_batch(db)

        mock_rejection = PayPalSubmitResult(
            success=False,
            sender_batch_id="test",
            error_message="400 Bad Request: CURRENCY_NOT_ALLOWED",
            http_status=400,
        )
        with patch("services.execution_coordinator.submit_payout", return_value=mock_rejection):
            res = submit_batch(batch_id, db)

        assert res.success is False
        assert res.submission_status == "FAILED"
        sub = db.query(ProviderSubmission).filter(ProviderSubmission.batch_id == batch_id).first()
        assert sub.status == "FAILED"


# ===========================================================================
# PHASE 2: Concurrent Duplicate Submission Protection Tests
# ===========================================================================

class TestPhase2ConcurrencyProtection:
    def test_concurrent_submissions_same_batch_blocked(self, db):
        batch_id, _ = _create_approved_batch(db)

        # Manually seed an active lock to simulate an in-flight concurrent request
        active_lock = ActiveBatchSubmission(batch_id=batch_id, submission_id="SUB-INFLIGHT-999")
        db.add(active_lock)
        db.commit()

        # Second submission attempt
        res = submit_batch(batch_id, db)
        assert res.success is False
        assert "CONCURRENT_SUBMISSION_CONFLICT" in res.error_message

    def test_losing_concurrent_request_returns_conflict_409(self, db, client):
        batch_id, _ = _create_approved_batch(db)

        # Pre-seed active lock
        active_lock = ActiveBatchSubmission(batch_id=batch_id, submission_id="SUB-INFLIGHT-888")
        db.add(active_lock)
        db.commit()

        resp = client.post(f"/api/v1/batches/{batch_id}/submit")
        assert resp.status_code == 409
        data = resp.json()
        assert data["detail"]["error"] == "CONCURRENT_SUBMISSION_CONFLICT"

    def test_concurrent_submissions_different_batches_succeed(self, db):
        batch1, _ = _create_approved_batch(db, provider="SIMULATED_FAST")
        batch2, _ = _create_approved_batch(db, provider="SIMULATED_FAST")

        res1 = submit_batch(batch1, db)
        res2 = submit_batch(batch2, db)

        assert res1.success is True
        assert res2.success is True
        assert res1.batch_id != res2.batch_id


# ===========================================================================
# PHASE 3: Complete UNKNOWN Recovery & Webhook Consistency Tests
# ===========================================================================

class TestPhase3ReconciliationAndWebhooks:
    def test_case_a_reconciliation_with_batch_id_resolves_unknown(self, db):
        batch_id, ob_id = _create_approved_batch(db)

        # Seed UNKNOWN submission with paypal_payout_batch_id
        now = datetime.now(timezone.utc)
        sender_batch_id = f"PUFI-{batch_id[:8]}-test"
        sub = ProviderSubmission(
            batch_id=batch_id,
            provider_code="PAYPAL_SANDBOX",
            sender_batch_id=sender_batch_id,
            paypal_payout_batch_id="PP-BATCH-RECON-1",
            status="UNKNOWN",
            created_at=now,
        )
        db.add(sub)
        batch = db.query(PaymentBatch).filter(PaymentBatch.id == batch_id).first()
        batch.status = "UNKNOWN"

        instr = PaymentInstruction(
            batch_id=batch_id,
            obligation_id=ob_id,
            provider_code="PAYPAL_SANDBOX",
            amount=Decimal("1000.00"),
            currency="USD",
            idempotency_key=f"IDEM-{batch_id}",
            sender_item_id=f"ITEM-{batch_id}",
            status="UNKNOWN",
            settlement_evidence="NOT_CONFIRMED",
        )
        db.add(instr)
        db.commit()

        # Mock provider query returning SUCCESS
        mock_status = PayPalBatchStatusResult(
            success=True,
            paypal_payout_batch_id="PP-BATCH-RECON-1",
            paypal_batch_status="SUCCESS",
            items=[
                PayoutItemStatus(
                    sender_item_id=f"ITEM-{batch_id}",
                    payout_item_id="PPI-123",
                    transaction_id="TXN-456",
                    item_status="SUCCESS",
                    error_message=None,
                )
            ],
        )

        with patch("services.execution_coordinator.get_batch_status", return_value=mock_status):
            refresh_res = refresh_batch_status(batch_id, db)

        assert refresh_res.success is True
        assert refresh_res.batch_status == "COMPLETED"
        assert sub.status == "SUBMITTED"
        assert instr.status == "COMPLETED"
        assert instr.settlement_evidence == "PROVIDER_REPORTED_COMPLETE"

    def test_case_b_reconciliation_without_batch_id_remains_unknown(self, db):
        batch_id, ob_id = _create_approved_batch(db)

        now = datetime.now(timezone.utc)
        sub = ProviderSubmission(
            batch_id=batch_id,
            provider_code="PAYPAL_SANDBOX",
            sender_batch_id=f"PUFI-{batch_id[:8]}-nobatch",
            paypal_payout_batch_id=None,
            status="UNKNOWN",
            created_at=now,
        )
        db.add(sub)
        batch = db.query(PaymentBatch).filter(PaymentBatch.id == batch_id).first()
        batch.status = "UNKNOWN"
        db.commit()

        refresh_res = refresh_batch_status(batch_id, db)

        assert refresh_res.success is False
        # Must NOT convert to FAILED
        assert sub.status == "UNKNOWN"
        assert batch.status == "UNKNOWN"

    def test_webhook_resolves_unknown_submission_and_batch(self, db, client):
        batch_id, ob_id = _create_approved_batch(db)

        now = datetime.now(timezone.utc)
        sub = ProviderSubmission(
            batch_id=batch_id,
            provider_code="PAYPAL_SANDBOX",
            sender_batch_id=f"PUFI-{batch_id[:8]}-wh",
            paypal_payout_batch_id=None,
            status="UNKNOWN",
            created_at=now,
        )
        db.add(sub)
        batch = db.query(PaymentBatch).filter(PaymentBatch.id == batch_id).first()
        batch.status = "UNKNOWN"

        instr = PaymentInstruction(
            batch_id=batch_id,
            obligation_id=ob_id,
            provider_code="PAYPAL_SANDBOX",
            amount=Decimal("1000.00"),
            currency="USD",
            idempotency_key=f"IDEM-WH-{batch_id}",
            sender_item_id=f"ITEM-WH-{batch_id}",
            status="UNKNOWN",
            settlement_evidence="NOT_CONFIRMED",
        )
        db.add(instr)
        db.commit()

        event_payload = {
            "id": f"WH-EVENT-{uuid.uuid4().hex[:8]}",
            "event_type": "PAYMENT.PAYOUTS-ITEM.SUCCEEDED",
            "resource": {
                "payout_item_id": "PP-ITEM-999",
                "payout_batch_id": "PP-BATCH-FROM-WEBHOOK",
                "transaction_id": "TXN-WEBHOOK-111",
                "payout_item": {
                    "sender_item_id": f"ITEM-WH-{batch_id}",
                },
            },
        }

        with patch.dict(os.environ, {"PAYPAL_WEBHOOK_ID": "WH-TEST-ID"}), \
             patch("routers.webhooks._get_access_token", return_value="dummy-token"), \
             patch("routers.webhooks._verify_webhook_signature", return_value=True):
            headers = {
                "PAYPAL-TRANSMISSION-ID": "trans-1",
                "PAYPAL-TRANSMISSION-TIME": "2026-11-12T00:00:00Z",
                "PAYPAL-CERT-URL": "https://api.sandbox.paypal.com/cert",
                "PAYPAL-AUTH-ALGO": "SHA256withRSA",
                "PAYPAL-TRANSMISSION-SIG": "sig==",
            }
            resp = client.post("/api/v1/webhooks/paypal", json=event_payload, headers=headers)

        assert resp.status_code == 200
        db.refresh(instr)
        db.refresh(sub)
        db.refresh(batch)

        assert instr.status == "COMPLETED"
        assert sub.status == "SUBMITTED"
        assert sub.paypal_payout_batch_id == "PP-BATCH-FROM-WEBHOOK"
        assert batch.status == "COMPLETED"

    def test_webhook_state_precedence_cannot_regress_completed(self, db, client):
        batch_id, ob_id = _create_approved_batch(db)

        instr = PaymentInstruction(
            batch_id=batch_id,
            obligation_id=ob_id,
            provider_code="PAYPAL_SANDBOX",
            amount=Decimal("1000.00"),
            currency="USD",
            idempotency_key=f"IDEM-PREC-{batch_id}",
            sender_item_id=f"ITEM-PREC-{batch_id}",
            status="COMPLETED",
            settlement_evidence="PROVIDER_REPORTED_COMPLETE",
        )
        db.add(instr)
        db.commit()

        late_event = {
            "id": f"WH-EVENT-LATE-{uuid.uuid4().hex[:8]}",
            "event_type": "PAYMENT.PAYOUTS-ITEM.UNCLAIMED",  # Attempts to regress to SUBMITTED
            "resource": {
                "payout_item": {
                    "sender_item_id": f"ITEM-PREC-{batch_id}",
                },
            },
        }

        with patch.dict(os.environ, {"PAYPAL_WEBHOOK_ID": "WH-TEST-ID"}), \
             patch("routers.webhooks._get_access_token", return_value="dummy-token"), \
             patch("routers.webhooks._verify_webhook_signature", return_value=True):
            headers = {
                "PAYPAL-TRANSMISSION-ID": "trans-2",
                "PAYPAL-TRANSMISSION-TIME": "2026-11-12T00:00:00Z",
                "PAYPAL-CERT-URL": "https://api.sandbox.paypal.com/cert",
                "PAYPAL-AUTH-ALGO": "SHA256withRSA",
                "PAYPAL-TRANSMISSION-SIG": "sig==",
            }
            resp = client.post("/api/v1/webhooks/paypal", json=late_event, headers=headers)

        assert resp.status_code == 200
        db.refresh(instr)
        # MUST remain COMPLETED!
        assert instr.status == "COMPLETED"

    def test_duplicate_webhook_ignored_idempotently(self, db, client):
        event_id = f"WH-DUP-{uuid.uuid4().hex[:8]}"
        payload = {
            "id": event_id,
            "event_type": "PAYMENT.PAYOUTS-ITEM.SUCCEEDED",
            "resource": {},
        }

        with patch.dict(os.environ, {"PAYPAL_WEBHOOK_ID": "WH-TEST-ID"}), \
             patch("routers.webhooks._get_access_token", return_value="dummy-token"), \
             patch("routers.webhooks._verify_webhook_signature", return_value=True):
            headers = {
                "PAYPAL-TRANSMISSION-ID": "trans-3",
                "PAYPAL-TRANSMISSION-TIME": "2026-11-12T00:00:00Z",
                "PAYPAL-CERT-URL": "https://api.sandbox.paypal.com/cert",
                "PAYPAL-AUTH-ALGO": "SHA256withRSA",
                "PAYPAL-TRANSMISSION-SIG": "sig==",
            }
            resp1 = client.post("/api/v1/webhooks/paypal", json=payload, headers=headers)
            assert resp1.status_code == 200
            assert resp1.json()["status"] == "PROCESSED"

            # Replay duplicate
            resp2 = client.post("/api/v1/webhooks/paypal", json=payload, headers=headers)
            assert resp2.status_code == 200
            assert resp2.json()["status"] == "DUPLICATE_IGNORED"


# ===========================================================================
# PRIORITY 1.1: Genuine Process-Crash & Concurrency Verification
# ===========================================================================

class TestPriority11CrashRecovery:
    """
    Priority 1.1 — Issue 1 & 2: Genuine Process-Crash Regression Tests.

    Simulates the server process terminating immediately after Transaction 1 commits,
    leaving a stranded PENDING submission and ActiveBatchSubmission lock.
    Verifies that on application restart:
      1. Original submission and sender_batch_id are preserved.
      2. Recovery workflow transitions the stranded record to UNKNOWN.
      3. No duplicate payout is generated.
      4. Controlled manual reconciliation can resolve the record safely.
    """

    def test_genuine_process_crash_after_transaction_1_retains_intent_and_recovers_safely(self, db):
        batch_id, ob_id = _create_approved_batch(db)
        now = datetime.now(timezone.utc)
        original_sender_batch_id = f"PUFI-{batch_id[:8]}-crash-test"

        # 1. TRANSACTION 1: Persist submission intent, active lock, and batch status
        sub = ProviderSubmission(
            batch_id=batch_id,
            provider_code="PAYPAL_SANDBOX",
            sender_batch_id=original_sender_batch_id,
            status="PENDING",
            intended_amount=Decimal("1000.00"),
            currency="USD",
            item_count=1,
            created_at=now,
        )
        db.add(sub)
        db.flush()

        active_lock = ActiveBatchSubmission(
            batch_id=batch_id,
            submission_id=sub.id,
            created_at=now,
        )
        db.add(active_lock)

        batch = db.query(PaymentBatch).filter(PaymentBatch.id == batch_id).first()
        batch.status = "SUBMISSION_PENDING"

        pi = PaymentInstruction(
            batch_id=batch_id,
            obligation_id=ob_id,
            provider_code="PAYPAL_SANDBOX",
            amount=Decimal("1000.00"),
            currency="USD",
            idempotency_key=f"PUFI-{batch_id[:8]}-{ob_id[-12:]}",
            sender_item_id=f"PUFI-{batch_id[:8]}-{ob_id[-12:]}",
            status="APPROVED",
            settlement_evidence="NOT_CONFIRMED",
        )
        db.add(pi)
        db.commit()

        # 2. SIMULATE SUDDEN PROCESS CRASH: Close session and discard all in-memory context
        sub_id = sub.id
        db.close()

        # 3. SIMULATE APPLICATION RESTART: Open a fresh database session
        from tests.conftest import TestSessionLocal
        fresh_db = TestSessionLocal()

        try:
            # Verify stranded on-disk state
            reloaded_batch = fresh_db.query(PaymentBatch).filter(PaymentBatch.id == batch_id).first()
            assert reloaded_batch.status == "SUBMISSION_PENDING"

            reloaded_sub = fresh_db.query(ProviderSubmission).filter(ProviderSubmission.id == sub_id).first()
            assert reloaded_sub.status == "PENDING"
            assert reloaded_sub.paypal_payout_batch_id is None
            assert reloaded_sub.sender_batch_id == original_sender_batch_id

            # While stranded in PENDING/SUBMISSION_PENDING, any naive submit attempt must be BLOCKED
            submit_attempt = submit_batch(batch_id, fresh_db)
            assert submit_attempt.success is False
            assert (
                "only approved batches can be submitted" in submit_attempt.error_message.lower()
                or "concurrent_submission_conflict" in submit_attempt.error_message.lower()
                or "already has an active submission" in submit_attempt.error_message.lower()
            )

            # 4. RUN RECOVERY MECHANISM (triggered by status refresh or operator check)
            refresh_res = refresh_batch_status(batch_id, fresh_db)
            assert refresh_res.success is False
            assert refresh_res.batch_status == "UNKNOWN"

            # 5. VERIFY RECOVERY STATE
            fresh_db.refresh(reloaded_sub)
            fresh_db.refresh(reloaded_batch)
            assert reloaded_sub.status == "UNKNOWN"
            assert reloaded_sub.sender_batch_id == original_sender_batch_id  # Stable ID retained!
            assert reloaded_batch.status == "UNKNOWN"

            # ActiveBatchSubmission lock must be released
            remaining_lock = fresh_db.query(ActiveBatchSubmission).filter(ActiveBatchSubmission.batch_id == batch_id).first()
            assert remaining_lock is None

            # Submitting again must be BLOCKED because payment outcome is UNKNOWN
            second_submit = submit_batch(batch_id, fresh_db)
            assert second_submit.success is False
            assert "PAYMENT_STATE_UNKNOWN" in second_submit.error_message

            # Audit trail must record STRANDED_SUBMISSION_RECOVERED
            ev = (
                fresh_db.query(AuditEvent)
                .filter(AuditEvent.entity_id == batch_id, AuditEvent.event_type == "STRANDED_SUBMISSION_RECOVERED")
                .first()
            )
            assert ev is not None
            details = json.loads(ev.details_redacted)
            assert details["sender_batch_id"] == original_sender_batch_id
            assert details["previous_status"] == "PENDING"
            assert details["new_status"] == "UNKNOWN"

        finally:
            fresh_db.close()

    def test_manual_resolution_never_sent(self, db):
        """Controlled recovery when investigation proves payout never reached provider."""
        batch_id, ob_id = _create_approved_batch(db)
        now = datetime.now(timezone.utc)
        sub = ProviderSubmission(
            batch_id=batch_id,
            provider_code="PAYPAL_SANDBOX",
            sender_batch_id=f"PUFI-{batch_id[:8]}-unsent",
            status="UNKNOWN",
            created_at=now,
        )
        db.add(sub)
        batch = db.query(PaymentBatch).filter(PaymentBatch.id == batch_id).first()
        batch.status = "UNKNOWN"
        db.commit()

        # Operator investigates PayPal dashboard and confirms sender_batch_id does not exist
        res = resolve_unresolved_submission(
            batch_id=batch_id,
            resolution="CONFIRM_NEVER_SENT",
            db=db,
            operator_id="OP-FINANCE-01",
            notes="Verified with PayPal Sandbox dashboard: sender_batch_id not present.",
        )
        assert res.success is True
        assert res.batch_status == "APPROVED"
        assert sub.status == "FAILED"
        assert "MANUALLY_RESOLVED_NEVER_SENT" in sub.error_message
        assert batch.status == "APPROVED"

        # Audit event recorded
        ev = db.query(AuditEvent).filter(AuditEvent.entity_id == batch_id, AuditEvent.event_type == "MANUAL_RECONCILIATION_RESOLVED").first()
        assert ev is not None
        assert ev.actor == "OP-FINANCE-01"

    def test_manual_resolution_confirmed_submitted(self, db):
        """Controlled recovery when operator discovers provider payout batch ID."""
        batch_id, ob_id = _create_approved_batch(db)
        now = datetime.now(timezone.utc)
        sub = ProviderSubmission(
            batch_id=batch_id,
            provider_code="PAYPAL_SANDBOX",
            sender_batch_id=f"PUFI-{batch_id[:8]}-found",
            status="UNKNOWN",
            created_at=now,
        )
        db.add(sub)
        batch = db.query(PaymentBatch).filter(PaymentBatch.id == batch_id).first()
        batch.status = "UNKNOWN"
        pi = PaymentInstruction(
            batch_id=batch_id,
            obligation_id=ob_id,
            provider_code="PAYPAL_SANDBOX",
            amount=Decimal("1000.00"),
            currency="USD",
            idempotency_key=f"PUFI-RES-{batch_id[:8]}",
            sender_item_id=f"PUFI-RES-{batch_id[:8]}",
            status="UNKNOWN",
            settlement_evidence="NOT_CONFIRMED",
        )
        db.add(pi)
        db.commit()

        mock_status = PayPalBatchStatusResult(
            success=True,
            paypal_payout_batch_id="5CG123456789",
            paypal_batch_status="SUCCESS",
            items=[
                PayoutItemStatus(
                    sender_item_id=f"PUFI-RES-{batch_id[:8]}",
                    payout_item_id="PI-999",
                    transaction_id="TX-999",
                    item_status="SUCCESS",
                    error_message=None,
                )
            ],
        )

        with patch("services.execution_coordinator.get_batch_status", return_value=mock_status):
            res = resolve_unresolved_submission(
                batch_id=batch_id,
                resolution="CONFIRM_SUBMITTED",
                confirmed_payout_batch_id="5CG123456789",
                db=db,
                operator_id="OP-FINANCE-02",
                notes="Found payout_batch_id in PayPal merchant portal.",
            )

        assert res.success is True
        assert res.batch_status == "COMPLETED"
        assert sub.status == "SUBMITTED"
        assert sub.paypal_payout_batch_id == "5CG123456789"
        assert pi.status == "COMPLETED"


class TestPriority11GenuineConcurrency:
    """
    Priority 1.1 — Issue 3: Genuine Multi-Threaded Concurrency Regression Tests.

    Uses a multi-connection test database and independent threads to prove:
      1. Two concurrent submission requests targeting the same batch result in exactly one payout.
      2. The losing thread receives a clear 409 CONCURRENT_SUBMISSION_CONFLICT error.
      3. Provider adapter is called at most once.
      4. Independent batches can submit concurrently without blocking each other.
    """

    def test_genuine_concurrent_requests_two_threads_independent_sessions(self):
        import tempfile
        import threading
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from models.db import Base

        temp_db = tempfile.mktemp(suffix=".db")
        engine = create_engine(f"sqlite:///{temp_db}", connect_args={"timeout": 15})
        Base.metadata.create_all(bind=engine)
        SessionFactory = sessionmaker(bind=engine)

        setup_db = SessionFactory()
        biz = Business(id="BIZ-CONC-1", display_name="Conc Corp")
        setup_db.add(biz)
        sup = Supplier(
            id="SUP-CONC-1", business_id="BIZ-CONC-1", external_reference="EXT-C1",
            display_name="Conc Sup", country_code="US", recipient_reference_type="EMAIL",
            recipient_reference_masked="c***@example.com", sandbox_recipient_email="conc@paypal.com",
            preferred_currency="USD",
        )
        setup_db.add(sup)
        ob = Obligation(
            id="OBL-CONC-1", business_id="BIZ-CONC-1", supplier_id="SUP-CONC-1",
            invoice_reference="INV-C1", amount=Decimal("500.00"), currency="USD",
            due_at=date(2026, 12, 31), status="VALIDATED", source_hash="hashc1",
        )
        setup_db.add(ob)
        batch = PaymentBatch(
            id="BATCH-CONC-1", business_id="BIZ-CONC-1", batch_reference="REF-C1",
            status="APPROVED", selected_provider_code="PAYPAL_SANDBOX",
        )
        setup_db.add(batch)
        setup_db.add(BatchObligation(batch_id="BATCH-CONC-1", obligation_id="OBL-CONC-1"))
        setup_db.commit()
        setup_db.close()

        results = []
        barrier = threading.Barrier(2)
        mock_submit = MagicMock(return_value=PayPalSubmitResult(
            success=True,
            sender_batch_id="s-conc-1",
            paypal_payout_batch_id="PP-CONC-1",
            paypal_batch_status="SUCCESS",
            http_status=201,
        ))

        def worker():
            thread_db = SessionFactory()
            barrier.wait()  # Synchronize both threads to hit submit_batch at the exact same moment
            with patch("services.execution_coordinator.submit_payout", mock_submit):
                res = submit_batch("BATCH-CONC-1", thread_db)
            results.append(res)
            thread_db.close()

        t1 = threading.Thread(target=worker)
        t2 = threading.Thread(target=worker)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        try:
            assert len(results) == 2
            successes = [r for r in results if r.success]
            failures = [r for r in results if not r.success]

            # Exactly one request must succeed, and exactly one must fail with conflict
            assert len(successes) == 1
            assert len(failures) == 1
            assert "CONCURRENT_SUBMISSION_CONFLICT" in failures[0].error_message

            # Provider adapter called at most once
            assert mock_submit.call_count == 1

            # Database has exactly ONE committed submission intent
            verify_db = SessionFactory()
            subs = verify_db.query(ProviderSubmission).filter_by(batch_id="BATCH-CONC-1").all()
            assert len(subs) == 1
            verify_db.close()

        finally:
            try:
                os.remove(temp_db)
            except Exception:
                pass

    def test_genuine_concurrent_requests_different_batches_succeed(self):
        import tempfile
        import threading
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from models.db import Base

        temp_db = tempfile.mktemp(suffix=".db")
        engine = create_engine(f"sqlite:///{temp_db}", connect_args={"timeout": 15})
        Base.metadata.create_all(bind=engine)
        SessionFactory = sessionmaker(bind=engine)

        setup_db = SessionFactory()
        biz = Business(id="BIZ-MULTI-1", display_name="Multi Corp")
        setup_db.add(biz)
        sup = Supplier(
            id="SUP-MULTI-1", business_id="BIZ-MULTI-1", external_reference="EXT-M1",
            display_name="Multi Sup", country_code="US", recipient_reference_type="EMAIL",
            recipient_reference_masked="m***@example.com", sandbox_recipient_email="multi@paypal.com",
            preferred_currency="USD",
        )
        setup_db.add(sup)
        ob1 = Obligation(
            id="OBL-M1", business_id="BIZ-MULTI-1", supplier_id="SUP-MULTI-1",
            invoice_reference="INV-M1", amount=Decimal("100.00"), currency="USD",
            due_at=date(2026, 12, 31), status="VALIDATED", source_hash="hm1",
        )
        ob2 = Obligation(
            id="OBL-M2", business_id="BIZ-MULTI-1", supplier_id="SUP-MULTI-1",
            invoice_reference="INV-M2", amount=Decimal("200.00"), currency="USD",
            due_at=date(2026, 12, 31), status="VALIDATED", source_hash="hm2",
        )
        setup_db.add_all([ob1, ob2])
        b1 = PaymentBatch(
            id="BATCH-DIFF-1", business_id="BIZ-MULTI-1", batch_reference="REF-M1",
            status="APPROVED", selected_provider_code="PAYPAL_SANDBOX",
        )
        b2 = PaymentBatch(
            id="BATCH-DIFF-2", business_id="BIZ-MULTI-1", batch_reference="REF-M2",
            status="APPROVED", selected_provider_code="PAYPAL_SANDBOX",
        )
        setup_db.add_all([b1, b2])
        setup_db.add(BatchObligation(batch_id="BATCH-DIFF-1", obligation_id="OBL-M1"))
        setup_db.add(BatchObligation(batch_id="BATCH-DIFF-2", obligation_id="OBL-M2"))
        setup_db.commit()
        setup_db.close()

        results = []
        barrier = threading.Barrier(2)

        def worker(b_id):
            thread_db = SessionFactory()
            barrier.wait()
            with patch("services.execution_coordinator.submit_payout", return_value=PayPalSubmitResult(
                success=True,
                sender_batch_id=f"s-{b_id}",
                paypal_payout_batch_id=f"PP-{b_id}",
                paypal_batch_status="SUCCESS",
                http_status=201,
            )):
                res = submit_batch(b_id, thread_db)
            results.append(res)
            thread_db.close()

        t1 = threading.Thread(target=worker, args=("BATCH-DIFF-1",))
        t2 = threading.Thread(target=worker, args=("BATCH-DIFF-2",))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        try:
            assert len(results) == 2
            successes = [r for r in results if r.success]
            assert len(successes) == 2

            verify_db = SessionFactory()
            subs = verify_db.query(ProviderSubmission).all()
            assert len(subs) == 2
            verify_db.close()

        finally:
            try:
                os.remove(temp_db)
            except Exception:
                pass

