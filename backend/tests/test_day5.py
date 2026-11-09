"""
PUFI — Day 5 tests: Access Control, Webhook Receiver, and Audit Trail.
"""
from unittest.mock import patch

import pytest
from httpx import Client

from models.entities import AuditEvent, PaymentInstruction


class TestDay5AccessControl:
    """Task 5: Minimal API-key access control for approve and submit."""

    def test_approve_bypassed_when_no_api_key_env(self, client: Client, monkeypatch):
        monkeypatch.delenv("DEMO_API_KEY", raising=False)
        # Calling without header should proceed (404/422 on nonexistent batch, NOT 403)
        res = client.post(
            "/api/v1/batches/nonexistent-id/approve",
            json={
                "approver_id": "TEST_USER",
                "selected_provider": "PAYPAL_SANDBOX",
                "routing_strategy": "LOWEST_COST",
                "confirmed_total": "100.00",
                "confirmed_currency": "USD",
            },
        )
        assert res.status_code != 403

    def test_approve_enforced_when_api_key_set(self, client: Client, monkeypatch):
        monkeypatch.setenv("DEMO_API_KEY", "secret-test-key")

        # Without header -> 403
        res = client.post(
            "/api/v1/batches/nonexistent-id/approve",
            json={
                "approver_id": "TEST_USER",
                "selected_provider": "PAYPAL_SANDBOX",
                "routing_strategy": "LOWEST_COST",
                "confirmed_total": "100.00",
                "confirmed_currency": "USD",
            },
        )
        assert res.status_code == 403
        data = res.json()
        assert data["detail"]["error"] == "FORBIDDEN"

        # With wrong header -> 403
        res_wrong = client.post(
            "/api/v1/batches/nonexistent-id/approve",
            headers={"X-Api-Key": "wrong-key"},
            json={
                "approver_id": "TEST_USER",
                "selected_provider": "PAYPAL_SANDBOX",
                "routing_strategy": "LOWEST_COST",
                "confirmed_total": "100.00",
                "confirmed_currency": "USD",
            },
        )
        assert res_wrong.status_code == 403

        # With correct header -> proceeds past auth check (not 403)
        res_ok = client.post(
            "/api/v1/batches/nonexistent-id/approve",
            headers={"X-Api-Key": "secret-test-key"},
            json={
                "approver_id": "TEST_USER",
                "selected_provider": "PAYPAL_SANDBOX",
                "routing_strategy": "LOWEST_COST",
                "confirmed_total": "100.00",
                "confirmed_currency": "USD",
            },
        )
        assert res_ok.status_code != 403

    def test_submit_enforced_when_api_key_set(self, client: Client, monkeypatch):
        monkeypatch.setenv("DEMO_API_KEY", "secret-test-key")

        res = client.post("/api/v1/batches/nonexistent-id/submit")
        assert res.status_code == 403

        res_ok = client.post(
            "/api/v1/batches/nonexistent-id/submit",
            headers={"X-Api-Key": "secret-test-key"},
        )
        assert res_ok.status_code != 403


class TestDay5Webhooks:
    """Task 4: PayPal Webhook receiver and verification."""

    def test_webhook_rejected_when_not_configured(self, client: Client, monkeypatch):
        monkeypatch.delenv("PAYPAL_WEBHOOK_ID", raising=False)
        res = client.post(
            "/api/v1/webhooks/paypal",
            json={"id": "WH-123", "event_type": "PAYMENT.PAYOUTS-ITEM.SUCCEEDED"},
        )
        assert res.status_code == 503
        assert res.json()["detail"]["error"] == "WEBHOOK_NOT_CONFIGURED"

    def test_webhook_rejected_when_headers_missing(self, client: Client, monkeypatch):
        monkeypatch.setenv("PAYPAL_WEBHOOK_ID", "WH-TEST-ID")
        res = client.post(
            "/api/v1/webhooks/paypal",
            json={"id": "WH-123", "event_type": "PAYMENT.PAYOUTS-ITEM.SUCCEEDED"},
        )
        assert res.status_code == 400
        assert res.json()["detail"]["error"] == "MISSING_HEADERS"

    def test_webhook_rejected_when_signature_invalid(self, client: Client, monkeypatch):
        monkeypatch.setenv("PAYPAL_WEBHOOK_ID", "WH-TEST-ID")
        monkeypatch.setenv("PAYPAL_CLIENT_ID", "client-id")
        monkeypatch.setenv("PAYPAL_CLIENT_SECRET", "client-secret")

        headers = {
            "PAYPAL-TRANSMISSION-ID": "trans-123",
            "PAYPAL-TRANSMISSION-TIME": "2026-11-09T12:00:00Z",
            "PAYPAL-CERT-URL": "https://api.sandbox.paypal.com/cert.pem",
            "PAYPAL-AUTH-ALGO": "SHA256withRSA",
            "PAYPAL-TRANSMISSION-SIG": "bad-signature",
        }

        with patch("routers.webhooks._get_access_token", return_value="mock-token"), \
             patch("routers.webhooks._verify_webhook_signature", return_value=False):
            res = client.post(
                "/api/v1/webhooks/paypal",
                headers=headers,
                json={"id": "WH-123", "event_type": "PAYMENT.PAYOUTS-ITEM.SUCCEEDED"},
            )
            assert res.status_code == 400
            assert res.json()["detail"]["error"] == "INVALID_SIGNATURE"

    def test_webhook_processed_and_idempotent(self, client: Client, monkeypatch):
        monkeypatch.setenv("PAYPAL_WEBHOOK_ID", "WH-TEST-ID")
        monkeypatch.setenv("PAYPAL_CLIENT_ID", "client-id")
        monkeypatch.setenv("PAYPAL_CLIENT_SECRET", "client-secret")

        headers = {
            "PAYPAL-TRANSMISSION-ID": "trans-456",
            "PAYPAL-TRANSMISSION-TIME": "2026-11-09T12:00:00Z",
            "PAYPAL-CERT-URL": "https://api.sandbox.paypal.com/cert.pem",
            "PAYPAL-AUTH-ALGO": "SHA256withRSA",
            "PAYPAL-TRANSMISSION-SIG": "valid-sig",
        }

        payload = {
            "id": "WH-EVENT-999",
            "event_type": "PAYMENT.PAYOUTS-ITEM.SUCCEEDED",
            "resource": {
                "payout_item_id": "ITEM-999",
                "transaction_id": "TXN-999",
            },
        }

        with patch("routers.webhooks._get_access_token", return_value="mock-token"), \
             patch("routers.webhooks._verify_webhook_signature", return_value=True):
            # 1. First delivery -> processed
            res = client.post("/api/v1/webhooks/paypal", headers=headers, json=payload)
            assert res.status_code == 200
            assert res.json()["status"] == "PROCESSED"

            # 2. Duplicate delivery -> silently ignored
            res2 = client.post("/api/v1/webhooks/paypal", headers=headers, json=payload)
            assert res2.status_code == 200
            assert res2.json()["status"] == "DUPLICATE_IGNORED"
