"""
PUFI — Shared FastAPI authentication and authorization dependencies (Priority 2.0).

Architecture & Security Model:
  1. Separation of Concerns:
     - Authentication: Validates caller credentials (X-Api-Key) and establishes an authenticated Principal.
     - Authorization: Enforces role-based permissions (require_role) independent of transport.
  2. Fail-Closed in Protected Environments:
     - If PUFI_ENV is 'production'/'staging' or REQUIRE_AUTH=true, missing DEMO_API_KEY
       causes requests to fail closed with HTTP 500 (AUTH_MISCONFIGURED).
     - In development mode without DEMO_API_KEY, a development mock principal is returned
       with explicit logging and metadata.
  3. Identity Integrity:
     - State-modifying actions (approval, submission) bind their audit actor to the
       authenticated principal, preventing unauthenticated callers from forging arbitrary approver IDs.

LIMITATIONS (Documented for Security Audit):
  - Demonstration Mechanism: This implementation uses a shared API key header (X-Api-Key).
  - Not Enterprise SSO / OAuth2: It does not integrate with an external IdP (Okta, Azure AD, Ping)
    or issue cryptographically signed JWT access tokens with short lifetimes and revocation lists.
  - Role Assignment: Caller roles are currently assigned via header / default policy; in production,
    roles must be asserted by a trusted identity token signed by an enterprise authorization server.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Callable, Optional, Set

from fastapi import Depends, Header, HTTPException, Request

logger = logging.getLogger("pufi.auth")


@dataclass
class Principal:
    """
    Authenticated security principal representing the caller.
    Separates authentication (who the caller is) from authorization (permissions granted).
    """
    identity: str
    roles: Set[str] = field(default_factory=lambda: {"OPERATOR"})
    auth_method: str = "API_KEY"

    def has_role(self, role: str) -> bool:
        """Check if principal possesses the specified role or superuser permissions."""
        return role in self.roles or "ADMIN" in self.roles


def is_auth_enforced() -> bool:
    """
    Returns True if authentication MUST be enforced and cannot be bypassed.
    Checked via PUFI_ENV / ENVIRONMENT or explicit REQUIRE_AUTH flag.
    """
    env = os.getenv("PUFI_ENV", os.getenv("ENVIRONMENT", "development")).lower()
    require_flag = os.getenv("REQUIRE_AUTH", "false").lower() in ("true", "1", "yes")
    return env in ("production", "staging", "prod") or require_flag


def authenticate_principal(
    request: Request,
    x_api_key: str = Header(default=""),
    x_actor_id: Optional[str] = Header(default=None),
    x_actor_role: Optional[str] = Header(default=None),
) -> Principal:
    """
    Authenticates the incoming request against configured credentials.
    Returns an authenticated Principal.
    """
    expected = os.getenv("DEMO_API_KEY", "").strip()
    enforced = is_auth_enforced()

    # Fail closed if auth is mandatory in this environment but unconfigured
    if enforced and not expected:
        logger.error("AUTH_MISCONFIGURED: Protected environment requires authentication but DEMO_API_KEY is not set.")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "AUTH_MISCONFIGURED",
                "message": (
                    "Authentication is mandatory in this environment but DEMO_API_KEY is unset. "
                    "System fails closed to prevent unauthenticated access."
                ),
            },
        )

    if expected:
        if not x_api_key or x_api_key != expected:
            logger.warning("Authentication failed: missing or invalid X-Api-Key.")
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "FORBIDDEN",
                    "message": "A valid X-Api-Key header is required for this action.",
                },
            )
        # Authenticated principal
        identity = x_actor_id.strip() if x_actor_id and x_actor_id.strip() else "AUTHENTICATED_OPERATOR"
        if x_actor_role and x_actor_role.strip():
            roles = {x_actor_role.strip().upper()}
        else:
            roles = {"CONTROLLER", "TREASURY_CHECKER", "OPERATOR"}
        principal = Principal(
            identity=identity,
            roles=roles,
            auth_method="API_KEY",
        )
    else:
        # Development unauthenticated convenience mode
        logger.debug("DEMO_API_KEY not configured; operating in unauthenticated development mode.")
        identity = x_actor_id.strip() if x_actor_id and x_actor_id.strip() else "DEV_OPERATOR"
        if x_actor_role and x_actor_role.strip():
            roles = {x_actor_role.strip().upper()}
        else:
            roles = {"CONTROLLER", "TREASURY_CHECKER", "OPERATOR"}
        principal = Principal(
            identity=identity,
            roles=roles,
            auth_method="DEV_MOCK",
        )

    # Store principal in request state for downstream handler access
    request.state.principal = principal
    request.state.authenticated_actor = principal.identity
    return principal


def require_api_key(
    request: Request,
    principal: Principal = Depends(authenticate_principal),
) -> Principal:
    """
    FastAPI dependency that validates the X-Api-Key header.
    Maintains full backward compatibility with existing route annotations while
    returning the authenticated Principal.
    """
    return principal


def require_role(required_role: str) -> Callable[[Principal], Principal]:
    """
    Role-based authorization dependency factory.
    Enforces that the authenticated principal possesses the specified role.
    """
    def _role_checker(principal: Principal = Depends(authenticate_principal)) -> Principal:
        if not principal.has_role(required_role):
            logger.warning(
                "Authorization failed: principal %s lacks required role %s",
                principal.identity,
                required_role,
            )
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "INSUFFICIENT_PERMISSIONS",
                    "message": f"Action requires '{required_role}' authorization role.",
                },
            )
        return principal

    return _role_checker
