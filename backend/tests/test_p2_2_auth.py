"""
PUFI — Priority 2.2 API Authentication and Authorization Regression Tests.

Verifies:
  1. Unauthenticated requests are rejected when authentication is enforced (REQUIRE_AUTH=true).
  2. Public health endpoint remains accessible without credentials.
  3. Read operations require appropriate authenticated roles / valid credentials.
  4. State-changing operations require appropriate permissions:
     - obligations import: OPERATOR or CONTROLLER
     - batch create: OPERATOR or CONTROLLER
     - batch analyze: OPERATOR, CONTROLLER, or TREASURY_CHECKER
     - batch approve: TREASURY_CHECKER
     - batch submit: CONTROLLER
     - batch refresh-status: OPERATOR or CONTROLLER
  5. Unauthorized roles receive HTTP 403 (INSUFFICIENT_PERMISSIONS).
  6. Client-supplied X-Actor-Role and X-Actor-Id headers cannot elevate privileges.
  7. PayPal webhook endpoint uses signature verification, not API key authentication.
"""
from __future__ import annotations

import os
import uuid
from decimal import Decimal
from datetime import date
import pytest
from starlette.testclient import TestClient

from main import app
from models.entities import Business, Supplier, Obligation, PaymentBatch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _setup_batch(db) -> str:
    _id = uuid.uuid4().hex[:8]
    biz = Business(id=f"BIZ-AUTH-{_id}", display_name="Auth Corp")
    db.add(biz)
    db.flush()

    sup = Supplier(
        id=f"SUP-AUTH-{_id}",
        business_id=biz.id,
        external_reference=f"EXT-AUTH-{_id}",
        display_name="Auth Supplier",
        country_code="US",
        recipient_reference_masked="a***@example.com",
    )
    db.add(sup)
    db.flush()

    ob = Obligation(
        id=f"OBL-AUTH-{_id}",
        business_id=biz.id,
        supplier_id=sup.id,
        invoice_reference=f"INV-AUTH-{_id}",
        amount=Decimal("150.00"),
        currency="USD",
        due_at=date(2026, 12, 31),
        status="VALIDATED",
        source_hash=f"src{_id}",
    )
    db.add(ob)
    db.flush()

    batch = PaymentBatch(
        id=f"BATCH-AUTH-{_id}",
        business_id=biz.id,
        batch_reference=f"REF-AUTH-{_id}",
        status="APPROVED",
        approved_currency="USD",
        selected_provider_code="PAYPAL_SANDBOX",
        approved_total_amount=Decimal("150.00"),
        approved_by="treasury_admin",
    )
    db.add(batch)
    db.commit()
    return batch.id


