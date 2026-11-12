# PUFI — Priority 2.1 Critical Security and Integrity Remediation Report

**Version:** pufi-0.2.1  
**Date:** 2026-11-12  
**Branch:** `frontend-redesign-v2`  
**Status:** ✅ All remediation items implemented and verified

---

## Executive Summary

Priority 2.1 addresses five independently identified gaps in the PUFI
security and data-integrity model. The remediation upgrades authentication
from client-asserted headers to a server-controlled principal registry,
enforces an explicit payment-state transition matrix that prevents terminal
reversals, corrects audit-chain verification to validate per-entity chains
independently, protects audit endpoints with role-based authorization, and
adds database-level constraints and strict input validation to the webhook
event model.

All 209 backend tests (206 unit/integration + 3 load) pass.  
The frontend production build succeeds.  
No existing tests were weakened or removed.

---

## 1. P0 — Trusted Authentication and Authorization

### 1.1 Problem

The previous implementation trusted client-supplied HTTP headers to assign
identity and roles:

- `X-Actor-Role` could grant the caller any role (CONTROLLER, ADMIN, etc.).
- `X-Actor-Id` could impersonate any user identity.
- Approval actors were taken from request payloads, not authenticated
  principals.

### 1.2 Remediation

**File:** `backend/dependencies.py` — full rewrite.

#### Server-Controlled Principal Registry

```
┌───────────────────────────────┐
│      Request with X-Api-Key   │
└───────────┬───────────────────┘
            ▼
┌───────────────────────────────┐
│  _get_server_principal_registry()
│  ─────────────────────────────
│  Sources (priority order):    │
│  1. PUFI_API_KEYS_JSON (JSON) │
│  2. DEMO_API_KEY              │
│  3. DEMO_CHECKER_KEY          │
│  4. DEMO_CONTROLLER_KEY       │
│  5. DEMO_AUDITOR_KEY          │
│  6. DEMO_OPERATOR_KEY         │
│                               │
│  Each key → PrincipalProfile  │
│    • identity  (server-set)   │
│    • roles     (server-set)   │
└───────────┬───────────────────┘
            ▼
┌───────────────────────────────┐
│  authenticate_principal()     │
│  ─────────────────────────────│
│  • X-Actor-Role IGNORED       │
│  • X-Actor-Id  IGNORED        │
│  • Logs security audit warning│
│    for untrusted header use   │
│  • Fails closed if enforced   │
│    env has no keys configured │
└───────────┬───────────────────┘
            ▼
┌───────────────────────────────┐
│  Principal(identity, roles,   │
│            auth_method)       │
└───────────────────────────────┘
```

#### Key-to-Identity Mapping (Default Configuration)

| Environment Variable | Identity | Roles |
|---|---|---|
| `DEMO_API_KEY` | `treasury_admin` | TREASURY_CHECKER, CONTROLLER, AUDITOR, OPERATOR |
| `DEMO_CHECKER_KEY` | `treasury_checker_alice` | TREASURY_CHECKER, OPERATOR |
| `DEMO_CONTROLLER_KEY` | `controller_carol` | CONTROLLER, OPERATOR |
| `DEMO_AUDITOR_KEY` | `auditor_eve` | AUDITOR |
| `DEMO_OPERATOR_KEY` | `operator_bob` | OPERATOR |

#### Fail-Closed Enforcement

- If `PUFI_ENV` is `production` or `staging`, or `REQUIRE_AUTH=true`:
  - Missing server credentials → HTTP 500 `AUTH_MISCONFIGURED`.
  - No unauthenticated fallback.
- Development mode without credentials: `dev_mock_operator` with full roles.

#### Approval Actor Derivation

- In enforced auth mode, `approved_by` is always set to `principal.identity`.
- Payload `approver_id` that mismatches the principal → HTTP 403 `IDENTITY_MISMATCH`.
- In DEV_MOCK mode, body `approver_id` is honored for backward compatibility.

### 1.3 Test Coverage

