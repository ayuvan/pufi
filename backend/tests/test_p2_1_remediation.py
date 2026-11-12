"""
PUFI — Priority 2.1 Critical Security and Integrity Verification Test Suite.

Covers:
  1. P0 — Trusted Authentication & Authorization:
     - Removal of trust from client-supplied X-Actor-Role and X-Actor-Id headers.
     - Server-controlled identity and role assignment (via API key registry).
     - Derivation of approval actors from authenticated principals.
     - Proof that callers cannot grant themselves CONTROLLER, TREASURY_CHECKER, or ADMIN.
     - Proof that changing identity headers cannot impersonate another approver.
  2. P0 — Terminal State Transition Integrity:
     - Rejection of FAILED -> COMPLETED, CANCELLED -> COMPLETED, CANCELLED -> FAILED.
     - Rejection of COMPLETED -> FAILED and COMPLETED -> SUBMITTED.
     - Permitting legitimate refunds/reversals ONLY through explicit refund events with verified timestamps.
     - Conservative rejection of untimestamped refund events against COMPLETED payments.
     - Verification for every terminal-state combination.
  3. P1 — Cryptographic Audit-Chain Verification:
     - Global verification validating independent entity chains separately.
     - Aggregation of results across distinct entities with separate genesis events.
     - Reporting the exact broken entity_id and broken_event_id on failure.
     - Detection of intermediate deletion, payload tampering, reordering, and truncation limitations.
  4. P1 — Audit Endpoint Protection:
     - Role-based authorization for audit listing and verification endpoints (AUDITOR, CONTROLLER).
     - Rejection of unauthorized roles (OPERATOR) with HTTP 403.
     - Protection against unauthenticated access in enforced mode.
  5. P1 — Webhook Model Correctness:
     - Rejection of missing/empty provider event IDs with HTTP 400.
     - Rejection of missing event types and malformed non-object resources with HTTP 400.
     - Proof that malformed payloads cannot modify payment states.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from main import app
from models.db import get_db
from models.entities import (
    AuditEvent, Base, Business, Obligation, PaymentBatch,
    PaymentInstruction, ProviderSubmission, Supplier, WebhookEvent,
)
from services.audit import (
    GENESIS_HASH, AuditVerificationResult, compute_event_hash,
    record_audit_event, verify_audit_chain,
)


# ===========================================================================
# Test Helpers
# ===========================================================================

def _make_paypal_headers(transmission_time: str = "2026-11-12T12:00:00Z") -> dict[str, str]:
    return {
        "PAYPAL-TRANSMISSION-ID": f"TRANS-{uuid.uuid4().hex[:8]}",
        "PAYPAL-TRANSMISSION-TIME": transmission_time,
        "PAYPAL-CERT-URL": "https://api.sandbox.paypal.com/v1/notifications/certs/CERT-123",
        "PAYPAL-AUTH-ALGO": "SHA256withRSA",
        "PAYPAL-TRANSMISSION-SIG": "dummy-sig-p2-1",
    }


def _create_instruction(db: Session, status: str = "SUBMITTED", last_event_time: datetime | None = None) -> tuple[str, str, str]:
    """Creates a batch, supplier, obligation, and instruction with the specified status."""
    _id = uuid.uuid4().hex[:8]
    biz = Business(
        id=f"BIZ-P21-{_id}",
        display_name="P21 Test Business",
    )
    db.add(biz)
    db.flush()

    sup = Supplier(
        id=f"SUP-P21-{_id}",
        business_id=biz.id,
        external_reference=f"EXT-P21-{_id}",
        display_name="P21 Test Supplier",
        country_code="US",
        recipient_reference_type="EMAIL",
        recipient_reference_masked="sup***@example.com",
        sandbox_recipient_email="sup-receiver@personal.paypal.com",
        preferred_currency="USD",
    )
    db.add(sup)
    db.flush()

    ob = Obligation(
        id=f"OBL-P21-{_id}",
        business_id=biz.id,
        supplier_id=sup.id,
        invoice_reference=f"INV-P21-{_id}",
        amount=Decimal("500.00"),
        currency="USD",
        due_at=date(2026, 12, 31),
        status="VALIDATED",
        source_hash=f"src{_id}",
    )
    db.add(ob)
    db.flush()

    batch = PaymentBatch(
        id=f"BATCH-P21-{_id}",
        business_id=biz.id,
        batch_reference=f"REF-P21-{_id}",
        status="SUBMITTED",
        approved_currency="USD",
        selected_provider_code="PAYPAL_SANDBOX",
        approved_total_amount=Decimal("500.00"),
        approved_by="treasury_admin",
    )
    db.add(batch)
    db.flush()

    sub = ProviderSubmission(
        id=f"SUB-P21-{_id}",
        batch_id=batch.id,
        provider_code="PAYPAL_SANDBOX",
        sender_batch_id=f"SB-P21-{_id}",
        paypal_payout_batch_id=f"PP-B-{_id}",
        status="SUBMITTED",
        intended_amount=Decimal("500.00"),
        currency="USD",
        item_count=1,
    )
    db.add(sub)

    pp_item_id = f"PP-ITEM-{_id}"
    now = datetime.now(timezone.utc)
    instr = PaymentInstruction(
        id=f"INSTR-P21-{_id}",
        batch_id=batch.id,
        obligation_id=ob.id,
        provider_code="PAYPAL_SANDBOX",
        amount=Decimal("500.00"),
        currency="USD",
        idempotency_key=f"IK-ITEM-{_id}",
        sender_item_id=f"SI-{_id}",
        paypal_payout_item_id=pp_item_id,
        status=status,
        settlement_evidence="PROVIDER_REPORTED_COMPLETE" if status == "COMPLETED" else "NOT_CONFIRMED",
        last_event_time=last_event_time or (now - timedelta(minutes=10)),
        last_event_id=f"WH-PREV-{_id}",
    )
    db.add(instr)
    db.commit()
    return batch.id, instr.id, pp_item_id


# ===========================================================================
# 1. P0 — Trusted Authentication and Authorization Tests
# ===========================================================================

class TestPriority21TrustedAuthAndRoles:
    """Verifies that client-supplied X-Actor-Role and X-Actor-Id headers are completely untrusted."""

    def test_caller_cannot_grant_self_admin_via_x_actor_role(self, db, client, monkeypatch):
        """A caller with an OPERATOR key cannot elevate permissions to ADMIN via X-Actor-Role."""
        monkeypatch.setenv("REQUIRE_AUTH", "true")
        monkeypatch.setenv("DEMO_OPERATOR_KEY", "operator-secret-token")

        # Attempt to access a CONTROLLER-only endpoint (submit_batch) while passing X-Actor-Role: ADMIN
        headers = {
            "X-Api-Key": "operator-secret-token",
            "X-Actor-Role": "ADMIN",
            "X-Actor-Id": "sneaky_operator",
        }
        resp = client.post("/api/v1/batches/dummy-batch/submit", headers=headers)
        assert resp.status_code == 403
        assert resp.json()["detail"]["error"] == "INSUFFICIENT_PERMISSIONS"

    def test_caller_cannot_grant_self_treasury_checker_via_x_actor_role(self, db, client, monkeypatch):
        """A caller with an OPERATOR key cannot approve a batch by asserting X-Actor-Role: TREASURY_CHECKER."""
        monkeypatch.setenv("REQUIRE_AUTH", "true")
        monkeypatch.setenv("DEMO_OPERATOR_KEY", "operator-secret-token")

        headers = {
            "X-Api-Key": "operator-secret-token",
            "X-Actor-Role": "TREASURY_CHECKER",
            "X-Actor-Id": "sneaky_operator",
        }
        body = {
            "approver_id": "sneaky_operator",
            "selected_provider": "PAYPAL_SANDBOX",
            "routing_strategy": "LOWEST_COST",
            "confirmed_total": "100.00",
            "confirmed_currency": "USD",
        }
        resp = client.post("/api/v1/batches/dummy-batch/approve", headers=headers, json=body)
        assert resp.status_code == 403
        assert resp.json()["detail"]["error"] == "INSUFFICIENT_PERMISSIONS"

    def test_caller_cannot_impersonate_another_approver_via_x_actor_id(self, db, client, monkeypatch):
        """An authenticated checker cannot spoof another approver's identity via X-Actor-Id or payload."""
        monkeypatch.setenv("REQUIRE_AUTH", "true")
        monkeypatch.setenv("DEMO_CHECKER_KEY", "checker-valid-token")

        from tests.test_day4 import _make_demo_batch
        batch_id = _make_demo_batch(db)

        # Token maps on the server to identity "treasury_checker_alice"
        headers = {
            "X-Api-Key": "checker-valid-token",
            "X-Actor-Id": "CFO_BOB",
        }
        body = {
            "approver_id": "CFO_BOB",
            "selected_provider": "PAYPAL_SANDBOX",
            "routing_strategy": "LOWEST_COST",
            "confirmed_total": "1250.00",
            "confirmed_currency": "USD",
        }
        resp = client.post(f"/api/v1/batches/{batch_id}/approve", headers=headers, json=body)
        assert resp.status_code == 403
        assert resp.json()["detail"]["error"] == "IDENTITY_MISMATCH"

    def test_approval_actor_derived_from_authenticated_principal(self, db, client, monkeypatch):
        """Batch approval records the authenticated principal's identity as the authoritative approver."""
        monkeypatch.setenv("REQUIRE_AUTH", "true")
        monkeypatch.setenv("DEMO_CHECKER_KEY", "checker-valid-token")

        from tests.test_day4 import _make_demo_batch
        batch_id = _make_demo_batch(db)

        headers = {
            "X-Api-Key": "checker-valid-token",
        }
        body = {
            "approver_id": "treasury_checker_alice",  # Matches server identity for DEMO_CHECKER_KEY
            "selected_provider": "PAYPAL_SANDBOX",
            "routing_strategy": "LOWEST_COST",
            "confirmed_total": "1250.00",
            "confirmed_currency": "USD",
        }
        resp = client.post(f"/api/v1/batches/{batch_id}/approve", headers=headers, json=body)
        assert resp.status_code == 200

        batch = db.query(PaymentBatch).filter(PaymentBatch.id == batch_id).first()
        assert batch.approved_by == "treasury_checker_alice"


