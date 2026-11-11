# PUFI ENTERPRISE 2.0 — FRONTEND API COMPATIBILITY SPECIFICATION

This document details every API endpoint, request body, query parameter, and response model used by the PUFI Frontend. All endpoints are hosted by FastAPI under the `/api/v1` prefix and proxied via Vite to port 8000.

---

## 1. System Endpoints

### `GET /api/v1/health`
- **Method**: `GET`
- **Purpose**: System health check, API version verification, and backend heartbeat.
- **Request Parameters**: None
- **Response Schema** (`HealthResponse`):
  ```typescript
  interface HealthResponse {
    status: string           // "ok"
    version: string          // "0.1.0"
    correlation_id: string   // UUID
  }
  ```

---

## 2. Obligation Endpoints

### `GET /api/v1/obligations`
- **Method**: `GET`
- **Purpose**: Fetch paginated supplier payment obligations with nested supplier metadata.
- **Query Parameters**:
  - `limit?: number` (default 50, min 1, max 200)
  - `offset?: number` (default 0)
  - `status?: ObligationStatus` (`DRAFT` | `VALIDATED` | `ON_HOLD` | `READY` | `CLOSED` | `CANCELLED`)
  - `business_id?: string` (optional tenant filter)
- **Response Schema** (`ObligationListResponse`):
  ```typescript
  interface ObligationListResponse {
    items: Obligation[]
    total: number
    limit: number
    offset: number
    correlation_id: string
  }

  interface Obligation {
    id: string
    invoice_reference: string
    amount: string             // Decimal string: e.g. "3500.0000"
    currency: string           // ISO 4217: e.g. "USD", "EUR"
    due_at: string             // "YYYY-MM-DD"
    status: ObligationStatus
    notes: string | null
    created_at: string
    supplier: {
      id: string
      external_reference: string
      display_name: string
      country_code: string
    }
  }
  ```

### `POST /api/v1/obligations/import`
- **Method**: `POST`
- **Purpose**: Bulk ingest raw obligation rows with automatic validation, supplier resolution, and duplicate detection.
- **Request Body** (`ObligationImportRow[]`):
  ```typescript
  interface ObligationImportRow {
    supplier_reference: string
    invoice_reference: string
    amount: string             // Numeric string > 0
    currency: string           // ISO 4217 uppercase
    due_at: string             // "YYYY-MM-DD"
    notes?: string
  }
  ```
- **Response Schema** (`ImportResponse`):
  ```typescript
  interface ImportResponse {
    total_rows: number
    accepted: number
    duplicate: number
    invalid: number
    results: ImportRowResult[]
    correlation_id: string
  }

  interface ImportRowResult {
    row_index: number
    invoice_reference: string
    supplier_reference: string
    status: 'ACCEPTED' | 'DUPLICATE' | 'INVALID'
    reason: string | null
    obligation_id: string | null
  }
  ```

---

## 3. Batch Endpoints

### `POST /api/v1/batches`
- **Method**: `POST`
- **Purpose**: Create a consolidated payment batch from a list of pre-validated obligations.
- **Request Body** (`BatchCreateRequest`):
  ```typescript
  interface BatchCreateRequest {
    batch_reference: string
    obligation_ids: string[]
    notes?: string
  }
  ```
- **Constraint**: All obligation IDs must be in `VALIDATED` status. Returns 422 `OBLIGATION_NOT_VALIDATED` if any is unvalidated.
- **Response Schema** (`Batch`):
  ```typescript
  interface Batch {
    id: string
    batch_reference: string
    status: string             // "DRAFT", "ANALYZED", "APPROVED", "SUBMITTED", "COMPLETED"
    notes: string | null
    created_at: string
    approved_by: string | null
    approved_at: string | null
    obligation_count: number
    obligations: BatchObligationSummary[]
  }

  interface BatchObligationSummary {
    obligation_id: string
    invoice_reference: string
    amount: string
    currency: string
    supplier_name: string
    added_at: string
  }
  ```

### `GET /api/v1/batches`
- **Method**: `GET`
- **Purpose**: List all batches ordered by creation timestamp descending.
- **Query Parameters**:
  - `limit?: number`
  - `offset?: number`
- **Response Schema**: `Batch[]`

### `GET /api/v1/batches/{batch_id}`
- **Method**: `GET`
- **Purpose**: Retrieve full details of a specific batch including associated obligations.
- **Response Schema**: `Batch`

---

## 4. Routing & Financial Analysis Endpoints

### `POST /api/v1/batches/{batch_id}/analyze`
- **Method**: `POST`
- **Purpose**: Run multi-provider route evaluation, cost calculations, FX fee analysis, and Gemini AI advisory.
- **Query Parameters**:
  - `strategy: 'LOWEST_COST' | 'FASTEST' | 'BALANCED'` (default: `'LOWEST_COST'`)