| Test | Assertion |
|---|---|
| `test_self_grant_admin_role_rejected` | Caller with OPERATOR key cannot self-grant ADMIN via X-Actor-Role |
| `test_self_grant_treasury_checker_rejected` | OPERATOR key cannot access TREASURY_CHECKER-protected endpoint |
| `test_impersonation_via_x_actor_id_rejected` | Changing X-Actor-Id header does not alter authenticated identity |
| `test_approval_actor_derived_from_principal` | Approval `approved_by` equals authenticated principal identity |

### 1.4 Documented Limitations

> **This is a demonstration-grade API key mechanism.** It is not enterprise
> SSO, OAuth2/OIDC, or JWT-based authentication. A production deployment
> must replace this with:
> - An external Identity Provider (Okta, Azure AD, Ping Identity)
> - Cryptographically signed JWT access tokens with short lifetimes
> - JWKS signature validation and audience/issuer verification
> - Enterprise directory group-based role claims

---

## 2. P0 — Terminal State Transition Integrity

### 2.1 Problem

Webhook events could potentially override terminal payment states:
- `FAILED → COMPLETED` was not explicitly blocked.
- `CANCELLED → COMPLETED` was not explicitly blocked.
- No distinction between legitimate refund/reversal events and erroneous
  terminal reversals.

### 2.2 Remediation

**File:** `backend/routers/webhooks.py`

#### Explicit State Transition Matrix

```
ALLOWED_TRANSITIONS = {
    CREATED            → {APPROVED, CANCELLED}
    APPROVED           → {SUBMISSION_PENDING, CANCELLED}
    SUBMISSION_PENDING → {SUBMITTED, UNKNOWN, FAILED}
    SUBMITTED          → {COMPLETED, FAILED, UNKNOWN, SUBMITTED}
    UNKNOWN            → {SUBMITTED, COMPLETED, FAILED, UNKNOWN}

    COMPLETED          → {REFUNDED, REVERSED}   (refund events only, verified timestamp required)

    FAILED             → ∅  (strictly terminal, no outward transitions)
    CANCELLED          → ∅
    REFUNDED           → ∅
    REVERSED           → ∅
}
```

#### Four-Layer Transition Enforcement

1. **Duplicate status events**: Same status as current → `DUPLICATE_IGNORED`.
2. **Strictly terminal states** (FAILED, CANCELLED, REFUNDED, REVERSED):
   - `→ COMPLETED`: `CONFLICT_REJECTED` with `"Unauthorized terminal reversal"`.
   - `→ non-terminal`: `OUT_OF_ORDER_IGNORED` with `"Terminal status cannot be reverted"`.
   - `→ other terminal`: `CONFLICT_REJECTED`.
3. **COMPLETED state**:
   - Refund/reversal events (REFUNDED, RETURNED, REVERSED) with **verified timestamp** → allowed.
   - Refund events with **missing or unparseable timestamp** → `UNVERIFIED_TIMESTAMP_IGNORED`.
   - Non-refund events → `CONFLICT_REJECTED` or `OUT_OF_ORDER_IGNORED`.
4. **Non-terminal states**: Checked against `ALLOWED_TRANSITIONS` map.
   - Disallowed target → `CONFLICT_REJECTED`.
   - Stale timestamp → `STALE_EVENT_IGNORED`.

#### Refund/Reversal Event Model

| PayPal Event Type | PUFI Status | Settlement Evidence | Is Refund/Reversal |
|---|---|---|---|
| `PAYOUTS-ITEM.REFUNDED` | `REFUNDED` | `FUNDS_REFUNDED` | ✅ |
| `PAYOUTS-ITEM.RETURNED` | `REFUNDED` | `FUNDS_RETURNED` | ✅ |
| `PAYOUTS-ITEM.REVERSED` | `REVERSED` | `FUNDS_REVERSED` | ✅ |

