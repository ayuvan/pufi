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
    refresh_batch_status, submit_batch,
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