- **Response Schema** (`BatchAnalysis`):
  ```typescript
  interface BatchAnalysis {
    batch_id: string
    batch_reference: string
    total_obligations: number
    total_amount_by_currency: Record<string, string>
    provider_routes: ProviderRoute[]
    ai_recommendation: AiRecommendation | null
    routing_strategy: string
    correlation_id: string
    analysis_label: string              // "SIMULATED"
    funding_snapshot_label: string      // "SIMULATED"
    disclaimer: string
  }

  interface ProviderRoute {
    provider_code: string
    display_name: string
    environment: string                // "SANDBOX" | "SIMULATED"
    is_simulated: boolean
    eligible: boolean
    exclusion_reasons: string[]
    provider_fee: string | null
    fx_spread_cost: string | null
    total_estimated_cost: string | null
    estimated_recipient_amount: string | null
    recipient_currency: string | null
    quote_rate: string | null
    effective_rate: string | null
    quote_label: string                // "LIVE" | "SIMULATED"
    quote_source: string
    quoted_at: string | null
    expires_at: string | null
    warnings: string[]
    estimated_processing_hours: number | null
  }

  interface AiRecommendation {
    summary: string
    recommended_route: string | null
    reasoning_factors: string[]
    warnings: string[]
    requires_human_review: boolean
    evidence_fields: string[]
    fallback_used: boolean
    fallback_reason: string | null
    model_name: string
  }
  ```

---

## 5. Approval & Execution Endpoints

### `POST /api/v1/batches/{batch_id}/approve`
- **Method**: `POST`
- **Purpose**: Dual-control human approval recording approver identity and confirming financial figures.
- **Request Body** (`ApproveRequest`):
  ```typescript
  interface ApproveRequest {
    approver_id: string
    routing_strategy: string
    selected_provider: string
    confirmed_total: string
    confirmed_currency: string
  }
  ```
- **Response Schema** (`ApprovalResponse`):
  ```typescript
  interface ApprovalResponse {
    batch_id: string
    status: string                     // "APPROVED"
    approved_by: string
    approved_at: string
    selected_provider: string
    confirmed_total: string
    confirmed_currency: string
    approved_recipient_count: number
    routing_strategy: string
    analysis_snapshot_id: string | null
    message: string
  }
  ```

### `POST /api/v1/batches/{batch_id}/submit`
- **Method**: `POST`
- **Purpose**: Transmit approved batch to PayPal Sandbox Payouts API.
- **Request Body**: None
- **Response Schema** (`SubmissionResponse`):
  ```typescript
  interface SubmissionResponse {
    success: boolean
    batch_id: string
    sender_batch_id: string
    paypal_payout_batch_id: string | null
    paypal_batch_status: string | null
    submission_status: string
    submitted_at: string
    is_simulated: boolean
    paypal_configured: boolean
    error_message: string | null
    disclaimer: string
  }
  ```

### `POST /api/v1/batches/{batch_id}/refresh-status`
- **Method**: `POST`
- **Purpose**: Poll PayPal Payouts API for real-time status and settlement outcomes.
- **Request Body**: None
- **Response Schema** (`StatusRefreshResponse`):
  ```typescript
  interface StatusRefreshResponse {
    success: boolean
    batch_id: string
    batch_status: string
    paypal_batch_status: string | null
    items_checked: number
    completed: number
    failed: number
    pending: number
    unknown: number
    refreshed_at: string
    error_message: string | null
    disclaimer: string
  }
  ```

### `GET /api/v1/batches/{batch_id}/instructions`
- **Method**: `GET`
- **Purpose**: Retrieve itemized payment instructions with PayPal payout IDs and settlement evidence.
- **Response Schema**: `PaymentInstructionOut[]`
  ```typescript
  interface PaymentInstructionOut {
    id: string
    batch_id: string
    obligation_id: string
    provider_code: string
    amount: string
    currency: string
    status: string
    settlement_evidence: string
    idempotency_key: string
    sender_item_id: string
    paypal_payout_item_id: string | null
    paypal_transaction_id: string | null
    paypal_item_status: string | null
    error_message: string | null
    created_at: string
    updated_at: string | null
  }
  ```

### `GET /api/v1/batches/{batch_id}/audit`
- **Method**: `GET`
- **Purpose**: Fetch tamper-evident audit events recorded for the batch.
- **Response Schema**: `AuditEventOut[]`
  ```typescript
  interface AuditEventOut {
    id: string
    entity_type: string
    entity_id: string
    event_type: string
    actor: string
    correlation_id: string | null
    details_redacted: string | null
    created_at: string
  }
  ```

---

## 6. Error Response Envelope

All non-2xx API responses return the following standard JSON payload:
```typescript
interface ApiError {
  error: {
    code: string
    message: string
  }
  correlation_id: string
}
```
Client code must always extract both `error.message` and `correlation_id` to present actionable feedback to the user.
