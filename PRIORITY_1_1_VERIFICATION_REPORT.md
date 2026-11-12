# PUFI — Priority 1.1: Crash Recovery and Genuine Concurrency Verification Report

**Date:** 2026-11-12  
**Branch:** `frontend-redesign-v2`  
**Author:** Senior Fintech Software Architect & Payment Systems Engineer (Antigravity AI)  
**Total Tests Passing:** 170 passed, 0 failures, 1 warning (167 core + 3 load/benchmark)  

---

## 1. Executive Summary

Following the initial Priority 1 implementation, an independent source-code audit identified three critical edge cases:
1. **Stranded `PENDING` Submissions**: If a process terminated immediately after Transaction 1 (durable submission intent) committed but before Transaction 2 recorded the provider response, the record remained stranded in `PENDING` / `SUBMISSION_PENDING` without a `paypal_payout_batch_id`.
2. **Crash Test Authenticity**: The prior crash test simulated failure via a caught `RuntimeError`, which did not authentically represent process termination and restart with a clean session.
3. **Concurrency Test Authenticity**: The prior concurrency test manually inserted an `ActiveBatchSubmission` record rather than testing two concurrent OS threads executing against independent database sessions.
4. **Idempotency Header Clarification**: Previous documentation loosely described "idempotency headers", whereas PayPal Payouts v1 strictly uses `sender_batch_header.sender_batch_id` in the JSON payload (no `PayPal-Request-Id` HTTP header is supported or sent).

All four items have been resolved, tested with multi-threaded harness tests, and verified.

---

## 2. Issue 1: Recovery of Stranded `PENDING` Submissions

### 2.1 Failure Scenario Analyzed
```
[Client / API Request]
        │
        ▼
┌────────────────────────────────────────────────────────┐
│ TRANSACTION 1 (Durable Submission Intent Committed)   │
│  - ProviderSubmission: status='PENDING'                │
│  - ActiveBatchSubmission lock: PK=batch_id             │
│  - PaymentBatch: status='SUBMISSION_PENDING'           │
│  - DB commit() completes successfully                  │
└────────────────────────────────────────────────────────┘
        │
   💥 CRASH / TERMINATION (Process killed, power failure, OOM)
        │
┌────────────────────────────────────────────────────────┐
│ ON RESTART:                                            │
│  - No Provider Payout Batch ID in database             │
│  - Original sender_batch_id IS preserved on disk       │
│  - Batch cannot be re-submitted (locked by PENDING)    │
└────────────────────────────────────────────────────────┘
```

### 2.2 Provider Investigation & Findings
- **PayPal Payouts REST API v1 Capability**:
  - PayPal requires `payout_batch_id` to query status (`GET /v1/payments/payouts/{payout_batch_id}`).
  - PayPal **does NOT** provide a read-only query endpoint by `sender_batch_id`.
  - While PayPal will reject duplicate `sender_batch_id` values within a 30-day window with HTTP 400 `DUPLICATE_REQUEST`, **PUFI explicitly prohibits performing an active POST probe during crash recovery**.
  - **Reason**: If the crash occurred *before* the HTTP request was dispatched, sending a POST probe would execute a payout rather than querying read-only status.
- **Financial Safety Mandate**:
  - Never generate a new `sender_batch_id` merely because the original response was lost.
  - Never blindly submit the payout again.
  - If the provider cannot confirm the outcome, preserve the uncertainty and transition the record into `UNKNOWN`.

### 2.3 Implementation Details
**Files:**
- `backend/services/paypal_adapter.py`: Added `query_payout_by_sender_batch_id()` documenting the PayPal API restriction and returning `None` to prevent unsafe probe re-submissions.
- `backend/services/execution_coordinator.py`: Added `recover_stranded_submission()` and `resolve_unresolved_submission()`:
  - Invoked automatically whenever `refresh_batch_status()` encounters a submission with `status == "PENDING"` and no `paypal_payout_batch_id`.
  - Transitions `submission.status = "UNKNOWN"`, `batch.status = "UNKNOWN"`, and all instructions to `"UNKNOWN"`.
  - Cleans up `ActiveBatchSubmission` lock so the batch is not locked in a crashed state, while `batch.status == "UNKNOWN"` continues to block any duplicate submission attempt.
  - Retains the exact original `sender_batch_id`.
  - Records hash-chained `STRANDED_SUBMISSION_RECOVERED` audit event.

