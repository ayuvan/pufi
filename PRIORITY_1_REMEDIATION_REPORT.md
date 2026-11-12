# PUFI — Priority 1 Critical Payment Safety Remediation Report

**Date:** 2026-11-12  
**Branch:** `frontend-redesign-v2`  
**Author:** Senior Fintech Engineer (Antigravity AI)  
**Baseline tests:** 152 passed, 1 warning  
**Final tests:** 165 passed, 0 errors, 1 warning  

---

## Executive Summary

An independent source-code audit identified four critical payment-execution risks in
the PUFI backend:

| # | Risk | Severity |
|---|------|----------|
| Phase 1 | No durable pre-commit record before external PayPal call | Critical |
| Phase 2 | Race condition allows two concurrent submissions for same batch | Critical |
| Phase 3 | UNKNOWN recovery incomplete; webhooks didn't cascade to Batch/Submission | High |
| Phase 4 | Credential hygiene gaps (.gitignore, packaging, startup validation) | Medium |

All four phases have been implemented, tested, and verified.  
**No existing features were removed.  No real financial transactions were introduced.**

---

## Baseline

Before any changes:

```
cd backend && .venv\Scripts\pytest tests/ -q
152 passed, 1 warning in ~48s
```

---

## Phase 1 — Durable Submission Intent

### Root Cause

The original `submit_batch()` created a `ProviderSubmission` record and called `db.flush()`
(not `db.commit()`), then immediately made the external PayPal API call.

**Risk:** A process crash *after* PayPal accepted the payout but *before* the endpoint
committed the database transaction would permanently lose the local submission record.
PUFI would have no evidence the payment was submitted.

### Implementation

**File:** `backend/services/execution_coordinator.py`

Rewrote `submit_batch()` with a **two-transaction pattern**:

```
Transaction 1  (commits BEFORE network call)
  ├─ Create ProviderSubmission (status=PENDING)
  ├─ Create ActiveBatchSubmission lock record (PK = batch_id)
  ├─ Set PaymentBatch.status = SUBMISSION_PENDING
  ├─ Record SUBMISSION_INTENT_COMMITTED audit event
  └─ db.commit()  ← durable before any network I/O

External PayPal API call (network)

Transaction 2  (commits AFTER network response)
  ├─ Re-fetch ProviderSubmission and PaymentBatch by ID
  ├─ Update status: SUBMITTED / UNKNOWN / FAILED
  ├─ Remove ActiveBatchSubmission lock
  ├─ Record SUBMISSION_COMPLETED / SUBMISSION_UNKNOWN / SUBMISSION_FAILED
  └─ db.commit()
```

**File:** `backend/models/entities.py`

