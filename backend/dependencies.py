"""
PUFI — Shared FastAPI authentication and authorization dependencies (Priority 2.1).

Architecture & Security Model (Priority 2.1 Remediation):
  1. Server-Controlled Identity and Roles:
     - Authorization is strictly server-controlled: client-supplied headers like X-Actor-Role
       or X-Actor-Id are NEVER trusted to assign roles or establish identity.
     - Known API key credentials map on the server to authoritative identities and role sets.
     - Segregation of duties: dedicated roles for TREASURY_CHECKER, CONTROLLER, AUDITOR, and OPERATOR.
  2. Fail-Closed in Protected Environments:
     - If PUFI_ENV is 'production'/'staging' or REQUIRE_AUTH=true, missing server credentials
       cause requests to fail closed with HTTP 500 (AUTH_MISCONFIGURED).
     - In development mode without configured credentials (and when auth is not enforced),
       a development mock principal is returned for local developer convenience.
  3. Identity Integrity:
     - State-modifying actions (approval, submission) bind their audit actor to the
       authoritative authenticated principal, preventing identity spoofing.

LIMITATIONS (Documented for Security Audit):
  - Demonstration Mechanism: This prototype implementation uses server-configured API keys.
  - Not Enterprise SSO / OAuth2: It does not integrate with an external IdP (Okta, Azure AD, Ping)
    or issue cryptographically signed JWT access tokens with short lifetimes, audience validation,
    and revocation lists.
  - In an enterprise production deployment, this mechanism must be replaced with an OAuth2 / OIDC
    Bearer token architecture validating JWKS signatures and enterprise directory group claims.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Callable, Optional, Set

from fastapi import Depends, Header, HTTPException, Request

logger = logging.getLogger("pufi.auth")


@dataclass(frozen=True)
class PrincipalProfile:
    """Server-authoritative mapping entry for a credential."""
    identity: str
    roles: frozenset[str]


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


def _get_server_principal_registry() -> dict[str, PrincipalProfile]:
    """
    Builds the authoritative server-side credential registry.
    Reads from:
      1. PUFI_API_KEYS_JSON: optional JSON dictionary of {"api_key": {"identity": "...", "roles": ["..."]}}
      2. Configured environment keys:
         - DEMO_API_KEY -> identity="treasury_admin", roles={"TREASURY_CHECKER", "CONTROLLER", "AUDITOR", "OPERATOR"}
         - DEMO_CHECKER_KEY -> identity="treasury_checker_alice", roles={"TREASURY_CHECKER", "OPERATOR"}
         - DEMO_CONTROLLER_KEY -> identity="controller_carol", roles={"CONTROLLER", "OPERATOR"}
         - DEMO_AUDITOR_KEY -> identity="auditor_eve", roles={"AUDITOR"}
         - DEMO_OPERATOR_KEY -> identity="operator_bob", roles={"OPERATOR"}
    """
    registry: dict[str, PrincipalProfile] = {}

    # 1. Custom JSON mapping if supplied
    custom_json = os.getenv("PUFI_API_KEYS_JSON", "").strip()
    if custom_json:
        try:
            parsed = json.loads(custom_json)
            for key, val in parsed.items():
                if isinstance(val, dict):
                    ident = val.get("identity", "custom_principal")
                    roles = frozenset(val.get("roles", ["OPERATOR"]))
                    registry[key] = PrincipalProfile(identity=ident, roles=roles)
        except Exception as exc:
            logger.warning("Failed to parse PUFI_API_KEYS_JSON: %s", exc)

    # 2. Standard configured keys
    demo_key = os.getenv("DEMO_API_KEY", "").strip()
    if demo_key and demo_key not in registry:
        demo_id = os.getenv("DEMO_PRINCIPAL_ID", "treasury_admin").strip()
        registry[demo_key] = PrincipalProfile(
            identity=demo_id,
            roles=frozenset({"TREASURY_CHECKER", "CONTROLLER", "AUDITOR", "OPERATOR"}),
        )

    checker_key = os.getenv("DEMO_CHECKER_KEY", "").strip()
    if checker_key and checker_key not in registry:
        registry[checker_key] = PrincipalProfile(
            identity=os.getenv("CHECKER_PRINCIPAL_ID", "treasury_checker_alice"),
            roles=frozenset({"TREASURY_CHECKER", "OPERATOR"}),
        )

    controller_key = os.getenv("DEMO_CONTROLLER_KEY", "").strip()
    if controller_key and controller_key not in registry:
        registry[controller_key] = PrincipalProfile(
            identity=os.getenv("CONTROLLER_PRINCIPAL_ID", "controller_carol"),
            roles=frozenset({"CONTROLLER", "OPERATOR"}),
        )

    auditor_key = os.getenv("DEMO_AUDITOR_KEY", "").strip()
    if auditor_key and auditor_key not in registry:
        registry[auditor_key] = PrincipalProfile(
            identity=os.getenv("AUDITOR_PRINCIPAL_ID", "auditor_eve"),
            roles=frozenset({"AUDITOR"}),
        )

    operator_key = os.getenv("DEMO_OPERATOR_KEY", "").strip()
    if operator_key and operator_key not in registry:
        registry[operator_key] = PrincipalProfile(
            identity=os.getenv("OPERATOR_PRINCIPAL_ID", "operator_bob"),
            roles=frozenset({"OPERATOR"}),
        )

    return registry


def authenticate_principal(
    request: Request,
    x_api_key: str = Header(default=""),
) -> Principal:
    """
    Authenticates the incoming request against server-controlled credentials.
    Returns an authenticated Principal with server-authoritative identity and roles.

    SECURITY ENFORCEMENT:
    - Client-supplied X-Actor-Role and X-Actor-Id headers are NEVER trusted or used
      to grant permissions or establish caller identity.
    - Identity and roles are mapped strictly on the server from the verified API key.
    - In protected environments (production/staging or REQUIRE_AUTH=true), missing
      credentials fail closed with HTTP 500.
    """
    enforced = is_auth_enforced()
    registry = _get_server_principal_registry()

    # Log security audit warning if client attempted to self-assert role or identity
    untrusted_role = request.headers.get("x-actor-role")
    untrusted_id = request.headers.get("x-actor-id")
    if untrusted_role or untrusted_id:
        logger.warning(
            "Untrusted client headers detected and ignored: X-Actor-Role=%r, X-Actor-Id=%r. "
            "Server-controlled identity and role policy enforced.",
            untrusted_role,
            untrusted_id,
        )

    # Fail closed if auth is mandatory in this environment but no keys configured
    if enforced and not registry:
        logger.error("AUTH_MISCONFIGURED: Protected environment requires authentication but no server API keys are configured.")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "AUTH_MISCONFIGURED",
                "message": (
                    "Authentication is mandatory in this environment but no valid API keys are configured on the server. "
                    "System fails closed to prevent unauthenticated access."
                ),
            },
        )

    if registry:
        if not x_api_key or x_api_key not in registry:
            logger.warning("Authentication failed: missing or invalid X-Api-Key.")
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "FORBIDDEN",
                    "message": "A valid server-configured X-Api-Key is required for this action.",
                },
            )
        profile = registry[x_api_key]
        principal = Principal(
            identity=profile.identity,
            roles=set(profile.roles),
            auth_method="API_KEY",
        )
    else:
        # Development unauthenticated convenience mode (only when auth is not enforced)
        logger.debug("No API keys configured; operating in unauthenticated development mode.")
        principal = Principal(
            identity="dev_mock_operator",
            roles={"CONTROLLER", "TREASURY_CHECKER", "AUDITOR", "OPERATOR"},
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
    FastAPI dependency that validates caller authentication.
    Maintains full backward compatibility with existing route annotations while
    returning the authenticated Principal.
    """
    return principal


def require_role(*required_roles: str) -> Callable[[Principal], Principal]:
    """
    Role-based authorization dependency factory.
    Enforces that the authenticated principal possesses at least one of the specified roles.
    """
    def _role_checker(principal: Principal = Depends(authenticate_principal)) -> Principal:
        has_any = any(principal.has_role(r) for r in required_roles)
        if not has_any:
            logger.warning(
                "Authorization failed: principal %s (roles=%s) lacks required role(s) %s",
                principal.identity,
                principal.roles,
                required_roles,
            )
            roles_str = ", ".join(repr(r) for r in required_roles)
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "INSUFFICIENT_PERMISSIONS",
                    "message": f"Action requires one of {roles_str} authorization role(s).",
                },
            )
        return principal

    return _role_checker