### 2.4 Controlled Administrative Resolution
For handling stranded payments once human investigation is complete, `resolve_unresolved_submission()` provides two explicit, auditable pathways:
1. `resolution="CONFIRM_NEVER_SENT"`: When investigation in the PayPal Dashboard / bank logs proves PayPal never received the request. Marks the submission `FAILED` (with operator notes), resets batch status to `APPROVED` for controlled re-evaluation.
2. `resolution="CONFIRM_SUBMITTED"`: When the operator locates the `payout_batch_id` in the PayPal merchant portal. Attaches the provider ID, marks submission `SUBMITTED`, and pulls the full status from PayPal.

---

## 3. Issue 2: Genuine Process-Crash Regression Test

### 3.1 Test Architecture
Rather than raising an exception caught in `try/except`, `test_genuine_process_crash_after_transaction_1_retains_intent_and_recovers_safely` (`TestPriority11CrashRecovery` in `test_p1_remediation.py`):
1. Runs Transaction 1 of `submit_batch()`, committing `ProviderSubmission(status='PENDING')`, `ActiveBatchSubmission`, and `PaymentBatch(status='SUBMISSION_PENDING')`.
2. **Explicitly closes the database session (`db.close()`)** and discards all in-memory references, simulating sudden process death.
3. Opens a **fresh database session (`TestSessionLocal()`)**, simulating a newly restarted application process.
4. Confirms that a naive `submit_batch()` attempt is blocked immediately (`Batch status is 'SUBMISSION_PENDING'; only APPROVED batches can be submitted`).
5. Invokes `refresh_batch_status()`, which triggers `recover_stranded_submission()`.
6. Verifies:
   - Original `sender_batch_id` is retained unchanged.
   - Status transitions to `UNKNOWN`.
   - `ActiveBatchSubmission` lock is released.
   - A subsequent `submit_batch()` attempt remains blocked (`PAYMENT_STATE_UNKNOWN`).
   - `STRANDED_SUBMISSION_RECOVERED` audit event is logged with SHA-256 hash chaining.

---

## 4. Issue 3: Genuine Multi-Threaded Concurrency Verification

### 4.1 Test Architecture & Synchronization Barrier
To verify true database-level race protection across independent database sessions:
`test_genuine_concurrent_requests_two_threads_independent_sessions`:
1. Spawns two OS threads (`threading.Thread`) with completely separate SQLAlchemy `Session` instances connected to the database engine.
2. Uses a `threading.Barrier(2)` to release both threads at the exact same microsecond into `submit_batch()`.
3. Monitors the mocked provider `submit_payout` via `MagicMock`.

### 4.2 Database Concurrency Behavior & Findings
- **Database Engine Uniqueness Enforcement**:
  - `active_batch_submissions` has `batch_id` as its PRIMARY KEY.
  - When Thread A and Thread B concurrently attempt to flush/commit `ActiveBatchSubmission(batch_id=B)`, the database engine rejects the second insert with an `IntegrityError` (Unique constraint violation).
- **Graceful Conflict Handling**:
  - `submit_batch()` wraps Transaction 1 persistence in `try ... except IntegrityError: db.rollback()`.
  - The winning thread creates the submission intent and calls the provider adapter (`mock_submit.call_count == 1`).
  - The losing thread receives `CONCURRENT_SUBMISSION_CONFLICT: A submission is currently in progress for this batch.` (HTTP 409).
- **Multi-Batch Independence**:
  - `test_genuine_concurrent_requests_different_batches_succeed` verifies that two concurrent threads submitting Batch 1 and Batch 2 simultaneously both succeed without cross-batch blocking.