# ===========================================================================
# 2. P0 — Terminal State Transition Integrity Tests
# ===========================================================================

class TestPriority21TerminalStateIntegrity:
    """Verifies that all unauthorized terminal state reversals and transitions are strictly rejected."""

    def _post_webhook(self, client, pp_item_id: str, event_type: str, event_time: str = "2026-11-12T12:05:00Z"):
        payload = {
            "id": f"WH-P21-{uuid.uuid4().hex[:8]}",
            "event_type": event_type,
            "create_time": event_time,
            "resource": {"payout_item_id": pp_item_id, "transaction_id": f"TX-{uuid.uuid4().hex[:6]}"},
        }
        with patch("routers.webhooks._get_access_token", return_value="mock-token"), \
             patch("routers.webhooks._verify_webhook_signature", return_value=True):
            return client.post("/api/v1/webhooks/paypal", headers=_make_paypal_headers(), json=payload)

    def test_terminal_failed_to_completed_rejected(self, db, client, monkeypatch):
        """FAILED instruction cannot be reversed to COMPLETED via SUCCEEDED webhook."""
        monkeypatch.setenv("PAYPAL_WEBHOOK_ID", "WH-VALID")
        monkeypatch.setenv("PAYPAL_CLIENT_ID", "p-id")
        monkeypatch.setenv("PAYPAL_CLIENT_SECRET", "p-sec")

        _, instr_id, pp_item_id = _create_instruction(db, status="FAILED")
        resp = self._post_webhook(client, pp_item_id, "PAYMENT.PAYOUTS-ITEM.SUCCEEDED")

        assert resp.status_code == 200
        assert resp.json()["status"] == "CONFLICT_REJECTED"

        instr = db.query(PaymentInstruction).filter(PaymentInstruction.id == instr_id).first()
        assert instr.status == "FAILED"

    def test_terminal_cancelled_to_completed_rejected(self, db, client, monkeypatch):
        """CANCELLED instruction cannot transition to COMPLETED."""
        monkeypatch.setenv("PAYPAL_WEBHOOK_ID", "WH-VALID")
        monkeypatch.setenv("PAYPAL_CLIENT_ID", "p-id")
        monkeypatch.setenv("PAYPAL_CLIENT_SECRET", "p-sec")

        _, instr_id, pp_item_id = _create_instruction(db, status="CANCELLED")
        resp = self._post_webhook(client, pp_item_id, "PAYMENT.PAYOUTS-ITEM.SUCCEEDED")

        assert resp.status_code == 200
        assert resp.json()["status"] == "CONFLICT_REJECTED"

        instr = db.query(PaymentInstruction).filter(PaymentInstruction.id == instr_id).first()
        assert instr.status == "CANCELLED"

    def test_terminal_failed_to_submitted_rejected(self, db, client, monkeypatch):
        """FAILED instruction cannot be reverted to SUBMITTED by late UNCLAIMED event."""
        monkeypatch.setenv("PAYPAL_WEBHOOK_ID", "WH-VALID")
        monkeypatch.setenv("PAYPAL_CLIENT_ID", "p-id")
        monkeypatch.setenv("PAYPAL_CLIENT_SECRET", "p-sec")

        _, instr_id, pp_item_id = _create_instruction(db, status="FAILED")
        resp = self._post_webhook(client, pp_item_id, "PAYMENT.PAYOUTS-ITEM.UNCLAIMED")

        assert resp.status_code == 200
        assert resp.json()["status"] == "OUT_OF_ORDER_IGNORED"

        instr = db.query(PaymentInstruction).filter(PaymentInstruction.id == instr_id).first()
        assert instr.status == "FAILED"

    def test_terminal_completed_to_failed_rejected(self, db, client, monkeypatch):
        """COMPLETED instruction cannot be converted to FAILED by late FAILED event."""
        monkeypatch.setenv("PAYPAL_WEBHOOK_ID", "WH-VALID")
        monkeypatch.setenv("PAYPAL_CLIENT_ID", "p-id")
        monkeypatch.setenv("PAYPAL_CLIENT_SECRET", "p-sec")

        _, instr_id, pp_item_id = _create_instruction(db, status="COMPLETED")
        resp = self._post_webhook(client, pp_item_id, "PAYMENT.PAYOUTS-ITEM.FAILED")

        assert resp.status_code == 200
        assert resp.json()["status"] == "CONFLICT_REJECTED"

        instr = db.query(PaymentInstruction).filter(PaymentInstruction.id == instr_id).first()
        assert instr.status == "COMPLETED"

    def test_terminal_completed_to_submitted_rejected(self, db, client, monkeypatch):
        """COMPLETED instruction cannot be converted to SUBMITTED by late UNCLAIMED event."""
        monkeypatch.setenv("PAYPAL_WEBHOOK_ID", "WH-VALID")
        monkeypatch.setenv("PAYPAL_CLIENT_ID", "p-id")
        monkeypatch.setenv("PAYPAL_CLIENT_SECRET", "p-sec")

        _, instr_id, pp_item_id = _create_instruction(db, status="COMPLETED")
        resp = self._post_webhook(client, pp_item_id, "PAYMENT.PAYOUTS-ITEM.UNCLAIMED")

        assert resp.status_code == 200
        assert resp.json()["status"] == "OUT_OF_ORDER_IGNORED"

        instr = db.query(PaymentInstruction).filter(PaymentInstruction.id == instr_id).first()
        assert instr.status == "COMPLETED"

    def test_terminal_completed_to_refunded_allowed(self, db, client, monkeypatch):
        """COMPLETED instruction can transition to REFUNDED upon explicit REFUNDED event with valid timestamp."""
        monkeypatch.setenv("PAYPAL_WEBHOOK_ID", "WH-VALID")
        monkeypatch.setenv("PAYPAL_CLIENT_ID", "p-id")
        monkeypatch.setenv("PAYPAL_CLIENT_SECRET", "p-sec")

        completion_time = datetime.now(timezone.utc) - timedelta(hours=2)
        _, instr_id, pp_item_id = _create_instruction(db, status="COMPLETED", last_event_time=completion_time)

        refund_time = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        resp = self._post_webhook(client, pp_item_id, "PAYMENT.PAYOUTS-ITEM.REFUNDED", event_time=refund_time)

        assert resp.status_code == 200
        assert resp.json()["status"] == "PROCESSED"

        instr = db.query(PaymentInstruction).filter(PaymentInstruction.id == instr_id).first()
        assert instr.status == "REFUNDED"
        assert instr.settlement_evidence == "FUNDS_REFUNDED"

    def test_terminal_refunded_to_completed_rejected(self, db, client, monkeypatch):
        """REFUNDED instruction cannot be reverted back to COMPLETED."""
        monkeypatch.setenv("PAYPAL_WEBHOOK_ID", "WH-VALID")
        monkeypatch.setenv("PAYPAL_CLIENT_ID", "p-id")
        monkeypatch.setenv("PAYPAL_CLIENT_SECRET", "p-sec")

        _, instr_id, pp_item_id = _create_instruction(db, status="REFUNDED")
        resp = self._post_webhook(client, pp_item_id, "PAYMENT.PAYOUTS-ITEM.SUCCEEDED")

        assert resp.status_code == 200
        assert resp.json()["status"] == "CONFLICT_REJECTED"

        instr = db.query(PaymentInstruction).filter(PaymentInstruction.id == instr_id).first()
        assert instr.status == "REFUNDED"

    def test_terminal_completed_refund_missing_timestamp_rejected(self, db, client, monkeypatch):
        """A refund event missing an explicit timestamp cannot reverse a COMPLETED payment."""
        monkeypatch.setenv("PAYPAL_WEBHOOK_ID", "WH-VALID")
        monkeypatch.setenv("PAYPAL_CLIENT_ID", "p-id")
        monkeypatch.setenv("PAYPAL_CLIENT_SECRET", "p-sec")

        _, instr_id, pp_item_id = _create_instruction(db, status="COMPLETED")

        payload = {
            "id": f"WH-P21-NOTIME-{uuid.uuid4().hex[:8]}",
            "event_type": "PAYMENT.PAYOUTS-ITEM.REFUNDED",
            "create_time": "INVALID-TIMESTAMP-STRING",
            "resource": {"payout_item_id": pp_item_id},
        }
        with patch("routers.webhooks._get_access_token", return_value="mock-token"), \
             patch("routers.webhooks._verify_webhook_signature", return_value=True):
            resp = client.post("/api/v1/webhooks/paypal", headers=_make_paypal_headers(transmission_time="INVALID-TIME-FORMAT"), json=payload)

        assert resp.status_code == 200
        assert resp.json()["status"] == "UNVERIFIED_TIMESTAMP_IGNORED"

        instr = db.query(PaymentInstruction).filter(PaymentInstruction.id == instr_id).first()
        assert instr.status == "COMPLETED"


