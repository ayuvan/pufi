"""
PUFI — PayPal Sandbox adapter (Day 4).

SECURITY RULES:
  - PAYPAL_MODE must be "sandbox" — no production mode is accepted.
  - client_secret is NEVER logged, stored in DB, or returned to the frontend.
  - Access tokens are cached in memory only; never persisted.
  - On timeout: set status=UNKNOWN; query provider before any retry.
  - Only USD is used (INR payout NOT assumed or supported here).

DISCLOSURES:
  - Payouts API access is account-gated; adapter returns is_configured=False
    if credentials are absent, allowing the rest of the system to function.
  - All test coverage uses mocked HTTP responses; no live API dependency.
  - Ref: https://developer.paypal.com/docs/payouts/standard/
  - Ref: https://developer.paypal.com/api/payments.payouts-batch/v1/
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

logger = logging.getLogger("pufi.paypal_adapter")

# ---------------------------------------------------------------------------
# PayPal Sandbox constants
# ---------------------------------------------------------------------------

PAYPAL_SANDBOX_BASE = "https://api-m.sandbox.paypal.com"
PAYPAL_OAUTH_URL = f"{PAYPAL_SANDBOX_BASE}/v1/oauth2/token"
PAYPAL_PAYOUTS_URL = f"{PAYPAL_SANDBOX_BASE}/v1/payments/payouts"
PAYPAL_PAYOUTS_GET_URL = f"{PAYPAL_SANDBOX_BASE}/v1/payments/payouts/{{payout_batch_id}}"

# Only USD is documented and verified for PayPal Payouts sandbox.
SUPPORTED_CURRENCIES: frozenset[str] = frozenset({"USD"})
REQUEST_TIMEOUT_SECONDS = 30


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class PayoutItem:
    """One recipient in a PayPal payout batch."""
    sender_item_id: str        # stable per-instruction reference
    receiver_email: str        # PayPal sandbox test account email
    amount_value: str          # Decimal string e.g. "500.00"
    currency: str              # must be "USD" for sandbox
    note: str = "PUFI Sandbox Test [SYNTHETIC DATA]"


@dataclass
class PayPalSubmitResult:
    """Result of POST /v1/payments/payouts."""
    success: bool
    sender_batch_id: str
    paypal_payout_batch_id: Optional[str] = None
    paypal_batch_status: Optional[str] = None
    # Sanitized HTTP status and error info (no credentials)
    http_status: Optional[int] = None
    error_message: Optional[str] = None
    is_simulated: bool = False   # True if adapter was not configured


@dataclass
class PayoutItemStatus:
    """Status of one item from GET /v1/payments/payouts/{id}."""
    sender_item_id: str
    payout_item_id: Optional[str]
    transaction_id: Optional[str]
    item_status: str              # PayPal item status string
    error_message: Optional[str]


@dataclass
class PayPalBatchStatusResult:
    """Result of GET /v1/payments/payouts/{payout_batch_id}."""
    success: bool
    paypal_payout_batch_id: str
    paypal_batch_status: Optional[str] = None
    items: list[PayoutItemStatus] = field(default_factory=list)
    error_message: Optional[str] = None


# ---------------------------------------------------------------------------
# Token cache (in-memory only; never persisted)
# ---------------------------------------------------------------------------

_cached_token: Optional[str] = None
_token_expires_at: Optional[datetime] = None


def _clear_token_cache() -> None:
    """Clear the in-memory token cache (used in tests)."""
    global _cached_token, _token_expires_at
    _cached_token = None
    _token_expires_at = None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def is_configured() -> bool:
    """
    Return True only if all required PayPal environment variables are present
    AND PAYPAL_MODE is exactly 'sandbox'.

    This allows the rest of the system to work without PayPal credentials by
    checking is_configured() before making API calls.
    """
    mode = os.getenv("PAYPAL_MODE", "").strip().lower()
    client_id = os.getenv("PAYPAL_CLIENT_ID", "").strip()
    client_secret = os.getenv("PAYPAL_CLIENT_SECRET", "").strip()
    return mode == "sandbox" and bool(client_id) and bool(client_secret)


def _get_access_token() -> str:
    """
    Obtain a PayPal OAuth 2.0 access token using client credentials.

    Token is cached in memory and reused until 60 seconds before expiry.
    The client_secret is NEVER logged.
    Raises RuntimeError if PayPal is not configured or authentication fails.
    """
    import httpx

    global _cached_token, _token_expires_at

    now = datetime.now(timezone.utc)
    if _cached_token and _token_expires_at and now < _token_expires_at:
        return _cached_token

    if not is_configured():
        raise RuntimeError("PayPal adapter is not configured (check PAYPAL_MODE, PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET)")

    client_id = os.getenv("PAYPAL_CLIENT_ID", "")
    client_secret = os.getenv("PAYPAL_CLIENT_SECRET", "")

    # Log the attempt WITHOUT the secret
    logger.info("Requesting PayPal Sandbox OAuth token for client_id=%s…", client_id[:8] + "***")

    try:
        resp = httpx.post(
            PAYPAL_OAUTH_URL,
            auth=(client_id, client_secret),
            data={"grant_type": "client_credentials"},
            headers={"Accept": "application/json"},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except httpx.TimeoutException as exc:
        raise RuntimeError(f"PayPal OAuth request timed out: {exc}") from exc

    if resp.status_code != 200:
        # Log status only — no secret in log
        logger.error(
            "PayPal OAuth failed: HTTP %d (client_id=%s***)",
            resp.status_code,
            client_id[:8],
        )
        raise RuntimeError(
            f"PayPal OAuth failed with HTTP {resp.status_code}. "
            "Check PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET."
        )

    data = resp.json()
    _cached_token = data["access_token"]
    expires_in = int(data.get("expires_in", 32400))  # default 9 hours
    # Cache expires 60 seconds early to avoid edge-case expiry during a request
    from datetime import timedelta
    _token_expires_at = now + timedelta(seconds=max(0, expires_in - 60))

    logger.info("PayPal Sandbox OAuth token obtained; expires in %ds", expires_in)
    return _cached_token


def submit_payout(
    *,
    sender_batch_id: str,
    items: list[PayoutItem],
) -> PayPalSubmitResult:
    """
    Submit a batch payout to PayPal Sandbox.

    SAFETY RULES:
      - sender_batch_id must be stable and must be persisted BEFORE this call.
      - Only USD is accepted; other currencies raise ValueError immediately.
      - On timeout, returns status UNKNOWN; caller must NOT retry with a new ID.
      - On HTTP error, returns failure result with sanitized message.
      - client_secret is never in the returned result or in logs.
    """
    import httpx

    # Validate all items are USD
    for item in items:
        if item.currency.upper() not in SUPPORTED_CURRENCIES:
            raise ValueError(
                f"PayPal Sandbox adapter only supports USD; got {item.currency!r} "
                f"for sender_item_id={item.sender_item_id!r}"
            )

    if not is_configured():
        logger.warning(
            "PayPal adapter not configured; submission for sender_batch_id=%r will be skipped.",
            sender_batch_id,
        )
        return PayPalSubmitResult(
            success=False,
            sender_batch_id=sender_batch_id,
            error_message="PayPal credentials not configured. Set PAYPAL_MODE=sandbox, PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET.",
            is_simulated=True,
        )

    try:
        token = _get_access_token()
    except RuntimeError as exc:
        return PayPalSubmitResult(
            success=False,
            sender_batch_id=sender_batch_id,
            error_message=str(exc),
        )

    payload = {
        "sender_batch_header": {
            "sender_batch_id": sender_batch_id,
            "email_subject": "PUFI Sandbox Payout [SYNTHETIC DATA]",
            "email_message": "This is a sandbox test payout from the PUFI prototype. No real money moves.",
        },
        "items": [
            {
                "recipient_type": "EMAIL",
                "amount": {
                    "value": item.amount_value,
                    "currency": item.currency.upper(),
                },
                "receiver": item.receiver_email,
                "note": item.note,
                "sender_item_id": item.sender_item_id,
            }
            for item in items
        ],
    }

    logger.info(
        "Submitting PayPal Sandbox payout: sender_batch_id=%r items=%d",
        sender_batch_id,
        len(items),
    )

    try:
        resp = httpx.post(
            PAYPAL_PAYOUTS_URL,
            json=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except httpx.TimeoutException:
        logger.error(
            "PayPal payout submission timed out for sender_batch_id=%r — "
            "status set to UNKNOWN; do NOT retry with a new ID",
            sender_batch_id,
        )
        return PayPalSubmitResult(
            success=False,
            sender_batch_id=sender_batch_id,
            http_status=None,
            error_message="Request timed out. Status is UNKNOWN — query PayPal before retrying.",
        )

    # Sanitize response: strip any header-level auth info
    sanitized = {
        "http_status": resp.status_code,
        "body": _sanitize_response_body(resp.text),
    }

    if resp.status_code in (200, 201):
        data = resp.json()
        batch_header = data.get("batch_header", {})
        payout_batch_id = batch_header.get("payout_batch_id")
        batch_status = batch_header.get("batch_status")
        logger.info(
            "PayPal payout accepted: payout_batch_id=%r status=%r",
            payout_batch_id,
            batch_status,
        )
        return PayPalSubmitResult(
            success=True,
            sender_batch_id=sender_batch_id,
            paypal_payout_batch_id=payout_batch_id,
            paypal_batch_status=batch_status,
            http_status=resp.status_code,
        )
    else:
        error_msg = f"PayPal API returned HTTP {resp.status_code}: {_extract_error_message(resp.text)}"
        logger.error(
            "PayPal payout failed: sender_batch_id=%r http=%d",
            sender_batch_id,
            resp.status_code,
        )
        return PayPalSubmitResult(
            success=False,
            sender_batch_id=sender_batch_id,
            http_status=resp.status_code,
            error_message=error_msg,
        )


def get_batch_status(paypal_payout_batch_id: str) -> PayPalBatchStatusResult:
    """
    Query PayPal Sandbox for the current batch and item statuses.

    Maps PayPal item_status values to PUFI instruction statuses.
    Never interprets PENDING or UNCLAIMED as final settlement.
    """
    import httpx

    if not is_configured():
        return PayPalBatchStatusResult(
            success=False,
            paypal_payout_batch_id=paypal_payout_batch_id,
            error_message="PayPal adapter not configured.",
        )

    try:
        token = _get_access_token()
    except RuntimeError as exc:
        return PayPalBatchStatusResult(
            success=False,
            paypal_payout_batch_id=paypal_payout_batch_id,
            error_message=str(exc),
        )

    url = PAYPAL_PAYOUTS_GET_URL.format(payout_batch_id=paypal_payout_batch_id)

    try:
        resp = httpx.get(
            url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except httpx.TimeoutException:
        return PayPalBatchStatusResult(
            success=False,
            paypal_payout_batch_id=paypal_payout_batch_id,
            error_message="Status query timed out.",
        )

    if resp.status_code != 200:
        return PayPalBatchStatusResult(
            success=False,
            paypal_payout_batch_id=paypal_payout_batch_id,
            error_message=f"HTTP {resp.status_code}: {_extract_error_message(resp.text)}",
        )

    data = resp.json()
    batch_header = data.get("batch_header", {})
    batch_status = batch_header.get("batch_status")

    items: list[PayoutItemStatus] = []
    for item_data in data.get("items", []):
        payout_item = item_data.get("payout_item", {})
        sender_item_id = payout_item.get("sender_item_id", "")
        payout_item_id = item_data.get("payout_item_id")
        transaction_id = item_data.get("transaction_id")
        item_status = item_data.get("transaction_status", "UNKNOWN")
        # Extract error if present
        error_info = item_data.get("errors")
        error_message = None
        if error_info:
            error_message = error_info.get("message", str(error_info))

        items.append(PayoutItemStatus(
            sender_item_id=sender_item_id,
            payout_item_id=payout_item_id,
            transaction_id=transaction_id,
            item_status=item_status,
            error_message=error_message,
        ))

    logger.info(
        "PayPal status refreshed: payout_batch_id=%r batch_status=%r items=%d",
        paypal_payout_batch_id,
        batch_status,
        len(items),
    )

    return PayPalBatchStatusResult(
        success=True,
        paypal_payout_batch_id=paypal_payout_batch_id,
        paypal_batch_status=batch_status,
        items=items,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _sanitize_response_body(raw: str) -> str:
    """
    Return a sanitized subset of the response body for audit storage.
    Strips access_token fields if present (defensive measure).
    """
    try:
        data = json.loads(raw)
        # Remove any token-like fields defensively
        for key in ("access_token", "refresh_token", "id_token"):
            data.pop(key, None)
        return json.dumps(data)[:2000]  # cap stored size
    except (json.JSONDecodeError, AttributeError):
        return raw[:500]


def _extract_error_message(raw: str) -> str:
    """Extract a human-readable error from a PayPal error response body."""
    try:
        data = json.loads(raw)
        name = data.get("name", "")
        message = data.get("message", "")
        if name and message:
            return f"{name}: {message}"
        return message or name or raw[:200]
    except (json.JSONDecodeError, AttributeError):
        return raw[:200]