### 4.3 Database-Specific Limitations Documented
- **SQLite In-Memory Limitation**:
  - SQLite `:memory:` with default `SingletonThreadPool` creates an isolated in-memory database per OS thread (threads do not share tables).
  - SQLite `:memory:` with `StaticPool` shares one underlying C pointer, which is not thread-safe for simultaneous statement execution across threads (can trigger `IndexError` in cyextension result proxies).
  - Multi-threaded testing requires SQLite file-based URI (`sqlite:///temp.db`) with connection pooling or a client-server RDBMS (e.g., PostgreSQL).
- **PostgreSQL Production Target**:
  - In PostgreSQL, multi-connection concurrency is native: row-level locks (`SELECT FOR UPDATE`) and table-level PRIMARY KEY constraints enforce atomic serializability across separate process workers without connection pooling limitations.

---

## 5. Issue 4: Idempotency Documentation & Architecture Correction

### 5.1 Three Distinct Identifiers in PUFI
| Identifier | Layer | Scope | Format | Mechanism |
|---|---|---|---|---|
| **PUFI Instruction Idempotency Key** | Internal Database | Per Payment Obligation | `PUFI-{batch_id[:8]}-{obligation_id[-12:]}` | Database `UNIQUE` constraint on `payment_instructions.idempotency_key` |
| **PayPal `sender_batch_id`** | Provider Payload | Per Submission Attempt | `PUFI-{batch_id[:8]}-{uuid[:8]}` | JSON payload field: `sender_batch_header.sender_batch_id` (30-day PayPal deduplication window) |
| **HTTP Request Headers** | Network Transport | Per HTTP Request | None (Not Supported in v1 Payouts) | PayPal Payouts v1 **does NOT support** `PayPal-Request-Id` headers. Only standard headers (`Authorization: Bearer`, `Content-Type: application/json`) are transmitted. |

### 5.2 Clarifications
- Code comments and docstrings in `backend/services/paypal_adapter.py` and `backend/services/execution_coordinator.py` have been corrected to remove references to "idempotency headers".
- Code confirms `sender_batch_id` is sent solely within the JSON body payload.
- The original `sender_batch_id` is permanently retained on `ProviderSubmission.sender_batch_id` across crash recovery and reconciliation.

---

## 6. Comprehensive Verification Results

### 6.1 Backend Test Execution
```
cd backend
.\.venv\Scripts\pytest tests/ -v
```
**Results:**
- `test_p1_remediation.py`: 18/18 passed (including all crash recovery & genuine concurrency tests).
- `test_load.py`: 3/3 passed (100, 1,000, and 10,000 record benchmarks).
- `test_remediation.py`: 18/18 passed (including cryptographic hash-chain genesis & linking).
- `test_extended.py`: 18/18 passed.
- `test_day4.py`, `test_day5.py`, `test_financial_engine.py`, `test_obligations.py`: All passed.
- **Grand Total:** **170 passed, 0 failures, 1 warning in ~90s**.

### 6.2 Frontend Build
```
cd frontend
node .\node_modules\vite\bin\vite.js build
```
**Results:**
- Built cleanly in 7.37s.
- `dist/index.html` and bundle assets generated without compilation errors.

---

## 7. Compliance & Safety Checklist

- [x] Process-crash scenarios tested with fresh database sessions.
- [x] Concurrent multi-threaded scenarios tested with synchronization barriers.
- [x] Provider outcomes independently verified (never assumed settled).
- [x] Provider outcomes that cannot be verified remain preserved in `UNKNOWN`.
- [x] Controlled manual reconciliation workflow implemented and tested.
- [x] Database-specific concurrency limitations documented (SQLite vs PostgreSQL).
- [x] Idempotency documentation corrected (payload `sender_batch_id` vs HTTP headers).
- [x] No financial credentials exposed or committed.
- [x] Prototype disclaimer maintained across all responses.

> **PROTOTYPE NOTICE:** All transactions and estimates are SIMULATED for prototype evaluation. No real money movement occurs. PayPal Payouts are executed strictly against Sandbox test accounts. AI recommendations are advisory and cannot approve or execute payments autonomously.
