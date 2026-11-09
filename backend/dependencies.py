"""
PUFI — Shared FastAPI dependencies.

access_control:
  Minimal API-key gate for sensitive endpoints (approve, submit).
  Uses the DEMO_API_KEY environment variable.

  In a production system this would be replaced with proper OAuth2/JWT
  authentication. For this hackathon prototype it provides a clear separation
  between read-only viewing and write-level (approve / execute) operations.

  To skip the check in development set DEMO_API_KEY to an empty string
  or omit it entirely — the check is bypassed when no key is configured.

  The key is passed by the client in the X-Api-Key header.

  IMPORTANT: This is NOT enterprise-grade identity management.
  It is explicitly labelled as a demo mechanism.
"""
import logging
import os

from fastapi import Header, HTTPException

logger = logging.getLogger("pufi.auth")


def require_api_key(x_api_key: str = Header(default="")) -> None:
    """
    FastAPI dependency that validates the X-Api-Key header against the
    DEMO_API_KEY environment variable.

    - If DEMO_API_KEY is not set or is empty, the check is bypassed
      (development convenience).
    - If DEMO_API_KEY is set, the header must match exactly.
    - Rejects the request with 403 on mismatch.

    Label: DEMO AUTH MECHANISM — not enterprise-grade.
    """
    expected = os.getenv("DEMO_API_KEY", "").strip()
    if not expected:
        # No key configured — open in development mode; log a warning
        logger.debug("DEMO_API_KEY not configured; access control bypassed.")
        return
    if x_api_key != expected:
        logger.warning("Invalid API key on sensitive endpoint (key masked).")
        raise HTTPException(
            status_code=403,
            detail={
                "error": "FORBIDDEN",
                "message": (
                    "A valid X-Api-Key header is required for this action. "
                    "DEMO AUTH MECHANISM — set DEMO_API_KEY in .env."
                ),
            },
        )
