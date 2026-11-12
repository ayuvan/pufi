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
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.db import get_db
from models.entities import (
    ActiveBatchSubmission, AuditEvent, PaymentBatch,
    PaymentInstruction, ProviderSubmission, WebhookEvent,
)
from services.audit import record_audit_event

logger = logging.getLogger("pufi.webhooks")

router = APIRouter()

PAYPAL_SANDBOX_BASE = "https://api-m.sandbox.paypal.com"

# Map PayPal webhook event types to (instruction_status, settlement_evidence, is_refund_or_reversal)
_EVENT_TYPE_MAP: dict[str, tuple[str, str, bool]] = {
    "PAYMENT.PAYOUTS-ITEM.SUCCEEDED":  ("COMPLETED",  "PROVIDER_REPORTED_COMPLETE", False),
    "PAYMENT.PAYOUTS-ITEM.FAILED":     ("FAILED",     "NOT_CONFIRMED",             False),
    "PAYMENT.PAYOUTS-ITEM.BLOCKED":    ("FAILED",     "NOT_CONFIRMED",             False),
    "PAYMENT.PAYOUTS-ITEM.DENIED":     ("FAILED",     "NOT_CONFIRMED",             False),
    "PAYMENT.PAYOUTS-ITEM.UNCLAIMED":  ("SUBMITTED",  "NOT_CONFIRMED",             False),
    "PAYMENT.PAYOUTS-ITEM.REFUNDED":   ("REFUNDED",   "FUNDS_REFUNDED",            True),
    "PAYMENT.PAYOUTS-ITEM.RETURNED":   ("REFUNDED",   "FUNDS_RETURNED",            True),
    "PAYMENT.PAYOUTS-ITEM.REVERSED":   ("REVERSED",   "FUNDS_REVERSED",            True),
}

# ===========================================================================
# Explicit State Transition Matrix (Priority 2.1)
# ===========================================================================

TERMINAL_STATUSES: frozenset[str] = frozenset({"COMPLETED", "FAILED", "CANCELLED", "REFUNDED", "REVERSED"})
REFUND_EVENT_TYPES: frozenset[str] = frozenset({
    "PAYMENT.PAYOUTS-ITEM.REFUNDED",
    "PAYMENT.PAYOUTS-ITEM.RETURNED",
    "PAYMENT.PAYOUTS-ITEM.REVERSED",
})

# Allowed forward transitions: current_status -> set of allowable target statuses
ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "CREATED": frozenset({"APPROVED", "CANCELLED"}),
    "APPROVED": frozenset({"SUBMISSION_PENDING", "CANCELLED"}),
    "SUBMISSION_PENDING": frozenset({"SUBMITTED", "UNKNOWN", "FAILED"}),
    "SUBMITTED": frozenset({"COMPLETED", "FAILED", "UNKNOWN", "SUBMITTED"}),
    "UNKNOWN": frozenset({"SUBMITTED", "COMPLETED", "FAILED", "UNKNOWN"}),
    # Terminal states: COMPLETED can only transition to REFUNDED or REVERSED via explicit refund events.
    "COMPLETED": frozenset({"REFUNDED", "REVERSED"}),
    # Strictly terminal states: NO outward transitions allowed under any circumstances.
    "FAILED": frozenset(),
    "CANCELLED": frozenset(),
    "REFUNDED": frozenset(),
    "REVERSED": frozenset(),
}