- Added `intended_amount: Decimal`, `currency: str`, `item_count: int` to `ProviderSubmission`
- Added `'SUBMISSION_PENDING'` to `PaymentBatch` status CHECK constraint
- Created `ActiveBatchSubmission(Base)` model with `batch_id` as PRIMARY KEY (db-enforced lock)
- Added `'SIMULATED_IMMEDIATE_SETTLEMENT'` and `'SIMULATED_PENDING_SETTLEMENT'` to
  `settlement_evidence` CHECK constraint (simulated adapter was using these values but
  the constraint didn't allow them, causing failures)

### Acceptance Tests (all pass)

| Test | Result |
|------|--------|
| `test_submission_intent_committed_before_network_call` | ✅ PASS |
| `test_simulated_crash_after_intent_persistence` | ✅ PASS |
| `test_provider_timeout_preserves_intent_and_marks_unknown` | ✅ PASS |
| `test_subsequent_execution_blocked_while_unknown` | ✅ PASS |
| `test_provider_rejection_marks_failed_not_unknown` | ✅ PASS |

---

## Phase 2 — Concurrent Duplicate Submission Protection

### Root Cause

The original duplicate guard was an application-level check:
```python
if existing_submission:
    return error
```
Two simultaneous requests could both pass this check before either created a record —
a classic time-of-check / time-of-use (TOCTOU) race condition.

### Implementation

**File:** `backend/models/entities.py`

```python
class ActiveBatchSubmission(Base):
    __tablename__ = "active_batch_submissions"
    batch_id = Column(String, ForeignKey("payment_batches.id"), primary_key=True)
    created_at = Column(DateTime, ...)
    provider_code = Column(String, ...)
```

The PRIMARY KEY on `batch_id` provides a **database-enforced uniqueness constraint**.
Two concurrent requests cannot both INSERT into this table — the second gets an
`IntegrityError` which is caught and returned as a 409 Conflict.

**File:** `backend/routers/execution.py`

Added 409 HTTP response for concurrent conflict:
```python
if "CONCURRENT_SUBMISSION_CONFLICT" in result.error_message:
    raise HTTPException(status_code=409, detail={...})
```

UNKNOWN, PENDING, and SUBMITTED states all block new execution until reconciliation
establishes a safe outcome.

### Acceptance Tests (all pass)

| Test | Result |
|------|--------|
| `test_concurrent_submissions_same_batch_blocked` | ✅ PASS |
| `test_losing_concurrent_request_returns_conflict_409` | ✅ PASS |
| `test_concurrent_submissions_different_batches_succeed` | ✅ PASS |

---

## Phase 3 — UNKNOWN Recovery and Webhook Consistency

### Root Cause (3 cases)

**Case A:** Provider batch ID available → reconciliation via PayPal status query worked
but didn't cascade status to `PaymentBatch` or clean up `ActiveBatchSubmission`.

**Case B:** No provider batch ID (pre-network crash) → system incorrectly converted
UNKNOWN to FAILED without provider proof.

**Case C:** Webhook processing updated `PaymentInstruction` status but did NOT update
the associated `ProviderSubmission` or `PaymentBatch`. A COMPLETED instruction still
had a SUBMITTED batch.

### Implementation

**File:** `backend/services/execution_coordinator.py` — `refresh_batch_status()`:

- **Case A:** Queries PayPal for batch status; cascades results to Submission + Batch;
  cleans up `ActiveBatchSubmission` on terminal states.
- **Case B:** Records `RECONCILIATION_ATTEMPT_UNRESOLVED` audit event; explicitly does
  NOT convert UNKNOWN to FAILED; human review required.
- State precedence: `COMPLETED` instructions are never regressed by a stale provider
  re-query unless refunded/reversed/returned.

**File:** `backend/routers/webhooks.py`:

- Replaced raw `db.add(AuditEvent(...))` with `record_audit_event()` for hash chaining.
- Added state precedence: `WEBHOOK_OUT_OF_ORDER_IGNORED` when status would regress from COMPLETED.
- When applying webhook: populates `submission.paypal_payout_batch_id` if missing;
  transitions submission from UNKNOWN → SUBMITTED.
- Re-evaluates entire `PaymentBatch` status across all instructions after each webhook.
- Cleans up `ActiveBatchSubmission` on terminal batch states.
- Added handlers for batch-level events (`PAYMENT.PAYOUTSBATCH.SUCCESS/DENIED`).

### Acceptance Tests (all pass)

| Test | Result |
|------|--------|
| `test_case_a_reconciliation_with_batch_id_resolves_unknown` | ✅ PASS |
| `test_case_b_reconciliation_without_batch_id_remains_unknown` | ✅ PASS |
| `test_webhook_resolves_unknown_submission_and_batch` | ✅ PASS |
| `test_webhook_state_precedence_cannot_regress_completed` | ✅ PASS |
| `test_duplicate_webhook_ignored_idempotently` | ✅ PASS |

---

## Phase 4 — Credential & Environment Hygiene

### Findings

| Item | Status |
|------|--------|
| `.gitignore` excludes `.env`, `.env.*`, `!.env.example` | ✅ Already present |
| `.gitignore` excludes `.venv/`, `__pycache__/`, `*.sqlite`, `*.log` | ✅ Already present |
| `.gitignore` excludes `*.zip`, `release/` | ✅ **Added** |
| `git ls-files` shows only `.env.example` files tracked | ✅ Confirmed clean |
| No real credentials in any git-tracked file | ✅ Confirmed |

### New: `scripts/package_release.py`

Creates a distributable ZIP with:
- Explicit exclusion of `.env*`, `.venv/`, `__pycache__/`, `*.sqlite`, `*.db`, `*.log`,
  `node_modules/`, `dist/`, `build/`
- Inclusion of `.env.example` files
- Post-creation secret scan: detects real PayPal/Gemini credentials in archive;
  **deletes the ZIP and exits with error code 1** if found
- Manifest printed to stdout for audit

```bash
python scripts/package_release.py --version 0.1.0
# → release/pufi-0.1.0.zip (299 KB), archive clean ✅
```

### New: Startup Credential Validation (`backend/main.py`)

Added `_validate_startup_credentials()` called during lifespan startup:
- Checks `PAYPAL_CLIENT_ID` and `PAYPAL_CLIENT_SECRET` for placeholder patterns
- Logs a **WARNING** (not an error) if credentials appear unset — app continues running
- **Never logs actual credential values**
- Simulated providers remain fully functional without PayPal credentials

---

## State Machine

```
CREATED
   │
   ▼
APPROVED
   │
   ▼
SUBMISSION_PENDING  ◄── ActiveBatchSubmission lock created (db-enforced)
   │
   ├──────────────► SUBMITTED ──► PENDING ──► COMPLETED
   │                                     └──► FAILED
   │
   └──────────────► UNKNOWN
                       │
                       ▼
                 RECONCILIATION (manual or webhook)
                       │
                 ┌─────┴──────┐
                 ▼            ▼
            COMPLETED      FAILED
```

**Key invariant:** No new payout is generated while the previous outcome is UNKNOWN.
The `ActiveBatchSubmission` lock prevents concurrent double-submission at the database
level. The UNKNOWN guard in `submit_batch()` prevents retry until reconciliation clears.

---

## Test Regression Fix

The two-transaction pattern in Phase 1 caused an unexpected regression in `test_extended.py`.

**Root cause:** `submit_batch()` now calls `db.commit()` internally. The test isolation
strategy in `conftest.py` uses SQLAlchemy savepoints (`begin_nested()`) with an outer
rollback on teardown. When `db.commit()` committed the outer transaction, the teardown
rollback became a no-op, leaving hardcoded IDs (`BIZ-EXT-001`) in the shared in-memory
schema. The next test using the same fixture hit `UNIQUE constraint failed: businesses.id`.

**Fix:** Converted the `ext_setup` fixture (and all tests that used its hardcoded
`external_reference` strings) to use `uuid.uuid4()`-based IDs, mirroring the pattern
already used by `seeded_batch_id`. No production code was changed.

---

## Files Changed

| File | Change |
|------|--------|
| `backend/models/entities.py` | `ActiveBatchSubmission` table; `SUBMISSION_PENDING` batch status; `intended_amount/currency/item_count` on `ProviderSubmission`; simulated settlement evidence values |
| `backend/services/execution_coordinator.py` | Two-transaction `submit_batch()`; improved Case A/B/C reconciliation; state precedence |
| `backend/routers/execution.py` | 409 conflict handling; removed duplicate `db.commit()` |
| `backend/routers/webhooks.py` | State precedence; Submission/Batch cascade; batch-level events; hash-chained audit |
| `backend/main.py` | `_validate_startup_credentials()` startup hook |
| `backend/tests/test_extended.py` | Fixed `ext_setup` fixture to use uuid-based IDs; updated supplier reference calls |
| `backend/tests/test_p1_remediation.py` | **New** — 13 acceptance tests for Phases 1–3 |
| `scripts/package_release.py` | **New** — secure release packaging with secret scan |
| `.gitignore` | Added `*.zip` and `release/` |
| `frontend/src/api/client.ts` | `ApiResponseError` class — structured `Error` subclass thrown on API failures |
| `frontend/src/pages/BatchDetailPage.tsx` | Updated `formatErrorMessage` to handle `Error` instances correctly |

---

## Final Verification

```
cd backend && .venv\Scripts\pytest tests/ -q
165 passed, 0 errors, 1 warning
```

| Metric | Before | After |
|--------|--------|-------|
| Tests passing | 152 | 165 |
| Test errors | 0 | 0 |
| New acceptance tests | 0 | +13 |
| Test regressions | 0 | 0 |
| Frontend build | ✅ | ✅ |
| Credentials in git-tracked files | None | None |
| `.env` files excluded from ZIP | N/A | ✅ |
| Duplicate submission protection | App-level only | DB-enforced (PRIMARY KEY) |
| Pre-network durable record | ❌ | ✅ |
| UNKNOWN → FAILED coercion | ❌ | Blocked — requires reconciliation |

---

> **PROTOTYPE NOTICE:** All cost estimates are SIMULATED. No real money movement occurs.
> PayPal submissions use Sandbox test accounts only. AI recommendations are advisory
> and require human approval before any action is taken.