**Database constraints added** to `PaymentInstruction` and `PaymentBatch`:
- Status: `REFUNDED`, `REVERSED` added to check constraints.
- Settlement evidence: `FUNDS_RETURNED`, `FUNDS_REFUNDED`, `FUNDS_REVERSED` added.

### 2.3 Test Coverage

| Test | Assertion |
|---|---|
| `test_failed_to_completed_rejected` | FAILED → COMPLETED blocked with CONFLICT_REJECTED |
| `test_cancelled_to_completed_rejected` | CANCELLED → COMPLETED blocked |
| `test_failed_to_submitted_rejected` | FAILED → SUBMITTED blocked |
| `test_completed_to_failed_rejected` | COMPLETED → FAILED blocked (non-refund event) |
| `test_completed_to_submitted_rejected` | COMPLETED → SUBMITTED blocked |
| `test_completed_to_refunded_allowed` | COMPLETED → REFUNDED allowed with valid timestamp |
| `test_refunded_to_completed_rejected` | REFUNDED → COMPLETED blocked |
| `test_completed_refund_invalid_timestamp_rejected` | Refund with unparseable timestamp rejected |

---

## 3. P1 — Audit-Chain Verification

### 3.1 Problem

The global `verify_audit_chain()` function treated all audit events as a
single linear chain, regardless of entity. Events from different entities
(e.g., two separate payment instructions) would fail verification because
entity B's genesis event would not link to entity A's chain head.

### 3.2 Remediation

**File:** `backend/services/audit.py`

#### Architecture

```
verify_audit_chain(entity_id=None)
        │
        ├── entity_id provided → _verify_single_entity_chain(entity_id)
        │
        └── entity_id=None (global) →
              ├── Query DISTINCT entity_ids with hash records
              ├── For each entity: _verify_single_entity_chain(eid)
              ├── Aggregate: total_events, chains_checked, failures
              └── Return first failure with broken_entity_id + broken_event_id
```

#### Per-Entity Chain Verification

`_verify_single_entity_chain(db, entity_id)` performs:

1. Query all events for the entity, ordered by `(created_at ASC, id ASC)`.
2. Attempt cryptographic chain reordering via `prev_hash` links if timestamp
   ties exist.
3. Verify genesis event has `prev_hash = GENESIS_HASH`.
4. For each subsequent event:
   - `prev_hash` must equal predecessor's `event_hash` (link integrity).
   - Recomputed hash must match stored `event_hash` (payload integrity).
5. Return `AuditVerificationResult` with:
   - `broken_entity_id`: which entity failed.
   - `broken_event_id`: which specific event broke the chain.
   - `failure_reason`: diagnostic description.

#### Global Aggregation

When `entity_id=None`:
- Each entity chain is verified independently.
- Results are aggregated: `chains_checked`, `total_events_checked`.
- On failure: `failed_entities` list includes `{entity_id, broken_event_id, reason}`.
- First failure's details are surfaced at the top level.

### 3.3 Architectural Limitations

> **The hash chain is stored entirely in the same database as the data
> it protects.** It is tamper-evident against:
> - Unauthorized local record modifications (field edits)
> - Intermediate record deletions
> - Event reordering
>
> It **cannot** detect:
> - Tail truncation (dropping the most recent event) without external
>   Merkle/WORM head anchoring
> - Whole-database restoration from a prior backup
> - A database administrator with direct SQL access who recalculates
>   all hashes after modification
>
> **Do not describe this as tamper-proof or equivalent to externally
> anchored immutable storage.**

### 3.4 Test Coverage

| Test | Assertion |
|---|---|
| `test_multi_entity_global_verification` | Two entities with separate genesis events both pass global verification |
| `test_broken_entity_identification` | Tampering in one entity's chain is identified with correct entity_id and event_id |
| `test_intermediate_deletion_detected` | Deleting a middle event breaks the prev_hash link chain |
| `test_truncation_limitation_documented` | Tail truncation is not detectable (documented limitation) |

---

## 4. P1 — Audit Endpoint Protection

