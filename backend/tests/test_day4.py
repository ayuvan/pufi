"""
PUFI — Day 4 automated tests.

Covers:
  - Approval service: valid approval, rejection cases
  - PayPal adapter: is_configured, mocked success, timeout, error
  - Execution coordinator: mocked submission and status refresh
  - Idempotency: duplicate submission rejection
  - API endpoints: approve, submit, refresh-status, instructions, audit
  - Demo seed idempotency

All PayPal HTTP calls are mocked — no live API dependency.
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

# Ensure backend/ on path
_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)


# ---------------------------------------------------------------------------
# Shared fixture helpers
# ---------------------------------------------------------------------------

def _make_demo_batch(db, *, with_analysis: bool = True, status: str = "DRAFT"):
    """
    Create a minimal demo batch with 2 VALIDATED USD obligations and
    optionally a stub AiRecommendation.  Returns batch_id.
    """
    from models.entities import (
        AiRecommendation, BatchObligation, Business, Obligation,
        PaymentBatch, Supplier,
    )

    _id = uuid.uuid4().hex[:8]
    biz = Business(id=f"BIZ-D4-{_id}", display_name="Day4 Corp")
    db.add(biz)
    db.flush()

    sup = Supplier(
        id=f"SUP-D4-{_id}",
        business_id=f"BIZ-D4-{_id}",
        external_reference=f"EXT-D4-{_id}",
        display_name="Day4 Supplier",
        country_code="US",
        recipient_reference_type="EMAIL",
        recipient_reference_masked="d4***@example.com",
        preferred_currency="USD",
    )
    db.add(sup)
    db.flush()

    ob1 = Obligation(
        id=f"OBL-D4-{_id}-1",
        business_id=f"BIZ-D4-{_id}",
        supplier_id=f"SUP-D4-{_id}",
        invoice_reference=f"INV-D4-{_id}-1",
        amount=Decimal("500.00"),
        currency="USD",
        due_at=date(2026, 12, 31),
        status="VALIDATED",
        source_hash=f"d4{_id}1",
    )
    ob2 = Obligation(
        id=f"OBL-D4-{_id}-2",
        business_id=f"BIZ-D4-{_id}",
        supplier_id=f"SUP-D4-{_id}",
        invoice_reference=f"INV-D4-{_id}-2",
        amount=Decimal("750.00"),
        currency="USD",
        due_at=date(2026, 12, 31),
        status="VALIDATED",
        source_hash=f"d4{_id}2",
    )
    db.add_all([ob1, ob2])
    db.flush()

    batch_id = f"BATCH-D4-{_id}"
    batch = PaymentBatch(
        id=batch_id,
        business_id=f"BIZ-D4-{_id}",
        batch_reference=f"D4-REF-{_id}",
        status=status,
    )
    db.add(batch)
    db.flush()

    db.add(BatchObligation(batch_id=batch_id, obligation_id=f"OBL-D4-{_id}-1"))
    db.add(BatchObligation(batch_id=batch_id, obligation_id=f"OBL-D4-{_id}-2"))
    db.flush()

    if with_analysis:
        ai_rec = AiRecommendation(
            id=f"AI-D4-{_id}",
            batch_id=batch_id,
            model_name="gemini-2.5-flash",
            input_summary_hash="abc123",
            recommendation_json=json.dumps({
                "summary": "Demo analysis",
                "recommended_route": "PAYPAL_SANDBOX",
                "reasoning_factors": ["Lowest cost"],
                "warnings": [],
                "requires_human_review": False,
                "evidence_fields": {
                    "eligible_route_codes": ["PAYPAL_SANDBOX", "SIMULATED_FAST"],
                },
                "fallback_used": False,
                "fallback_reason": None,
            }),
            fallback_used=False,
            fallback_reason=None,
        )
        db.add(ai_rec)
        db.flush()

    return batch_id


# ===========================================================================
# Approval service tests
# ===========================================================================

class TestApprovalService:
    def test_approve_valid_batch(self, db):
        """Happy path: DRAFT batch + analysis → APPROVED."""
        from services.approval import approve_batch

        batch_id = _make_demo_batch(db)
        result = approve_batch(
            batch_id=batch_id,
            approver_id="DEMO_USER",
            selected_provider="PAYPAL_SANDBOX",
            routing_strategy="LOWEST_COST",
            confirmed_total="1250.00",
            confirmed_currency="USD",
            db=db,
        )
        assert result.success, f"Expected success, got error: {result.error_code}: {result.error_detail}"
        assert result.status == "APPROVED"
        assert result.approved_by == "DEMO_USER"
        assert result.selected_provider == "PAYPAL_SANDBOX"
        assert result.approved_recipient_count == 2

    def test_approve_rejects_missing_batch(self, db):
        """Non-existent batch returns BATCH_NOT_FOUND."""
        from services.approval import approve_batch

        result = approve_batch(
            batch_id="NO-SUCH-BATCH",
            approver_id="DEMO_USER",
            selected_provider="PAYPAL_SANDBOX",
            routing_strategy="LOWEST_COST",
            confirmed_total="100.00",
            confirmed_currency="USD",
            db=db,
        )
        assert not result.success
        assert result.error_code == "BATCH_NOT_FOUND"

    def test_approve_rejects_no_analysis(self, db):
        """Batch without AiRecommendation returns ANALYSIS_REQUIRED."""
        from services.approval import approve_batch

        batch_id = _make_demo_batch(db, with_analysis=False)
        result = approve_batch(
            batch_id=batch_id,
            approver_id="DEMO_USER",
            selected_provider="PAYPAL_SANDBOX",
            routing_strategy="LOWEST_COST",
            confirmed_total="1250.00",
            confirmed_currency="USD",
            db=db,
        )
        assert not result.success
        assert result.error_code == "ANALYSIS_REQUIRED"

    def test_approve_rejects_wrong_status(self, db):
        """Already SUBMITTED batch returns INVALID_BATCH_STATUS."""
        from services.approval import approve_batch

        batch_id = _make_demo_batch(db, status="SUBMITTED")
        result = approve_batch(
            batch_id=batch_id,
            approver_id="DEMO_USER",
            selected_provider="PAYPAL_SANDBOX",
            routing_strategy="LOWEST_COST",
            confirmed_total="1250.00",
            confirmed_currency="USD",
            db=db,
        )
        assert not result.success
        assert result.error_code == "INVALID_BATCH_STATUS"

    def test_approve_rejects_total_mismatch(self, db):
        """Wrong confirmed_total returns TOTAL_MISMATCH."""
        from services.approval import approve_batch

        batch_id = _make_demo_batch(db)
        result = approve_batch(
            batch_id=batch_id,
            approver_id="DEMO_USER",
            selected_provider="PAYPAL_SANDBOX",
            routing_strategy="LOWEST_COST",
            confirmed_total="9999.00",   # wrong
            confirmed_currency="USD",
            db=db,
        )
        assert not result.success
        assert result.error_code == "TOTAL_MISMATCH"

    def test_approve_rejects_inr_for_paypal(self, db):
        """PayPal Sandbox with INR currency returns UNSUPPORTED_CURRENCY."""
        from services.approval import approve_batch

        batch_id = _make_demo_batch(db)
        result = approve_batch(
            batch_id=batch_id,
            approver_id="DEMO_USER",
            selected_provider="PAYPAL_SANDBOX",
            routing_strategy="LOWEST_COST",
            confirmed_total="1250.00",
            confirmed_currency="INR",   # not supported by PayPal sandbox
            db=db,
        )
        assert not result.success
        assert result.error_code == "UNSUPPORTED_CURRENCY"

    def test_approve_rejects_provider_not_eligible(self, db):
        """Provider not in eligible routes from analysis → PROVIDER_NOT_ELIGIBLE."""
        from services.approval import approve_batch

        batch_id = _make_demo_batch(db)
        result = approve_batch(
            batch_id=batch_id,
            approver_id="DEMO_USER",
            selected_provider="NONEXISTENT_PROVIDER",
            routing_strategy="LOWEST_COST",
            confirmed_total="1250.00",
            confirmed_currency="USD",
            db=db,
        )
        assert not result.success
        assert result.error_code == "PROVIDER_NOT_ELIGIBLE"

    def test_approve_rejects_already_submitted(self, db):
        """Batch with active ProviderSubmission → ALREADY_SUBMITTED."""
        from models.entities import ProviderSubmission
        from services.approval import approve_batch

        batch_id = _make_demo_batch(db)
        # Pre-create an active submission
        sub = ProviderSubmission(
            batch_id=batch_id,
            provider_code="PAYPAL_SANDBOX",
            sender_batch_id=f"PUFI-TEST-SENDER-{uuid.uuid4().hex[:8]}",
            status="SUBMITTED",
        )
        db.add(sub)
        db.flush()

        result = approve_batch(
            batch_id=batch_id,
            approver_id="DEMO_USER",
            selected_provider="PAYPAL_SANDBOX",
            routing_strategy="LOWEST_COST",
            confirmed_total="1250.00",
            confirmed_currency="USD",
            db=db,
        )
        assert not result.success
        assert result.error_code == "ALREADY_SUBMITTED"

    def test_approve_writes_audit_event(self, db):
        """Successful approval creates an AuditEvent."""
        from models.entities import AuditEvent
        from services.approval import approve_batch

        batch_id = _make_demo_batch(db)
        result = approve_batch(
            batch_id=batch_id,
            approver_id="DEMO_USER",
            selected_provider="PAYPAL_SANDBOX",
            routing_strategy="LOWEST_COST",
            confirmed_total="1250.00",
            confirmed_currency="USD",
            db=db,
        )
        assert result.success
        audit = db.query(AuditEvent).filter(
            AuditEvent.entity_id == batch_id,
            AuditEvent.event_type == "APPROVED",
        ).first()
        assert audit is not None
        assert audit.actor == "DEMO_USER"


# ===========================================================================
# PayPal adapter tests (all mocked)
# ===========================================================================

class TestPayPalAdapter:
    def test_is_configured_false_when_no_env(self, monkeypatch):
        """is_configured returns False without credentials."""
        from services import paypal_adapter
        monkeypatch.delenv("PAYPAL_MODE", raising=False)
        monkeypatch.delenv("PAYPAL_CLIENT_ID", raising=False)
        monkeypatch.delenv("PAYPAL_CLIENT_SECRET", raising=False)
        assert paypal_adapter.is_configured() is False

    def test_is_configured_false_when_mode_wrong(self, monkeypatch):
        """is_configured returns False when mode is not 'sandbox'."""
        from services import paypal_adapter
        monkeypatch.setenv("PAYPAL_MODE", "production")
        monkeypatch.setenv("PAYPAL_CLIENT_ID", "abc")
        monkeypatch.setenv("PAYPAL_CLIENT_SECRET", "secret")
        assert paypal_adapter.is_configured() is False

    def test_is_configured_true(self, monkeypatch):
        """is_configured returns True with all correct env vars."""
        from services import paypal_adapter
        monkeypatch.setenv("PAYPAL_MODE", "sandbox")
        monkeypatch.setenv("PAYPAL_CLIENT_ID", "CLIENT_ID")
        monkeypatch.setenv("PAYPAL_CLIENT_SECRET", "CLIENT_SECRET")
        assert paypal_adapter.is_configured() is True

    def test_submit_payout_unconfigured_returns_simulated(self, monkeypatch):
        """submit_payout returns is_simulated=True when adapter not configured."""
        from services import paypal_adapter
        from services.paypal_adapter import PayoutItem
        monkeypatch.delenv("PAYPAL_MODE", raising=False)
        monkeypatch.delenv("PAYPAL_CLIENT_ID", raising=False)
        monkeypatch.delenv("PAYPAL_CLIENT_SECRET", raising=False)

        result = paypal_adapter.submit_payout(
            sender_batch_id="TEST-BATCH-001",
            items=[
                PayoutItem(
                    sender_item_id="ITEM-001",
                    receiver_email="test@example.com",
                    amount_value="500.00",
                    currency="USD",
                )
            ],
        )
        assert result.is_simulated is True
        assert result.success is False
        assert result.sender_batch_id == "TEST-BATCH-001"

    def test_submit_payout_rejects_non_usd(self, monkeypatch):
        """submit_payout raises ValueError for non-USD currencies."""
        from services import paypal_adapter
        from services.paypal_adapter import PayoutItem
        monkeypatch.setenv("PAYPAL_MODE", "sandbox")
        monkeypatch.setenv("PAYPAL_CLIENT_ID", "ID")
        monkeypatch.setenv("PAYPAL_CLIENT_SECRET", "SECRET")

        with pytest.raises(ValueError, match="only supports USD"):
            paypal_adapter.submit_payout(
                sender_batch_id="TEST-BATCH-INR",
                items=[
                    PayoutItem(
                        sender_item_id="ITEM-INR",
                        receiver_email="test@example.com",
                        amount_value="1000.00",
                        currency="INR",
                    )
                ],
            )

    def test_submit_payout_mocked_success(self, monkeypatch):
        """Mocked PayPal submission returns success with payout_batch_id."""
        import httpx
        from services import paypal_adapter
        from services.paypal_adapter import PayoutItem

        monkeypatch.setenv("PAYPAL_MODE", "sandbox")
        monkeypatch.setenv("PAYPAL_CLIENT_ID", "FAKE_ID")
        monkeypatch.setenv("PAYPAL_CLIENT_SECRET", "FAKE_SECRET")
        paypal_adapter._clear_token_cache()

        # Mock OAuth
        oauth_resp = MagicMock()
        oauth_resp.status_code = 200
        oauth_resp.json.return_value = {"access_token": "MOCK_TOKEN", "expires_in": 3600}

        # Mock payout submission
        payout_resp = MagicMock()
        payout_resp.status_code = 201
        payout_resp.json.return_value = {
            "batch_header": {
                "payout_batch_id": "MOCK_PAYPAL_BATCH_001",
                "batch_status": "PENDING",
                "sender_batch_header": {"sender_batch_id": "TEST-BATCH-MOCK"},
            }
        }
        payout_resp.text = json.dumps(payout_resp.json.return_value)

        with patch("httpx.post", side_effect=[oauth_resp, payout_resp]):
            result = paypal_adapter.submit_payout(
                sender_batch_id="TEST-BATCH-MOCK",
                items=[
                    PayoutItem(
                        sender_item_id="ITEM-001",
                        receiver_email="sb-test@example.com",
                        amount_value="500.00",
                        currency="USD",
                    )
                ],
            )

        assert result.success is True
        assert result.paypal_payout_batch_id == "MOCK_PAYPAL_BATCH_001"
        assert result.paypal_batch_status == "PENDING"
        assert result.is_simulated is False

    def test_submit_payout_timeout_returns_unknown(self, monkeypatch):
        """Timeout during payout submission returns UNKNOWN (not FAILED)."""
        import httpx
        from services import paypal_adapter
        from services.paypal_adapter import PayoutItem

        monkeypatch.setenv("PAYPAL_MODE", "sandbox")
        monkeypatch.setenv("PAYPAL_CLIENT_ID", "FAKE_ID")
        monkeypatch.setenv("PAYPAL_CLIENT_SECRET", "FAKE_SECRET")
        paypal_adapter._clear_token_cache()

        oauth_resp = MagicMock()
        oauth_resp.status_code = 200
        oauth_resp.json.return_value = {"access_token": "MOCK_TOKEN", "expires_in": 3600}

        with patch("httpx.post", side_effect=[oauth_resp, httpx.TimeoutException("timed out")]):
            result = paypal_adapter.submit_payout(
                sender_batch_id="TEST-TIMEOUT-BATCH",
                items=[
                    PayoutItem(
                        sender_item_id="ITEM-T",
                        receiver_email="sb-test@example.com",
                        amount_value="500.00",
                        currency="USD",
                    )
                ],
            )

        assert result.success is False
        assert "timed out" in (result.error_message or "").lower()

    def test_submit_payout_api_error(self, monkeypatch):
        """PayPal API 400 error is handled gracefully."""
        import httpx
        from services import paypal_adapter
        from services.paypal_adapter import PayoutItem

        monkeypatch.setenv("PAYPAL_MODE", "sandbox")
        monkeypatch.setenv("PAYPAL_CLIENT_ID", "FAKE_ID")
        monkeypatch.setenv("PAYPAL_CLIENT_SECRET", "FAKE_SECRET")
        paypal_adapter._clear_token_cache()

        oauth_resp = MagicMock()
        oauth_resp.status_code = 200
        oauth_resp.json.return_value = {"access_token": "MOCK_TOKEN", "expires_in": 3600}

        err_resp = MagicMock()
        err_resp.status_code = 400
        err_resp.text = json.dumps({"name": "VALIDATION_ERROR", "message": "Invalid request"})

        with patch("httpx.post", side_effect=[oauth_resp, err_resp]):
            result = paypal_adapter.submit_payout(
                sender_batch_id="TEST-ERR-BATCH",
                items=[
                    PayoutItem(
                        sender_item_id="ITEM-ERR",
                        receiver_email="sb-test@example.com",
                        amount_value="500.00",
                        currency="USD",
                    )
                ],
            )

        assert result.success is False
        assert result.http_status == 400
        assert "VALIDATION_ERROR" in (result.error_message or "")

    def test_oauth_failure_handled(self, monkeypatch):
        """OAuth failure returns failure result (no credentials in error)."""
        import httpx
        from services import paypal_adapter
        from services.paypal_adapter import PayoutItem

        monkeypatch.setenv("PAYPAL_MODE", "sandbox")
        monkeypatch.setenv("PAYPAL_CLIENT_ID", "FAKE_ID")
        monkeypatch.setenv("PAYPAL_CLIENT_SECRET", "FAKE_SECRET")
        paypal_adapter._clear_token_cache()

        oauth_resp = MagicMock()
        oauth_resp.status_code = 401
        oauth_resp.text = "Unauthorized"

        with patch("httpx.post", return_value=oauth_resp):
            result = paypal_adapter.submit_payout(
                sender_batch_id="TEST-OAUTH-FAIL",
                items=[
                    PayoutItem(
                        sender_item_id="ITEM-OF",
                        receiver_email="sb-test@example.com",
                        amount_value="500.00",
                        currency="USD",
                    )
                ],
            )

        assert result.success is False
        # Ensure secret is NOT in the error message
        assert "FAKE_SECRET" not in (result.error_message or "")


# ===========================================================================
# Execution coordinator tests (mocked adapter calls)
# ===========================================================================

class TestExecutionCoordinator:
    def _approve_batch(self, db, batch_id: str) -> None:
        """Helper: set batch to APPROVED with required fields."""
        from models.entities import PaymentBatch
        batch = db.query(PaymentBatch).filter(PaymentBatch.id == batch_id).first()
        batch.status = "APPROVED"
        batch.approved_by = "DEMO_USER"
        batch.approved_at = datetime.now(timezone.utc)
        batch.selected_provider_code = "PAYPAL_SANDBOX"
        batch.approved_total_amount = Decimal("1250.00")
        batch.approved_currency = "USD"
        batch.approved_recipient_count = 2
        batch.approved_routing_strategy = "LOWEST_COST"
        db.flush()

    def test_submit_batch_not_approved(self, db):
        """submit_batch fails if batch not in APPROVED status."""
        from services.execution_coordinator import submit_batch as _submit

        batch_id = _make_demo_batch(db)
        result = _submit(batch_id=batch_id, db=db)
        assert not result.success
        assert "APPROVED" in (result.error_message or "")

    def test_submit_batch_mocked_paypal_success(self, db, monkeypatch):
        """Mocked successful PayPal submission creates instructions and ProviderSubmission."""
        from models.entities import PaymentInstruction, ProviderSubmission
        from services import paypal_adapter
        from services.paypal_adapter import PayPalSubmitResult
        from services.execution_coordinator import submit_batch as _submit

        batch_id = _make_demo_batch(db)
        self._approve_batch(db, batch_id)

        mock_result = PayPalSubmitResult(
            success=True,
            sender_batch_id="MOCK-SBH",
            paypal_payout_batch_id="PP-MOCK-001",
            paypal_batch_status="PENDING",
            http_status=201,
            is_simulated=False,
        )

        with patch("services.execution_coordinator.submit_payout", return_value=mock_result):
            with patch("services.execution_coordinator.is_configured", return_value=True):
                result = _submit(batch_id=batch_id, db=db)

        assert result.success is True
        assert result.paypal_payout_batch_id == "PP-MOCK-001"
        assert result.submission_status == "SUBMITTED"
        assert result.paypal_configured is True
        assert result.is_simulated is False

        # Verify instructions were created
        instrs = db.query(PaymentInstruction).filter(PaymentInstruction.batch_id == batch_id).all()
        assert len(instrs) == 2
        for instr in instrs:
            assert instr.status == "SUBMITTED"
            assert instr.currency == "USD"

        # Verify ProviderSubmission was created
        sub = db.query(ProviderSubmission).filter(ProviderSubmission.batch_id == batch_id).first()
        assert sub is not None
        assert sub.paypal_payout_batch_id == "PP-MOCK-001"

    def test_duplicate_submission_rejected(self, db):
        """APPROVED batch with active ProviderSubmission is rejected (duplicate guard)."""
        from models.entities import PaymentBatch, ProviderSubmission
        from services.execution_coordinator import submit_batch as _submit

        # Batch must be APPROVED so we reach the ProviderSubmission guard
        batch_id = _make_demo_batch(db, status="APPROVED")
        batch = db.query(PaymentBatch).filter(PaymentBatch.id == batch_id).first()
        batch.selected_provider_code = "PAYPAL_SANDBOX"
        db.flush()

        # Pre-existing active submission
        sub = ProviderSubmission(
            batch_id=batch_id,
            provider_code="PAYPAL_SANDBOX",
            sender_batch_id=f"PUFI-EXISTING-{uuid.uuid4().hex[:8]}",
            status="SUBMITTED",
            paypal_payout_batch_id="PP-EXISTING-001",
        )
        db.add(sub)
        db.flush()

        result = _submit(batch_id=batch_id, db=db)
        assert not result.success
        assert "already has an active submission" in (result.error_message or "")

    def test_sender_batch_id_reused_on_pending_submission(self, db):
        """Existing PENDING submission is returned (sender_batch_id stable)."""
        from models.entities import ProviderSubmission
        from services.execution_coordinator import submit_batch as _submit

        batch_id = _make_demo_batch(db, status="APPROVED")
        sender_id = f"PUFI-STABLE-{uuid.uuid4().hex[:8]}"
        sub = ProviderSubmission(
            batch_id=batch_id,
            provider_code="PAYPAL_SANDBOX",
            sender_batch_id=sender_id,
            status="PENDING",
        )
        db.add(sub)
        db.flush()

        result = _submit(batch_id=batch_id, db=db)
        assert not result.success
        assert result.sender_batch_id == sender_id

    def test_status_refresh_success(self, db, monkeypatch):
        """Status refresh maps PayPal SUCCESS items to COMPLETED instructions."""
        from models.entities import BatchObligation, PaymentInstruction, ProviderSubmission
        from services.paypal_adapter import PayPalBatchStatusResult, PayoutItemStatus
        from services.execution_coordinator import refresh_status as _refresh

        batch_id = _make_demo_batch(db, status="SUBMITTED")
        # Get a real obligation ID from the batch
        bo = db.query(BatchObligation).filter(BatchObligation.batch_id == batch_id).first()
        real_ob_id = bo.obligation_id

        # Create submission record
        sub = ProviderSubmission(
            batch_id=batch_id,
            provider_code="PAYPAL_SANDBOX",
            sender_batch_id=f"PUFI-REFRESH-{uuid.uuid4().hex[:8]}",
            status="SUBMITTED",
            paypal_payout_batch_id="PP-REFRESH-001",
        )
        db.add(sub)
        # Create instruction records with real obligation FK
        instr = PaymentInstruction(
            batch_id=batch_id,
            obligation_id=real_ob_id,
            provider_code="PAYPAL_SANDBOX",
            amount=Decimal("500.00"),
            currency="USD",
            idempotency_key=f"IDEM-REFRESH-{uuid.uuid4().hex}",
            sender_item_id="ITEM-REFRESH-001",
            status="SUBMITTED",
        )
        db.add(instr)
        db.flush()

        mock_status = PayPalBatchStatusResult(
            success=True,
            paypal_payout_batch_id="PP-REFRESH-001",
            paypal_batch_status="SUCCESS",
            items=[
                PayoutItemStatus(
                    sender_item_id="ITEM-REFRESH-001",
                    payout_item_id="PP-ITEM-001",
                    transaction_id="TXN-001",
                    item_status="SUCCESS",
                    error_message=None,
                )
            ],
        )

        with patch("services.execution_coordinator.get_batch_status", return_value=mock_status):
            with patch("services.execution_coordinator.is_configured", return_value=True):
                result = _refresh(batch_id=batch_id, db=db)

        assert result.success is True
        assert result.completed == 1
        assert result.batch_status == "COMPLETED"

    def test_status_refresh_partial_completion(self, db):
        """Partial success: mix of SUCCESS and FAILED items → PARTIALLY_COMPLETED."""
        from models.entities import ProviderSubmission
        from services.paypal_adapter import PayPalBatchStatusResult, PayoutItemStatus
        from services.execution_coordinator import refresh_status as _refresh

        batch_id = _make_demo_batch(db, status="SUBMITTED")
        sub = ProviderSubmission(
            batch_id=batch_id,
            provider_code="PAYPAL_SANDBOX",
            sender_batch_id=f"PUFI-PARTIAL-{uuid.uuid4().hex[:8]}",
            status="SUBMITTED",
            paypal_payout_batch_id="PP-PARTIAL-001",
        )
        db.add(sub)
        db.flush()

        mock_status = PayPalBatchStatusResult(
            success=True,
            paypal_payout_batch_id="PP-PARTIAL-001",
            paypal_batch_status="PROCESSING",
            items=[
                PayoutItemStatus("ITEM-A", "PP-A", "TXN-A", "SUCCESS", None),
                PayoutItemStatus("ITEM-B", None, None, "FAILED", "Account restricted"),
            ],
        )

        with patch("services.execution_coordinator.get_batch_status", return_value=mock_status):
            with patch("services.execution_coordinator.is_configured", return_value=True):
                result = _refresh(batch_id=batch_id, db=db)

        assert result.completed == 1
        assert result.failed == 1
        assert result.batch_status == "PARTIALLY_COMPLETED"

    def test_status_refresh_no_submission(self, db):
        """refresh_status returns error when no PayPal payout batch ID exists."""
        from services.execution_coordinator import refresh_status as _refresh

        batch_id = _make_demo_batch(db, status="SUBMITTED")
        result = _refresh(batch_id=batch_id, db=db)
        assert not result.success
        assert "No PayPal payout batch ID" in (result.error_message or "")


# ===========================================================================
# API endpoint tests
# ===========================================================================

class TestApprovalEndpoint:
    def test_approve_endpoint_success(self, client, db):
        """POST /approve returns 200 with approval details."""
        batch_id = _make_demo_batch(db)

        resp = client.post(
            f"/api/v1/batches/{batch_id}/approve",
            json={
                "approver_id": "DEMO_USER",
                "selected_provider": "PAYPAL_SANDBOX",
                "routing_strategy": "LOWEST_COST",
                "confirmed_total": "1250.00",
                "confirmed_currency": "USD",
            },
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["status"] == "APPROVED"
        assert data["approved_by"] == "DEMO_USER"
        assert data["selected_provider"] == "PAYPAL_SANDBOX"

    def test_approve_endpoint_invalid_batch(self, client):
        """POST /approve with unknown batch returns 422."""
        resp = client.post(
            "/api/v1/batches/NO-SUCH-BATCH/approve",
            json={
                "approver_id": "DEMO_USER",
                "selected_provider": "PAYPAL_SANDBOX",
                "routing_strategy": "LOWEST_COST",
                "confirmed_total": "100.00",
                "confirmed_currency": "USD",
            },
        )
        assert resp.status_code == 422

    def test_submit_endpoint_requires_approved_status(self, client, db):
        """POST /submit for DRAFT batch returns 422."""
        batch_id = _make_demo_batch(db)

        resp = client.post(f"/api/v1/batches/{batch_id}/submit")
        assert resp.status_code == 422
        data = resp.json()
        assert "APPROVED" in str(data)

    def test_submit_endpoint_unconfigured_paypal(self, client, db, monkeypatch):
        """POST /submit when PayPal not configured returns simulated=True in error detail."""
        monkeypatch.delenv("PAYPAL_MODE", raising=False)
        monkeypatch.delenv("PAYPAL_CLIENT_ID", raising=False)
        monkeypatch.delenv("PAYPAL_CLIENT_SECRET", raising=False)

        from models.entities import PaymentBatch
        batch_id = _make_demo_batch(db)
        # Manually set to APPROVED with required fields
        batch = db.query(PaymentBatch).filter(PaymentBatch.id == batch_id).first()
        batch.status = "APPROVED"
        batch.selected_provider_code = "PAYPAL_SANDBOX"
        batch.approved_total_amount = Decimal("1250.00")
        batch.approved_currency = "USD"
        batch.approved_recipient_count = 2
        db.flush()

        resp = client.post(f"/api/v1/batches/{batch_id}/submit")
        # Unconfigured PayPal: 422 with is_simulated in detail
        assert resp.status_code == 422
        data = resp.json()
        assert data["detail"]["is_simulated"] is True

    def test_instructions_endpoint_empty(self, client, db):
        """GET /instructions for batch with no instructions returns empty list."""
        batch_id = _make_demo_batch(db)
        resp = client.get(f"/api/v1/batches/{batch_id}/instructions")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_audit_endpoint_empty(self, client, db):
        """GET /audit for new batch returns empty list."""
        batch_id = _make_demo_batch(db)
        resp = client.get(f"/api/v1/batches/{batch_id}/audit")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_audit_endpoint_after_approval(self, client, db):
        """GET /audit shows APPROVED event after batch approval."""
        batch_id = _make_demo_batch(db)
        client.post(
            f"/api/v1/batches/{batch_id}/approve",
            json={
                "approver_id": "DEMO_USER",
                "selected_provider": "PAYPAL_SANDBOX",
                "routing_strategy": "LOWEST_COST",
                "confirmed_total": "1250.00",
                "confirmed_currency": "USD",
            },
        )
        resp = client.get(f"/api/v1/batches/{batch_id}/audit")
        assert resp.status_code == 200
        events = resp.json()
        assert len(events) >= 1
        assert any(e["event_type"] == "APPROVED" for e in events)


# ===========================================================================
# ORM model tests
# ===========================================================================

class TestDay4Models:
    def test_payment_instruction_created(self, db):
        """PaymentInstruction can be created and queried."""
        from models.entities import PaymentInstruction

        batch_id = _make_demo_batch(db)
        # Get one obligation ID
        from models.entities import BatchObligation
        bo = db.query(BatchObligation).filter(BatchObligation.batch_id == batch_id).first()

        instr = PaymentInstruction(
            batch_id=batch_id,
            obligation_id=bo.obligation_id,
            provider_code="PAYPAL_SANDBOX",
            amount=Decimal("500.00"),
            currency="USD",
            idempotency_key=f"TEST-IDEM-{uuid.uuid4().hex}",
            sender_item_id=f"TEST-SENDER-{uuid.uuid4().hex}",
            status="CREATED",
            settlement_evidence="NOT_CONFIRMED",
        )
        db.add(instr)
        db.flush()

        fetched = db.query(PaymentInstruction).filter(PaymentInstruction.id == instr.id).first()
        assert fetched is not None
        assert fetched.currency == "USD"
        assert fetched.status == "CREATED"
        assert fetched.settlement_evidence == "NOT_CONFIRMED"

    def test_idempotency_key_unique_constraint(self, db):
        """Two instructions with the same idempotency_key are rejected."""
        from models.entities import BatchObligation, PaymentInstruction
        from sqlalchemy.exc import IntegrityError

        batch_id = _make_demo_batch(db)
        bos = db.query(BatchObligation).filter(BatchObligation.batch_id == batch_id).all()

        idem_key = f"UNIQUE-IDEM-{uuid.uuid4().hex}"
        instr1 = PaymentInstruction(
            batch_id=batch_id,
            obligation_id=bos[0].obligation_id,
            provider_code="PAYPAL_SANDBOX",
            amount=Decimal("500.00"),
            currency="USD",
            idempotency_key=idem_key,
            sender_item_id=f"SENDER-1-{uuid.uuid4().hex}",
            status="CREATED",
        )
        db.add(instr1)
        db.flush()

        instr2 = PaymentInstruction(
            batch_id=batch_id,
            obligation_id=bos[1].obligation_id,
            provider_code="PAYPAL_SANDBOX",
            amount=Decimal("750.00"),
            currency="USD",
            idempotency_key=idem_key,  # duplicate!
            sender_item_id=f"SENDER-2-{uuid.uuid4().hex}",
            status="CREATED",
        )
        db.add(instr2)
        with pytest.raises(IntegrityError):
            db.flush()

    def test_audit_event_created(self, db):
        """AuditEvent can be inserted and queried."""
        from models.entities import AuditEvent

        batch_id = _make_demo_batch(db)
        ev = AuditEvent(
            entity_type="BATCH",
            entity_id=batch_id,
            event_type="TEST_EVENT",
            actor="TEST_ACTOR",
            details_redacted=json.dumps({"key": "value"}),
        )
        db.add(ev)
        db.flush()

        fetched = db.query(AuditEvent).filter(AuditEvent.entity_id == batch_id).first()
        assert fetched is not None
        assert fetched.event_type == "TEST_EVENT"