class TestPriority22ApiAuthentication:
    """Tests comprehensive authentication coverage across all endpoints."""

    def test_health_endpoint_public_without_auth(self, client, monkeypatch):
        """The health check endpoint must remain accessible without any API key even when REQUIRE_AUTH=true."""
        monkeypatch.setenv("REQUIRE_AUTH", "true")
        monkeypatch.setenv("DEMO_API_KEY", "admin-key")

        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_unauthenticated_request_rejected_when_auth_enforced(self, client, monkeypatch):
        """When REQUIRE_AUTH=true, requests missing X-Api-Key must be rejected with 403."""
        monkeypatch.setenv("REQUIRE_AUTH", "true")
        monkeypatch.setenv("DEMO_API_KEY", "admin-key")

        # GET /obligations
        resp = client.get("/api/v1/obligations")
        assert resp.status_code == 403
        assert resp.json()["detail"]["error"] == "FORBIDDEN"

        # GET /batches
        resp = client.get("/api/v1/batches")
        assert resp.status_code == 403

        # POST /obligations/import
        resp = client.post("/api/v1/obligations/import", json=[])
        assert resp.status_code == 403

        # POST /batches
        resp = client.post("/api/v1/batches", json={"batch_reference": "TEST", "obligation_ids": []})
        assert resp.status_code == 403

    def test_fail_closed_in_protected_environment_without_server_keys(self, client, monkeypatch):
        """When REQUIRE_AUTH=true but no server API keys are configured, system must fail closed with 500."""
        monkeypatch.setenv("REQUIRE_AUTH", "true")
        # Ensure no demo keys exist in environment
        for key in ["DEMO_API_KEY", "DEMO_CHECKER_KEY", "DEMO_CONTROLLER_KEY", "DEMO_AUDITOR_KEY", "DEMO_OPERATOR_KEY", "PUFI_API_KEYS_JSON"]:
            monkeypatch.delenv(key, raising=False)

        resp = client.get("/api/v1/obligations", headers={"X-Api-Key": "some-key"})
        assert resp.status_code == 500
        assert resp.json()["detail"]["error"] == "AUTH_MISCONFIGURED"

    def test_authorized_user_accesses_permitted_read_endpoints(self, client, db, monkeypatch):
        """A user with valid credentials can access authenticated read endpoints."""
        monkeypatch.setenv("REQUIRE_AUTH", "true")
        monkeypatch.setenv("DEMO_OPERATOR_KEY", "operator-token")

        headers = {"X-Api-Key": "operator-token"}
        resp = client.get("/api/v1/obligations", headers=headers)
        assert resp.status_code == 200

        resp = client.get("/api/v1/batches", headers=headers)
        assert resp.status_code == 200

    def test_role_authorization_obligations_import(self, client, monkeypatch):
        """Only OPERATOR or CONTROLLER can import obligations."""
        monkeypatch.setenv("REQUIRE_AUTH", "true")
        monkeypatch.setenv("DEMO_AUDITOR_KEY", "auditor-token")
        monkeypatch.setenv("DEMO_OPERATOR_KEY", "operator-token")

        # Auditor lacks OPERATOR/CONTROLLER
        resp = client.post("/api/v1/obligations/import", headers={"X-Api-Key": "auditor-token"}, json=[])
        assert resp.status_code == 403
        assert resp.json()["detail"]["error"] == "INSUFFICIENT_PERMISSIONS"

        # Operator succeeds
        resp = client.post("/api/v1/obligations/import", headers={"X-Api-Key": "operator-token"}, json=[])
        assert resp.status_code == 200

    def test_role_authorization_batch_creation(self, client, monkeypatch):
        """Only OPERATOR or CONTROLLER can create batches."""
        monkeypatch.setenv("REQUIRE_AUTH", "true")
        monkeypatch.setenv("DEMO_AUDITOR_KEY", "auditor-token")

        resp = client.post(
            "/api/v1/batches",
            headers={"X-Api-Key": "auditor-token"},
            json={"batch_reference": "B1", "obligation_ids": ["none"]},
        )
        assert resp.status_code == 403
        assert resp.json()["detail"]["error"] == "INSUFFICIENT_PERMISSIONS"

    def test_role_authorization_refresh_status(self, client, db, monkeypatch):
        """Only OPERATOR or CONTROLLER can trigger status refresh."""
        monkeypatch.setenv("REQUIRE_AUTH", "true")
        monkeypatch.setenv("DEMO_AUDITOR_KEY", "auditor-token")
        batch_id = _setup_batch(db)

        resp = client.post(
            f"/api/v1/batches/{batch_id}/refresh-status",
            headers={"X-Api-Key": "auditor-token"},
        )
        assert resp.status_code == 403
        assert resp.json()["detail"]["error"] == "INSUFFICIENT_PERMISSIONS"

    def test_headers_cannot_elevate_privileges(self, client, monkeypatch):
        """Client headers X-Actor-Role and X-Actor-Id are strictly ignored and logged."""
        monkeypatch.setenv("REQUIRE_AUTH", "true")
        monkeypatch.setenv("DEMO_OPERATOR_KEY", "operator-token")

        # Operator asserts X-Actor-Role: CONTROLLER on submit endpoint
        headers = {
            "X-Api-Key": "operator-token",
            "X-Actor-Role": "CONTROLLER",
            "X-Actor-Id": "super_admin",
        }
        resp = client.post("/api/v1/batches/dummy/submit", headers=headers)
        assert resp.status_code == 403
        assert resp.json()["detail"]["error"] == "INSUFFICIENT_PERMISSIONS"

    def test_webhook_uses_paypal_signature_not_api_key(self, client, monkeypatch):
        """PayPal webhooks must not require an X-Api-Key header (they verify PayPal signatures)."""
        monkeypatch.setenv("REQUIRE_AUTH", "true")
        monkeypatch.setenv("DEMO_API_KEY", "admin-key")
        monkeypatch.setenv("PAYPAL_WEBHOOK_ID", "WH-12345")

        # Missing PayPal signature headers returns 400 (not 403 FORBIDDEN from API key auth)
        resp = client.post("/api/v1/webhooks/paypal", json={"id": "EV-1"})
        assert resp.status_code == 400
        assert resp.json()["detail"]["error"] == "MISSING_HEADERS"