### 4.1 Problem

Audit listing (`GET /batches/{id}/audit`) and verification
(`GET /audit/verify`) endpoints had no role-based access control beyond
basic API key authentication.

### 4.2 Remediation

**File:** `backend/routers/execution.py`

Both endpoints now require one of: `AUDITOR`, `CONTROLLER`, or
`TREASURY_CHECKER` roles.

```python
@router.get("/batches/{batch_id}/audit", ...)
def list_audit_events(
    ...,
    principal: Principal = Depends(require_role("AUDITOR", "CONTROLLER", "TREASURY_CHECKER")),
):

@router.get("/audit/verify", ...)
def verify_audit(
    ...,
    principal: Principal = Depends(require_role("AUDITOR", "CONTROLLER", "TREASURY_CHECKER")),
):
```

### 4.3 Test Coverage

| Test | Assertion |
|---|---|
| `test_unauthorized_operator_audit_listing_rejected` | OPERATOR role gets HTTP 403 for audit listing |
| `test_authorized_auditor_audit_listing_succeeds` | AUDITOR role gets HTTP 200 for audit listing |
| `test_unauthorized_operator_audit_verify_rejected` | OPERATOR role gets HTTP 403 for audit verify |
| `test_authorized_auditor_audit_verify_succeeds` | AUDITOR role gets HTTP 200 for audit verify |

---

## 5. P1 — Webhook Model Correctness

### 5.1 Problem

- The `WebhookEvent` model had no database constraint on the `status` column.
- Missing or empty `provider_event_id` could be inserted.
- Malformed payloads (missing event type, non-object resource) were not
  rejected at the HTTP boundary before reaching state-update logic.

### 5.2 Remediation

**File:** `backend/models/entities.py`

```python
class WebhookEvent(Base):
    __table_args__ = (
        UniqueConstraint("provider", "provider_event_id", name="uq_webhook_event_id"),
        CheckConstraint(
            "status IN ('RECEIVED','PROCESSED','DUPLICATE_IGNORED',...,'FAILED')",
            name="ck_webhook_event_status_valid",
        ),
        CheckConstraint(
            "length(provider_event_id) > 0",
            name="ck_webhook_event_id_nonempty",
        ),
    )
```

**File:** `backend/routers/webhooks.py` — input validation added:

1. **Missing/empty event ID** → HTTP 400 `MISSING_EVENT_ID`.
2. **Missing/empty event type** → HTTP 400 `MISSING_EVENT_TYPE`.
3. **Non-dict resource** → HTTP 400 `MALFORMED_RESOURCE`.
4. All validation occurs *after* signature verification but *before* any
   database state modification.

### 5.3 Test Coverage

| Test | Assertion |
|---|---|
| `test_missing_event_id_rejected` | Empty `id` field → HTTP 400 with `MISSING_EVENT_ID` |
| `test_missing_event_type_rejected` | Empty `event_type` → HTTP 400 with `MISSING_EVENT_TYPE` |
| `test_malformed_resource_rejected` | Non-object `resource` → HTTP 400 with `MALFORMED_RESOURCE` |
| `test_malformed_webhook_no_state_modification` | Malformed payload does not modify instruction status |

---

## 6. Complete Test Results

### 6.1 Backend Unit/Integration Tests

| Test Suite | Tests | Status |
|---|---|---|
| `test_day4.py` | 35 | ✅ PASSED |
| `test_day5.py` | 7 | ✅ PASSED |
| `test_extended.py` | 18 | ✅ PASSED |
| `test_financial_engine.py` | 47 | ✅ PASSED |
| `test_obligations.py` | 25 | ✅ PASSED |
| `test_p1_remediation.py` | 18 | ✅ PASSED |
| `test_p2_remediation.py` | 15 | ✅ PASSED |
| `test_p2_1_remediation.py` | 24 | ✅ PASSED |
| `test_remediation.py` | 17 | ✅ PASSED |
| **Subtotal** | **206** | **ALL PASSED** |