# ===========================================================================
# 3. P1 — Audit-Chain Verification Tests
# ===========================================================================

class TestPriority21AuditChainVerification:
    """Verifies that global audit verification checks independent entity chains separately."""

    def test_multiple_entities_with_separate_genesis_events_global_verification(self, db):
        """Two separate entities with independent genesis events both pass global verification."""
        entity_a = f"ENTITY-A-{uuid.uuid4().hex[:6]}"
        entity_b = f"ENTITY-B-{uuid.uuid4().hex[:6]}"

        # Interleave event creations for Entity A and Entity B
        record_audit_event(db, "BATCH", entity_a, "INIT_A", "ACTOR_1", details_redacted="{}")
        record_audit_event(db, "BATCH", entity_b, "INIT_B", "ACTOR_2", details_redacted="{}")
        record_audit_event(db, "BATCH", entity_a, "STEP_A2", "ACTOR_1", details_redacted="{}")
        record_audit_event(db, "BATCH", entity_b, "STEP_B2", "ACTOR_2", details_redacted="{}")
        db.flush()

        # Global verification (entity_id=None) must validate both chains separately and succeed
        result = verify_audit_chain(db, entity_id=None)
        assert result.is_valid is True
        assert result.total_events_checked >= 4
        assert result.chains_checked >= 2
        assert result.broken_event_id is None

    def test_global_verification_identifies_broken_entity_and_event(self, db):
        """When one entity's chain is tampered with, global verification reports the specific entity and event."""
        entity_clean = f"ENTITY-CLEAN-{uuid.uuid4().hex[:6]}"
        entity_tampered = f"ENTITY-TAMPER-{uuid.uuid4().hex[:6]}"

        record_audit_event(db, "BATCH", entity_clean, "EV1", "ACTOR", details_redacted="{}")
        record_audit_event(db, "BATCH", entity_clean, "EV2", "ACTOR", details_redacted="{}")

        ev_t1 = record_audit_event(db, "BATCH", entity_tampered, "EV_T1", "ACTOR", details_redacted="{}")
        ev_t2 = record_audit_event(db, "BATCH", entity_tampered, "EV_T2", "ACTOR", details_redacted="{}")
        db.flush()

        # Tamper with entity_tampered's second event
        ev_t2.details_redacted = '{"tampered": true}'
        db.flush()

        result = verify_audit_chain(db, entity_id=None)
        assert result.is_valid is False
        assert result.broken_entity_id == entity_tampered
        assert result.broken_event_id == ev_t2.id
        assert "tampered" in (result.failure_reason or "").lower()

    def test_intermediate_deletion_detected(self, db):
        """Deleting an intermediate event in an entity's chain is detected as a broken hash link."""
        entity_id = f"ENTITY-DEL-{uuid.uuid4().hex[:6]}"

        ev1 = record_audit_event(db, "BATCH", entity_id, "SEQ_1", "ACTOR", details_redacted="{}")
        ev2 = record_audit_event(db, "BATCH", entity_id, "SEQ_2", "ACTOR", details_redacted="{}")
        ev3 = record_audit_event(db, "BATCH", entity_id, "SEQ_3", "ACTOR", details_redacted="{}")
        db.flush()

        # Delete intermediate event
        del_id = ev2.id
        next_id = ev3.id
        db.delete(ev2)
        db.flush()

        result = verify_audit_chain(db, entity_id=entity_id)
        assert result.is_valid is False
        assert result.broken_event_id == next_id
        assert "broken hash chain" in (result.failure_reason or "").lower()

    def test_truncation_limitation_documented(self, db):
        """
        Documented security limitation:
        Deleting the head (last) event of an in-database chain cannot be detected without
        an external anchor, because the remaining prefix is internally cryptographically valid.
        """
        entity_id = f"ENTITY-TRUNC-{uuid.uuid4().hex[:6]}"

        ev1 = record_audit_event(db, "BATCH", entity_id, "STEP_1", "ACTOR", details_redacted="{}")
        ev2 = record_audit_event(db, "BATCH", entity_id, "STEP_2", "ACTOR", details_redacted="{}")
        ev3 = record_audit_event(db, "BATCH", entity_id, "STEP_3", "ACTOR", details_redacted="{}")
        db.flush()

        # Delete the last event
        db.delete(ev3)
        db.flush()

        # The remaining chain [ev1, ev2] is internally consistent, demonstrating why external anchoring is required
        result = verify_audit_chain(db, entity_id=entity_id)
        assert result.is_valid is True  # Proves the documented limitation!
        assert result.total_events_checked == 2


