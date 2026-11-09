"""
PUFI — PayPal Webhook receiver (Day 5).

Receives and verifies incoming PayPal webhook events.

SECURITY RULES:
  1. Every incoming webhook is verified using PayPal's documented
     verification mechanism before any state is updated.
  2. Duplicate events (same event_id) are silently acknowledged (idempotent).
  3. Unrecognised event types are logged and acknowledged but ignored.
  4. Webhook status updates do NOT override manual refresh; they supplement it.
  5. No PayPal credentials are returned in any response.

LIMITATIONS (documented):
  - PayPal Sandbox webhook delivery requires a publicly reachable HTTPS URL.
  - For local development, use ngrok or a similar tunnel.
  - If PAYPAL_WEBHOOK_ID is not set, signature verification is SKIPPED and
    the endpoint rejects all incoming webhooks with 503 (not configured).
  - This is a minimal prototype implementation, not production hardening.

PAYPAL VERIFICATION ENDPOINT (official documentation):
  POST https://api-m.sandbox.paypal.com/v1/notifications/verify-webhook-signature
  Reference: https://developer.paypal.com/api/rest/webhooks/

EVENT TYPES HANDLED:
  PAYMENT.PAYOUTS-ITEM.SUCCEEDED  → instruction COMPLETED
  PAYMENT.PAYOUTS-ITEM.FAILED     → instruction FAILED
  PAYMENT.PAYOUTS-ITEM.BLOCKED    → instruction FAILED
  PAYMENT.PAYOUTS-ITEM.REFUNDED   → instruction FAILED
  PAYMENT.PAYOUTS-ITEM.RETURNED   → instruction FAILED
  PAYMENT.PAYOUTS-ITEM.UNCLAIMED  → instruction SUBMITTED (not settled)
  PAYMENT.PAYOUTS-ITEM.DENIED     → instruction FAILED

POLLING ALTERNATIVE:
  If webhooks are unavailable (e.g. local development without a tunnel),
  use POST /api/v1/batches/{batch_id}/refresh-status to poll PayPal
  for updated batch and item statuses.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

import requests
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from models.db import get_db
from models.entities import AuditEvent, PaymentInstruction

logger = logging.getLogger("pufi.webhooks")

router = APIRouter()

PAYPAL_SANDBOX_BASE = "https://api-m.sandbox.paypal.com"

# Map PayPal webhook event types to PUFI instruction status
_EVENT_TYPE_MAP: dict[str, tuple[str, str]] = {
    "PAYMENT.PAYOUTS-ITEM.SUCCEEDED":  ("COMPLETED",  "PROVIDER_REPORTED_COMPLETE"),
    "PAYMENT.PAYOUTS-ITEM.FAILED":     ("FAILED",     "NOT_CONFIRMED"),
    "PAYMENT.PAYOUTS-ITEM.BLOCKED":    ("FAILED",     "NOT_CONFIRMED"),
    "PAYMENT.PAYOUTS-ITEM.REFUNDED":   ("FAILED",     "NOT_CONFIRMED"),
    "PAYMENT.PAYOUTS-ITEM.RETURNED":   ("FAILED",     "NOT_CONFIRMED"),
    "PAYMENT.PAYOUTS-ITEM.DENIED":     ("FAILED",     "NOT_CONFIRMED"),
    "PAYMENT.PAYOUTS-ITEM.UNCLAIMED":  ("SUBMITTED",  "NOT_CONFIRMED"),
}


def _get_access_token() -> Optional[str]:
    """Get a fresh PayPal OAuth2 token for webhook verification."""
    client_id = os.getenv("PAYPAL_CLIENT_ID", "").strip()
    client_secret = os.getenv("PAYPAL_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        return None
    try:
        resp = requests.post(
            f"{PAYPAL_SANDBOX_BASE}/v1/oauth2/token",
            auth=(client_id, client_secret),
            data={"grant_type": "client_credentials"},
            timeout=10,
        )
        if resp.status_code == 200:
            return resp.json().get("access_token")
    except Exception as exc:
        logger.warning("PayPal token fetch failed: %s", exc)
    return None


def _verify_webhook_signature(
    *,
    transmission_id: str,
    transmission_time: str,
    cert_url: str,
    auth_algo: str,
    transmission_sig: str,
    webhook_id: str,
    raw_body: bytes,
    access_token: str,
) -> bool:
    """
    Verify the webhook signature using PayPal's verify-webhook-signature API.
    Returns True if PayPal reports SUCCESS, False otherwise.

    Reference:
      POST /v1/notifications/verify-webhook-signature
      https://developer.paypal.com/api/rest/webhooks/
    """
    try:
        payload = json.loads(raw_body)
    except Exception:
        return False

    try:
        resp = requests.post(
            f"{PAYPAL_SANDBOX_BASE}/v1/notifications/verify-webhook-signature",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {access_token}",
            },
            json={
                "transmission_id": transmission_id,
                "transmission_time": transmission_time,
                "cert_url": cert_url,
                "auth_algo": auth_algo,
                "transmission_sig": transmission_sig,
                "webhook_id": webhook_id,
                "webhook_event": payload,
            },
            timeout=10,
        )
        if resp.status_code == 200:
            verification_status = resp.json().get("verification_status", "")
            return verification_status == "SUCCESS"
    except Exception as exc:
        logger.warning("Webhook signature verification call failed: %s", exc)
    return False


@router.post(
    "/webhooks/paypal",
    summary="PayPal webhook receiver",
    description=(
        "Receives PayPal payout webhook events. "
        "Verifies signature using PayPal's documented verification API before any state update. "
        "Requires PAYPAL_WEBHOOK_ID in environment. "
        "Returns 200 to acknowledge; never returns 4xx/5xx for valid but unhandled events. "
        "SANDBOX ONLY."
    ),
    status_code=200,
)
async def receive_paypal_webhook(
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    """
    PayPal webhook receiver.

    Verification steps (all required before state changes):
    1. PAYPAL_WEBHOOK_ID must be configured.
    2. Required PayPal headers must be present.
    3. Signature verified via PayPal's verify-webhook-signature API.
    4. Event ID checked for duplicate processing.
    """
    webhook_id = os.getenv("PAYPAL_WEBHOOK_ID", "").strip()
    if not webhook_id:
        # Webhook not configured — reject with 503 so PayPal retries later
        raise HTTPException(
            status_code=503,
            detail={
                "error": "WEBHOOK_NOT_CONFIGURED",
                "message": (
                    "PAYPAL_WEBHOOK_ID is not set. Configure it in .env. "
                    "Use POST /batches/{id}/refresh-status as a polling alternative."
                ),
            },
        )

    raw_body = await request.body()

    # --- Required PayPal signature headers ---
    transmission_id  = request.headers.get("PAYPAL-TRANSMISSION-ID", "")
    transmission_time = request.headers.get("PAYPAL-TRANSMISSION-TIME", "")
    cert_url         = request.headers.get("PAYPAL-CERT-URL", "")
    auth_algo        = request.headers.get("PAYPAL-AUTH-ALGO", "")
    transmission_sig = request.headers.get("PAYPAL-TRANSMISSION-SIG", "")

    if not all([transmission_id, transmission_time, cert_url, auth_algo, transmission_sig]):
        logger.warning("Webhook rejected: missing PayPal signature headers.")
        raise HTTPException(
            status_code=400,
            detail={"error": "MISSING_HEADERS", "message": "Required PayPal signature headers are absent."},
        )

    # --- Get access token for verification call ---
    access_token = _get_access_token()
    if not access_token:
        logger.warning("Webhook rejected: could not obtain PayPal access token for verification.")
        raise HTTPException(
            status_code=503,
            detail={"error": "VERIFICATION_UNAVAILABLE", "message": "Cannot verify webhook: PayPal credentials not configured."},
        )

    # --- Verify signature ---
    verified = _verify_webhook_signature(
        transmission_id=transmission_id,
        transmission_time=transmission_time,
        cert_url=cert_url,
        auth_algo=auth_algo,
        transmission_sig=transmission_sig,
        webhook_id=webhook_id,
        raw_body=raw_body,
        access_token=access_token,
    )

    if not verified:
        logger.warning(
            "Webhook REJECTED — signature verification failed. "
            "transmission_id=%s", transmission_id
        )
        raise HTTPException(
            status_code=400,
            detail={"error": "INVALID_SIGNATURE", "message": "Webhook signature verification failed."},
        )

    # --- Parse event ---
    try:
        event = json.loads(raw_body)
    except Exception:
        raise HTTPException(status_code=400, detail={"error": "INVALID_JSON"})

    event_id   = event.get("id", "")
    event_type = event.get("event_type", "")

    # --- Idempotency: reject duplicate event IDs ---
    event_id_hash = hashlib.sha256(event_id.encode()).hexdigest() if event_id else ""
    existing = (
        db.query(AuditEvent)
        .filter(
            AuditEvent.entity_type == "WEBHOOK",
            AuditEvent.correlation_id == event_id_hash,
        )
        .first()
    )
    if existing:
        logger.info("Webhook duplicate ignored: event_id=%s", event_id)
        return {"status": "DUPLICATE_IGNORED", "event_id": event_id}

    # --- Record raw event ---
    now = datetime.now(timezone.utc)
    db.add(AuditEvent(
        entity_type="WEBHOOK",
        entity_id=event_id or "unknown",
        event_type=event_type,
        actor="PAYPAL_WEBHOOK",
        correlation_id=event_id_hash,
        details_redacted=json.dumps({
            "event_type": event_type,
            "transmission_id": transmission_id,
            "verified": True,
        }),
    ))

    # --- Process known event types ---
    new_status, settlement_evidence = _EVENT_TYPE_MAP.get(event_type, (None, None))

    if new_status:
        # Extract payout_item_id from event resource
        resource = event.get("resource", {})
        payout_item_id = resource.get("payout_item_id") or resource.get("payout_item", {}).get("payout_item_id")
        sender_item_id = resource.get("payout_item", {}).get("sender_item_id")
        transaction_id = resource.get("transaction_id")

        instruction = None
        if payout_item_id:
            instruction = (
                db.query(PaymentInstruction)
                .filter(PaymentInstruction.paypal_payout_item_id == payout_item_id)
                .first()
            )
        if not instruction and sender_item_id:
            instruction = (
                db.query(PaymentInstruction)
                .filter(PaymentInstruction.sender_item_id == sender_item_id)
                .first()
            )

        if instruction:
            instruction.status = new_status
            instruction.settlement_evidence = settlement_evidence
            instruction.paypal_item_status = event_type.split(".")[-1]
            if transaction_id:
                instruction.paypal_transaction_id = transaction_id
            instruction.updated_at = now
            logger.info(
                "Webhook applied: event=%s instruction=%s new_status=%s",
                event_type, instruction.id, new_status,
            )
        else:
            logger.info("Webhook event %s: no matching instruction found.", event_type)
    else:
        logger.info("Webhook event %s: unhandled type, acknowledged.", event_type)

    db.commit()
    return {"status": "PROCESSED", "event_id": event_id, "event_type": event_type}