### 6.2 Load Tests

| Test Suite | Tests | Time | Status |
|---|---|---|---|
| `test_load.py` (100, 1000, 10000 items) | 3 | 46.62s | ✅ PASSED |

### 6.3 Frontend Production Build

```
vite v8.3.5 building client environment for production...
✓ 2147 modules transformed.
dist/index.html                     0.45 kB │ gzip:   0.29 kB
dist/assets/index-3z4sL3CL.css    309.26 kB │ gzip:  53.07 kB
dist/assets/index-C362LDnA.js   1,175.56 kB │ gzip: 326.45 kB
✓ built in 6.14s
```

Status: ✅ **Build successful.**

> Note: Chunk size warning (> 500 kB) is a Vite optimization advisory,
> not a build failure. Consider code-splitting for production optimization.

---

## 7. Files Modified

| File | Change Type | Description |
|---|---|---|
| `backend/dependencies.py` | Rewritten | Server-controlled auth, principal registry, untrusted headers ignored |
| `backend/models/entities.py` | Modified | Added REFUNDED/REVERSED status constraints, webhook check constraints |
| `backend/routers/execution.py` | Modified | Approval actor derivation, audit endpoint role protection |
| `backend/routers/webhooks.py` | Modified | State transition matrix, input validation, refund event model |
| `backend/services/audit.py` | Modified | Per-entity chain verification, global aggregation |
| `backend/tests/test_p2_1_remediation.py` | Created | 24 new tests across all 5 remediation areas |

---

## 8. Unresolved Priority 1.1 Issues (Retained)

The following issues from Priority 1.1 remain unresolved and are explicitly
retained for future remediation:

1. **PayPal `sender_batch_id` reverse lookup**: The PayPal Payouts API does
   not provide a documented endpoint to look up a payout batch by its
   `sender_batch_id`. The recovery workflow for stranded PENDING submissions
   requires either a PayPal-side change or a local batch scan approach.

2. **Unsent submission recovery**: A crash immediately after Transaction 1
   (committing `ProviderSubmission` with status PENDING) but before the
   network request to PayPal creates a submission record that was never
   actually sent. The system cannot currently distinguish this from a crash
   after PayPal accepted the request. The record transitions to
   `REQUIRES_INVESTIGATION` status for manual human review.

3. **SQLite threading limitations**: SQLite's process-level file locking
   prevents true concurrent-session regression tests from reproducing the
   intended race conditions. The `ActiveBatchSubmission` UNIQUE constraint
   is verified but the concurrent-request test documents the SQLite
   limitation and recommends PostgreSQL integration testing.

4. **Automated reconciliation daemon**: No automated periodic reconciliation
   process exists. Stranded submissions require manual `refresh-status`
   polling or webhook delivery.

---

## 9. Security Posture Statement

This implementation is a **prototype demonstration** of financial payment
coordination. The following claims are explicitly **NOT** made:

- ❌ Production-grade authentication (current: API key registry, not
  enterprise SSO/OAuth2/OIDC)
- ❌ Immutable audit storage (current: in-database hash chain, not
  externally anchored WORM/Merkle)
- ❌ Live settlement capability (current: PayPal Sandbox only)
- ❌ Regulatory compliance certification
- ❌ PCI DSS compliance

The following security properties **ARE** provided within the prototype scope:

- ✅ Server-controlled identity and role assignment
- ✅ Client-asserted headers are logged and ignored
- ✅ Fail-closed authentication in protected environments
- ✅ Explicit state transition matrix preventing terminal reversals
- ✅ Refund/reversal events modelled separately with timestamp verification
- ✅ Database-enforced webhook deduplication and status constraints
- ✅ Per-entity audit chain verification with tampering detection
- ✅ Role-based access control on sensitive audit endpoints
- ✅ Strict input validation rejecting malformed webhook payloads

---

*Report generated: 2026-11-12 | PUFI pufi-0.2.1 | Priority 2.1 Remediation*