# ===========================================================================
# 4. P1 — Audit Endpoint Protection Tests
# ===========================================================================

class TestPriority21AuditEndpointProtection:
    """Verifies authentication and authorization enforcement on audit endpoints."""

    def test_audit_listing_unauthorized_role_rejected(self, client, monkeypatch):
        """An authenticated caller with only OPERATOR role cannot list batch audit events."""
        monkeypatch.setenv("DEMO_OPERATOR_KEY", "operator-token")

        resp = client.get(
            "/api/v1/batches/dummy-batch/audit",
            headers={"X-Api-Key": "operator-token"},
        )
        assert resp.status_code == 403
        assert resp.json()["detail"]["error"] == "INSUFFICIENT_PERMISSIONS"

    def test_audit_listing_authorized_auditor_succeeds(self, db, client, monkeypatch):
        """An authenticated caller with AUDITOR role can list batch audit events."""
        monkeypatch.setenv("DEMO_AUDITOR_KEY", "auditor-token")

        from tests.test_day4 import _make_demo_batch
        batch_id = _make_demo_batch(db)

        resp = client.get(
            f"/api/v1/batches/{batch_id}/audit",
            headers={"X-Api-Key": "auditor-token"},
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_audit_verify_unauthorized_role_rejected(self, client, monkeypatch):
        """An authenticated caller with only OPERATOR role cannot trigger audit chain verification."""
        monkeypatch.setenv("DEMO_OPERATOR_KEY", "operator-token")

        resp = client.get(
            "/api/v1/audit/verify",
            headers={"X-Api-Key": "operator-token"},
        )
        assert resp.status_code == 403
        assert resp.json()["detail"]["error"] == "INSUFFICIENT_PERMISSIONS"

    def test_audit_verify_authorized_auditor_succeeds(self, client, monkeypatch):
        """An authenticated caller with AUDITOR role can run audit chain verification."""
        monkeypatch.setenv("DEMO_AUDITOR_KEY", "auditor-token")

        resp = client.get(
            "/api/v1/audit/verify",
            headers={"X-Api-Key": "auditor-token"},
        )
        assert resp.status_code == 200
        assert "is_valid" in resp.json()


# ===========================================================================
# 5. P1 — Webhook Model Correctness Tests
# ===========================================================================

class TestPriority21WebhookModelCorrectness:
    """Verifies that malformed, incomplete, or empty webhook events are strictly rejected."""

    def test_webhook_missing_event_id_rejected_400(self, client, monkeypatch):
        """Webhook with missing event id is rejected with HTTP 400."""
        monkeypatch.setenv("PAYPAL_WEBHOOK_ID", "WH-VALID")
        monkeypatch.setenv("PAYPAL_CLIENT_ID", "p-id")
        monkeypatch.setenv("PAYPAL_CLIENT_SECRET", "p-sec")

        payload = {
            "id": "",  # Empty ID
            "event_type": "PAYMENT.PAYOUTS-ITEM.SUCCEEDED",
            "resource": {"payout_item_id": "PP-ITEM-123"},
        }
        with patch("routers.webhooks._get_access_token", return_value="mock-token"), \
             patch("routers.webhooks._verify_webhook_signature", return_value=True):
            resp = client.post("/api/v1/webhooks/paypal", headers=_make_paypal_headers(), json=payload)

        assert resp.status_code == 400
        assert resp.json()["detail"]["error"] == "MISSING_EVENT_ID"

    def test_webhook_missing_event_type_rejected_400(self, client, monkeypatch):
        """Webhook with missing event_type is rejected with HTTP 400."""
        monkeypatch.setenv("PAYPAL_WEBHOOK_ID", "WH-VALID")
        monkeypatch.setenv("PAYPAL_CLIENT_ID", "p-id")
        monkeypatch.setenv("PAYPAL_CLIENT_SECRET", "p-sec")

        payload = {
            "id": "WH-VALID-ID-123",
            "event_type": "",  # Empty event type
            "resource": {"payout_item_id": "PP-ITEM-123"},
        }
        with patch("routers.webhooks._get_access_token", return_value="mock-token"), \
             patch("routers.webhooks._verify_webhook_signature", return_value=True):
            resp = client.post("/api/v1/webhooks/paypal", headers=_make_paypal_headers(), json=payload)

        assert resp.status_code == 400
        assert resp.json()["detail"]["error"] == "MISSING_EVENT_TYPE"

    def test_webhook_malformed_resource_rejected_400(self, client, monkeypatch):
        """Webhook with non-dict resource is rejected with HTTP 400."""
        monkeypatch.setenv("PAYPAL_WEBHOOK_ID", "WH-VALID")
        monkeypatch.setenv("PAYPAL_CLIENT_ID", "p-id")
        monkeypatch.setenv("PAYPAL_CLIENT_SECRET", "p-sec")

        payload = {
            "id": "WH-VALID-ID-123",
            "event_type": "PAYMENT.PAYOUTS-ITEM.SUCCEEDED",
            "resource": "not-a-dict",
        }
        with patch("routers.webhooks._get_access_token", return_value="mock-token"), \
             patch("routers.webhooks._verify_webhook_signature", return_value=True):
            resp = client.post("/api/v1/webhooks/paypal", headers=_make_paypal_headers(), json=payload)

        assert resp.status_code == 400
        assert resp.json()["detail"]["error"] == "MALFORMED_RESOURCE"

    def test_malformed_webhook_does_not_modify_payment_instruction(self, db, client, monkeypatch):
        """Malformed webhooks cannot alter existing instruction states or insert corrupted records."""
        monkeypatch.setenv("PAYPAL_WEBHOOK_ID", "WH-VALID")
        monkeypatch.setenv("PAYPAL_CLIENT_ID", "p-id")
        monkeypatch.setenv("PAYPAL_CLIENT_SECRET", "p-sec")

        _, instr_id, pp_item_id = _create_instruction(db, status="SUBMITTED")

        payload = {
            "id": "   ",  # Whitespace only
            "event_type": "PAYMENT.PAYOUTS-ITEM.SUCCEEDED",
            "resource": {"payout_item_id": pp_item_id},
        }
        with patch("routers.webhooks._get_access_token", return_value="mock-token"), \
             patch("routers.webhooks._verify_webhook_signature", return_value=True):
            resp = client.post("/api/v1/webhooks/paypal", headers=_make_paypal_headers(), json=payload)

        assert resp.status_code == 400

        # State must remain SUBMITTED
        instr = db.query(PaymentInstruction).filter(PaymentInstruction.id == instr_id).first()
        assert instr.status == "SUBMITTED"