def _parse_event_datetime(raw: Optional[str]) -> Optional[datetime]:
    """Parse an ISO 8601 provider timestamp into an explicit UTC datetime."""
    if not raw:
        return None
    try:
        dt_str = raw.replace("Z", "+00:00")
        dt = datetime.fromisoformat(dt_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


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
        raise HTTPException(status_code=400, detail={"error": "INVALID_JSON", "message": "Webhook payload must be valid JSON."})

    if not isinstance(event, dict):
        raise HTTPException(status_code=400, detail={"error": "MALFORMED_EVENT", "message": "Webhook payload must be a JSON object."})

    event_id = event.get("id")
    if not event_id or not isinstance(event_id, str) or not event_id.strip():
        logger.warning("Webhook rejected: missing or empty event id.")
        raise HTTPException(status_code=400, detail={"error": "MISSING_EVENT_ID", "message": "Event payload must contain a non-empty string 'id'."})
    event_id = event_id.strip()

    event_type = event.get("event_type")
    if not event_type or not isinstance(event_type, str) or not event_type.strip():
        logger.warning("Webhook rejected: missing or empty event_type.")
        raise HTTPException(status_code=400, detail={"error": "MISSING_EVENT_TYPE", "message": "Event payload must contain a non-empty string 'event_type'."})
    event_type = event_type.strip()

    resource = event.get("resource")
    if not isinstance(resource, dict):
        logger.warning("Webhook rejected: resource must be a JSON object.")
        raise HTTPException(status_code=400, detail={"error": "MALFORMED_RESOURCE", "message": "Event 'resource' must be a JSON object."})

    now = datetime.now(timezone.utc)
    raw_event_time = (
        event.get("create_time")
        or resource.get("time_processed")
        or resource.get("time_updated")
        or transmission_time
    )
    parsed_event_time = _parse_event_datetime(raw_event_time)

    # --- Priority 2.0: Database-level Webhook Deduplication ---
    # 1. Pre-query WebhookEvent table
    existing_webhook = (
        db.query(WebhookEvent)
        .filter(
            WebhookEvent.provider == "PAYPAL",
            WebhookEvent.provider_event_id == event_id,
        )
        .first()
    )
    if existing_webhook:
        logger.info("Webhook duplicate ignored via database uniqueness: event_id=%s", event_id)
        return {
            "status": "DUPLICATE_IGNORED",
            "event_id": event_id,
            "recorded_status": existing_webhook.status,
            "message": "Duplicate webhook event previously received and ignored.",
        }

    # 2. Insert WebhookEvent record and flush to enforce DB UNIQUE constraint
    redacted_event = {k: v for k, v in event.items() if k not in ("client_secret", "access_token")}
    resource_id = (
        resource.get("payout_item_id")
        or resource.get("payout_batch_id")
        or resource.get("payout_item", {}).get("payout_item_id")
        or event_id
    )

    webhook_record = WebhookEvent(
        provider="PAYPAL",
        provider_event_id=event_id,
        event_type=event_type,
        resource_type=event.get("resource_type", "payouts_item"),
        resource_id=resource_id,
        event_time=parsed_event_time,
        transmission_id=transmission_id,
        status="RECEIVED",
        payload_json=json.dumps(redacted_event),
        headers_json=json.dumps({
            "transmission_id": transmission_id,
            "transmission_time": transmission_time,
            "cert_url": cert_url,
            "auth_algo": auth_algo,
        }),
        created_at=now,
    )
    db.add(webhook_record)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        logger.info("Simultaneous duplicate webhook caught by database UNIQUE constraint: event_id=%s", event_id)
        return {
            "status": "DUPLICATE_IGNORED",
            "event_id": event_id,
            "message": "Simultaneous duplicate webhook caught by database constraint.",
        }

    # --- Record raw event in AuditEvent with cryptographic hash chaining ---
    event_id_hash = hashlib.sha256(event_id.encode()).hexdigest() if event_id else ""
    record_audit_event(
        db=db,
        entity_type="WEBHOOK",
        entity_id=event_id or "unknown",
        event_type=event_type,
        actor="PAYPAL_WEBHOOK",
        correlation_id=event_id_hash,
        details_redacted=json.dumps({
            "event_type": event_type,
            "transmission_id": transmission_id,
            "event_time": parsed_event_time.isoformat() if parsed_event_time else None,
            "verified": True,
        }),
    )

    # --- Process known event types ---
    new_status, settlement_evidence, is_refund_or_reversal = _EVENT_TYPE_MAP.get(event_type, (None, None, False))

    if new_status:
        payout_item_id = resource.get("payout_item_id") or resource.get("payout_item", {}).get("payout_item_id")
        sender_item_id = resource.get("payout_item", {}).get("sender_item_id")
        transaction_id = resource.get("transaction_id")
        payout_batch_id = resource.get("payout_batch_id")

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
            current_status = instruction.status

            # Rule 1: Duplicate event for identical status
            if current_status == new_status:
                logger.info(
                    "Duplicate status event ignored: instruction %s already in status %s",
                    instruction.id, current_status,
                )
                webhook_record.status = "IGNORED_DUPLICATE_TERMINAL" if current_status in TERMINAL_STATUSES else "DUPLICATE_IGNORED"
                webhook_record.processed_at = now
                db.commit()
                return {
                    "status": "DUPLICATE_IGNORED",
                    "event_id": event_id,
                    "instruction_id": instruction.id,
                    "reason": f"Instruction already in status {current_status}",
                }

            # Rule 2: Strictly Terminal States (FAILED, CANCELLED, REFUNDED, REVERSED)
            # These states have NO outward transitions permitted under any circumstances.
            if current_status in ("FAILED", "CANCELLED", "REFUNDED", "REVERSED"):
                if new_status == "COMPLETED":
                    logger.warning(
                        "Unauthorized terminal reversal rejected: event %s attempted to transition %s instruction %s to COMPLETED",
                        event_id, current_status, instruction.id,
                    )
                    record_audit_event(
                        db=db,
                        entity_type="INSTRUCTION",
                        entity_id=instruction.id,
                        event_type="WEBHOOK_CONFLICT_REJECTED",
                        actor="PAYPAL_WEBHOOK",
                        correlation_id=event_id_hash,
                        details_redacted=json.dumps({
                            "event_type": event_type,
                            "current_status": current_status,
                            "attempted_status": new_status,
                            "reason": f"Unauthorized terminal reversal: {current_status} cannot be reversed to COMPLETED",
                        }),
                    )
                    webhook_record.status = "REJECTED_CONFLICT"
                    webhook_record.processed_at = now
                    db.commit()
                    return {
                        "status": "CONFLICT_REJECTED",
                        "event_id": event_id,
                        "instruction_id": instruction.id,
                        "error": f"Unauthorized terminal reversal: cannot transition {current_status} to COMPLETED",
                    }
                elif new_status in ("SUBMITTED", "UNKNOWN", "APPROVED"):
                    logger.info(
                        "State precedence enforced: ignoring late non-terminal event %s for %s instruction %s",
                        event_type, current_status, instruction.id,
                    )
                    record_audit_event(
                        db=db,
                        entity_type="INSTRUCTION",
                        entity_id=instruction.id,
                        event_type="WEBHOOK_OUT_OF_ORDER_IGNORED",
                        actor="PAYPAL_WEBHOOK",
                        correlation_id=event_id_hash,
                        details_redacted=json.dumps({
                            "event_type": event_type,
                            "current_status": current_status,
                            "attempted_status": new_status,
                            "reason": f"Terminal status {current_status} cannot be reverted by non-terminal event",
                        }),
                    )
                    webhook_record.status = "IGNORED_STALE"
                    webhook_record.processed_at = now
                    db.commit()
                    return {
                        "status": "OUT_OF_ORDER_IGNORED",
                        "event_id": event_id,
                        "instruction_id": instruction.id,
                        "reason": f"Terminal status {current_status} cannot be reverted by non-terminal event",
                    }
                else:
                    logger.warning(
                        "Conflicting terminal status update rejected: %s instruction %s cannot transition to %s",
                        current_status, instruction.id, new_status,
                    )
                    record_audit_event(
                        db=db,
                        entity_type="INSTRUCTION",
                        entity_id=instruction.id,
                        event_type="WEBHOOK_CONFLICT_REJECTED",
                        actor="PAYPAL_WEBHOOK",
                        correlation_id=event_id_hash,
                        details_redacted=json.dumps({
                            "event_type": event_type,
                            "current_status": current_status,
                            "attempted_status": new_status,
                            "reason": f"Conflicting terminal transition: cannot change {current_status} to {new_status}",
                        }),
                    )
                    webhook_record.status = "REJECTED_CONFLICT"
                    webhook_record.processed_at = now
                    db.commit()
                    return {
                        "status": "CONFLICT_REJECTED",
                        "event_id": event_id,
                        "instruction_id": instruction.id,
                        "error": f"Conflicting terminal status update rejected: cannot change {current_status} to {new_status}",
                    }

            # Rule 3: COMPLETED State
            # Can ONLY transition to REFUNDED or REVERSED via explicit refund/reversal events.
            if current_status == "COMPLETED":
                if is_refund_or_reversal and new_status in ("REFUNDED", "REVERSED"):
                    # Legitimate refund/reversal path: require verified timestamp
                    if not parsed_event_time:
                        logger.warning(
                            "Refund event rejected: unverified or missing timestamp for COMPLETED instruction %s",
                            instruction.id,
                        )
                        record_audit_event(
                            db=db,
                            entity_type="INSTRUCTION",
                            entity_id=instruction.id,
                            event_type="WEBHOOK_UNVERIFIED_TIMESTAMP_IGNORED",
                            actor="PAYPAL_WEBHOOK",
                            correlation_id=event_id_hash,
                            details_redacted=json.dumps({
                                "event_type": event_type,
                                "current_status": current_status,
                                "attempted_status": new_status,
                                "reason": "Missing or invalid event timestamp; cannot reverse settled payment without verified ordering",
                            }),
                        )
                        webhook_record.status = "UNVERIFIED_TIMESTAMP_IGNORED"
                        webhook_record.processed_at = now
                        db.commit()
                        return {
                            "status": "UNVERIFIED_TIMESTAMP_IGNORED",
                            "event_id": event_id,
                            "instruction_id": instruction.id,
                            "reason": "Missing or unverified timestamp cannot reverse settled payment",
                        }

                    # Check timestamp staleness against last_event_time
                    if instruction.last_event_time:
                        last_t = instruction.last_event_time
                        ev_t = parsed_event_time
                        if last_t.tzinfo is None:
                            last_t = last_t.replace(tzinfo=timezone.utc)
                        if ev_t.tzinfo is None:
                            ev_t = ev_t.replace(tzinfo=timezone.utc)
                        if ev_t < last_t:
                            logger.info("Stale refund event ignored: timestamp older than last_event_time")
                            record_audit_event(
                                db=db,
                                entity_type="INSTRUCTION",
                                entity_id=instruction.id,
                                event_type="WEBHOOK_STALE_EVENT_IGNORED",
                                actor="PAYPAL_WEBHOOK",
                                correlation_id=event_id_hash,
                                details_redacted=json.dumps({
                                    "event_type": event_type,
                                    "current_status": current_status,
                                    "attempted_status": new_status,
                                }),
                            )
                            webhook_record.status = "IGNORED_STALE"
                            webhook_record.processed_at = now
                            db.commit()
                            return {
                                "status": "STALE_EVENT_IGNORED",
                                "event_id": event_id,
                                "instruction_id": instruction.id,
                                "reason": "Refund event timestamp is older than last applied update",
                            }

                    # Valid forward refund/reversal: proceed to update
                    logger.info("Applying legitimate refund/reversal event %s to COMPLETED instruction %s", event_type, instruction.id)
                else:
                    # Non-refund events cannot alter COMPLETED payments
                    if new_status in ("FAILED", "BLOCKED", "DENIED"):
                        logger.warning(
                            "Conflicting terminal update rejected: event %s attempted to transition COMPLETED instruction %s to %s without refund",
                            event_id, instruction.id, new_status,
                        )
                        record_audit_event(
                            db=db,
                            entity_type="INSTRUCTION",
                            entity_id=instruction.id,
                            event_type="WEBHOOK_CONFLICT_REJECTED",
                            actor="PAYPAL_WEBHOOK",
                            correlation_id=event_id_hash,
                            details_redacted=json.dumps({
                                "event_type": event_type,
                                "current_status": current_status,
                                "attempted_status": new_status,
                                "reason": "Cannot transition COMPLETED instruction to FAILED without explicit refund/reversal event",
                            }),
                        )
                        webhook_record.status = "REJECTED_CONFLICT"
                        webhook_record.processed_at = now
                        db.commit()
                        return {
                            "status": "CONFLICT_REJECTED",
                            "event_id": event_id,
                            "instruction_id": instruction.id,
                            "error": "Conflicting terminal state update rejected",
                        }
                    else:
                        logger.info(
                            "State precedence enforced: ignoring late event %s for already COMPLETED instruction %s",
                            event_type, instruction.id,
                        )
                        record_audit_event(
                            db=db,
                            entity_type="INSTRUCTION",
                            entity_id=instruction.id,
                            event_type="WEBHOOK_OUT_OF_ORDER_IGNORED",
                            actor="PAYPAL_WEBHOOK",
                            correlation_id=event_id_hash,
                            details_redacted=json.dumps({
                                "event_type": event_type,
                                "current_status": current_status,
                                "attempted_status": new_status,
                                "reason": "Terminal status cannot be reverted by non-terminal event",
                            }),
                        )
                        webhook_record.status = "IGNORED_STALE"
                        webhook_record.processed_at = now
                        db.commit()
                        return {
                            "status": "OUT_OF_ORDER_IGNORED",
                            "event_id": event_id,
                            "instruction_id": instruction.id,
                            "reason": "Terminal status cannot be reverted by non-terminal event",
                        }

            # Rule 4: Non-Terminal States (CREATED, APPROVED, SUBMISSION_PENDING, SUBMITTED, UNKNOWN)
            if current_status not in TERMINAL_STATUSES:
                allowed_targets = ALLOWED_TRANSITIONS.get(current_status, frozenset())
                if new_status not in allowed_targets:
                    logger.warning(
                        "Disallowed transition from %s to %s for instruction %s",
                        current_status, new_status, instruction.id,
                    )
                    record_audit_event(
                        db=db,
                        entity_type="INSTRUCTION",
                        entity_id=instruction.id,
                        event_type="WEBHOOK_CONFLICT_REJECTED",
                        actor="PAYPAL_WEBHOOK",
                        correlation_id=event_id_hash,
                        details_redacted=json.dumps({
                            "event_type": event_type,
                            "current_status": current_status,
                            "attempted_status": new_status,
                            "reason": f"Disallowed transition from {current_status} to {new_status}",
                        }),
                    )
                    webhook_record.status = "REJECTED_CONFLICT"
                    webhook_record.processed_at = now
                    db.commit()
                    return {
                        "status": "CONFLICT_REJECTED",
                        "event_id": event_id,
                        "instruction_id": instruction.id,
                        "error": f"Disallowed state transition from {current_status} to {new_status}",
                    }

                # Check timestamp ordering
                if instruction.last_event_time and parsed_event_time:
                    last_time = instruction.last_event_time
                    ev_time = parsed_event_time
                    if last_time.tzinfo is None and ev_time.tzinfo is not None:
                        last_time = last_time.replace(tzinfo=timezone.utc)
                    elif last_time.tzinfo is not None and ev_time.tzinfo is None:
                        ev_time = ev_time.replace(tzinfo=timezone.utc)

                    if ev_time < last_time:
                        logger.info(
                            "Stale webhook ignored: event %s timestamp %s is older than instruction last_event_time %s",
                            event_id, ev_time.isoformat(), last_time.isoformat(),
                        )
                        record_audit_event(
                            db=db,
                            entity_type="INSTRUCTION",
                            entity_id=instruction.id,
                            event_type="WEBHOOK_STALE_EVENT_IGNORED",
                            actor="PAYPAL_WEBHOOK",
                            correlation_id=event_id_hash,
                            details_redacted=json.dumps({
                                "event_type": event_type,
                                "event_time": ev_time.isoformat(),
                                "last_event_time": last_time.isoformat(),
                                "current_status": instruction.status,
                                "attempted_status": new_status,
                            }),
                        )
                        webhook_record.status = "IGNORED_STALE"
                        webhook_record.processed_at = now
                        db.commit()
                        return {
                            "status": "STALE_EVENT_IGNORED",
                            "event_id": event_id,
                            "instruction_id": instruction.id,
                            "reason": f"Event time ({ev_time}) is older than last applied update ({last_time})",
                        }

            # 5. Apply state transition
            instruction.status = new_status
            instruction.settlement_evidence = settlement_evidence
            instruction.paypal_item_status = event_type.split(".")[-1]
            if transaction_id:
                instruction.paypal_transaction_id = transaction_id
            if payout_item_id and not instruction.paypal_payout_item_id:
                instruction.paypal_payout_item_id = payout_item_id
            instruction.last_event_time = parsed_event_time or now
            instruction.last_event_id = event_id
            instruction.updated_at = now

            # Correlate and update associated ProviderSubmission
            submission = (
                db.query(ProviderSubmission)
                .filter(ProviderSubmission.batch_id == instruction.batch_id)
                .order_by(ProviderSubmission.created_at.desc())
                .first()
            )
            if submission:
                if payout_batch_id and not submission.paypal_payout_batch_id:
                    submission.paypal_payout_batch_id = payout_batch_id
                if submission.status == "UNKNOWN":
                    submission.status = "SUBMITTED"

            # Re-evaluate associated PaymentBatch status across all instructions
            batch = db.query(PaymentBatch).filter(PaymentBatch.id == instruction.batch_id).first()
            if batch:
                all_instrs = (
                    db.query(PaymentInstruction)
                    .filter(PaymentInstruction.batch_id == batch.id)
                    .all()
                )
                total = len(all_instrs)
                completed_count = sum(1 for i in all_instrs if i.status == "COMPLETED")
                failed_count = sum(1 for i in all_instrs if i.status in ("FAILED", "CANCELLED"))
                refunded_count = sum(1 for i in all_instrs if i.status in ("REFUNDED", "REVERSED"))
                unresolved_count = sum(1 for i in all_instrs if i.status in ("UNKNOWN", "SUBMITTED", "PENDING", "APPROVED", "SUBMISSION_PENDING", "CREATED"))

                if unresolved_count == 0:
                    if completed_count == total:
                        batch.status = "COMPLETED"
                    elif refunded_count == total:
                        batch.status = "REVERSED"
                    elif failed_count == total:
                        batch.status = "FAILED"
                    else:
                        batch.status = "PARTIALLY_COMPLETED"
                    # Remove ActiveBatchSubmission lock if batch has reached terminal state
                    db.query(ActiveBatchSubmission).filter(ActiveBatchSubmission.batch_id == batch.id).delete()

                if total > 0:
                    if completed_count == total:
                        batch.status = "COMPLETED"
                    elif failed_count == total:
                        batch.status = "FAILED"
                    elif completed_count > 0 and failed_count > 0:
                        batch.status = "PARTIALLY_COMPLETED"
                    elif unresolved_count > 0:
                        batch.status = "SUBMITTED"

                if batch.status in ("COMPLETED", "FAILED", "PARTIALLY_COMPLETED"):
                    db.query(ActiveBatchSubmission).filter(ActiveBatchSubmission.batch_id == batch.id).delete()

            record_audit_event(
                db=db,
                entity_type="INSTRUCTION",
                entity_id=instruction.id,
                event_type="WEBHOOK_RECONCILIATION_APPLIED",
                actor="PAYPAL_WEBHOOK",
                correlation_id=event_id_hash,
                details_redacted=json.dumps({
                    "event_type": event_type,
                    "instruction_status": instruction.status,
                    "batch_status": batch.status if batch else None,
                    "payout_item_id": payout_item_id,
                }),
            )
            logger.info(
                "Webhook applied: event=%s instruction=%s new_status=%s batch_status=%s",
                event_type, instruction.id, new_status, batch.status if batch else "None",
            )
        else:
            logger.info("Webhook event %s: no matching instruction found.", event_type)

    elif event_type.startswith("PAYMENT.PAYOUTSBATCH."):
        # Handle batch-level events
        batch_header = resource.get("batch_header", {})
        payout_batch_id = batch_header.get("payout_batch_id") or resource.get("payout_batch_id")
        sender_batch_id = batch_header.get("sender_batch_header", {}).get("sender_batch_id")

        submission = None
        if payout_batch_id:
            submission = (
                db.query(ProviderSubmission)
                .filter(ProviderSubmission.paypal_payout_batch_id == payout_batch_id)
                .first()
            )
        if not submission and sender_batch_id:
            submission = (
                db.query(ProviderSubmission)
                .filter(ProviderSubmission.sender_batch_id == sender_batch_id)
                .first()
            )

        if submission:
            batch = db.query(PaymentBatch).filter(PaymentBatch.id == submission.batch_id).first()
            if event_type == "PAYMENT.PAYOUTSBATCH.SUCCESS":
                submission.paypal_batch_status = "SUCCESS"
                if submission.status == "UNKNOWN":
                    submission.status = "SUBMITTED"
            elif event_type == "PAYMENT.PAYOUTSBATCH.DENIED":
                submission.paypal_batch_status = "DENIED"
                submission.status = "FAILED"
                if batch:
                    batch.status = "FAILED"
                    db.query(ActiveBatchSubmission).filter(ActiveBatchSubmission.batch_id == batch.id).delete()

            record_audit_event(
                db=db,
                entity_type="BATCH",
                entity_id=submission.batch_id,
                event_type="WEBHOOK_BATCH_STATUS_APPLIED",
                actor="PAYPAL_WEBHOOK",
                correlation_id=event_id_hash,
                details_redacted=json.dumps({
                    "event_type": event_type,
                    "paypal_batch_status": submission.paypal_batch_status,
                }),
            )
            logger.info("Batch-level webhook applied: event=%s batch=%s", event_type, submission.batch_id)
    else:
        logger.info("Webhook event %s: unhandled type, acknowledged.", event_type)

    webhook_record.status = "PROCESSED"
    webhook_record.processed_at = now
    db.commit()
    return {"status": "PROCESSED", "event_id": event_id, "event_type": event_type}
