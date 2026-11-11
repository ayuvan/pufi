# PUFI ENTERPRISE 2.0 — FRONTEND REPOSITORY AUDIT & SYSTEM ARCHITECTURE

## 1. Executive Summary

This document establishes the authoritative initial baseline audit for the **PUFI Enterprise 2.0** frontend redesign. PUFI (PayPal-Integrated Payment Coordination Infrastructure) is an enterprise financial platform designed to coordinate supplier payment obligations, batch management, multi-provider routing (with PayPal Sandbox integration and simulated alternatives), Gemini AI routing advisory, human maker-checker approval workflows, and immutable audit logs.

The current frontend is a functioning React + TypeScript application built on Vite and TanStack Query. While functionally complete across Days 1–5 of the PUFI roadmap, its visual hierarchy resembles a traditional prototype dashboard with heavy container boxes, inconsistent typography, and a basic tab navigation bar.

The objective of this redesign is to elevate PUFI into a tier-1 fintech platform inspired by **Mercury** (enterprise banking elegance and typographic hierarchy), **Stripe** (crisp financial tables, developer clarity, and metadata drawers), **Ramp** (spend management analytics), and **CashPod** (modern subtle motion and depth), while **strictly preserving all backend endpoints and financial logic**.

---

## 2. Existing Pages and Routes

The application currently uses hash-based client routing (`window.location.hash` with `hashchange` listeners) inside `frontend/src/App.tsx`:

| Hash Route | Page Component | Functional Purpose |
|---|---|---|
| `#obligations` (default) | `ObligationsPage.tsx` | View, filter, and search supplier payment obligations; status filters; summary statistics; AG Grid integration. |
| `#import` | `ImportPage.tsx` | Ingest JSON obligations via text/paste; duplicate checking; validation summary; Zapier/accounting connector guides. |
| `#batches` | `BatchesPage.tsx` | View consolidated payment batches; create batch from `VALIDATED` obligations; navigate to batch details. |
| `#batch/:id` | `BatchDetailPage.tsx` | In-depth batch operations: Bryntum lifecycle stepper, analysis trigger, dual-control approval, PayPal Sandbox submission, payment instructions list, and audit trail. |
| `#analysis` | `AnalysisPage.tsx` | Multi-provider routing strategy selector (`LOWEST_COST`, `FASTEST`, `BALANCED`), cost/fee breakdown, FX spread comparison, and Gemini AI advisory panel. |
| `#audit` | `AuditPage.tsx` | Global audit trail viewer; batch selector dropdown; actor attribution; event classification; JSON payload inspector. |
| *Modal Dialog* | `App.tsx` (Inline Modal) | **Ecosystem & Sponsors Modal**: 10 sponsor tools (AG Grid, APIMatic, Astropods, Bryntum, Channel3, Elastic, KERNEL, Postman, Render, Zapier) and IaC blueprints. |

---

## 3. Existing Component Catalog

The baseline codebase organizes components across `frontend/src/pages/` and inline sub-components:

1. **`App.tsx`**:
   - Header with official PayPal double-P monogram SVG and prototype sandbox indicator.
   - Main tab navigation bar with Lucide icons (`FileText`, `UploadCloud`, `Layers`, `Cpu`, `ShieldCheck`).
   - Sponsors modal drawer (10 sponsor integrations).
   - Global footer with sandbox disclaimers, documentation links, and GitHub reference.

2. **`ObligationsPage.tsx`**:
   - `ConnectionStatus`: Real-time backend `/api/v1/health` heartbeat.
   - `StatusBadge`: Maps `DRAFT`, `VALIDATED`, `ON_HOLD`, `READY`, `CLOSED`, `CANCELLED` to color classes.
   - `formatAmount`: Number format helper using `Intl.NumberFormat` with string inputs.
   - `AgGridReact`: Enterprise data grid with pinned columns, custom cell renderers, and tabular numbers.
   - Quick search input, status dropdown filter, and view toggles (AG Grid vs standard HTML table).
   - Pagination controls (`limit`, `offset`).

3. **`ImportPage.tsx`**:
   - `parseJsonRows`: JSON validation and parsing logic.
   - `RowResultBadge`: Accepted, Duplicate, or Invalid status badges.
   - `ImportSummary`: Metric counts for Accepted, Duplicate, Invalid, Total.
   - Textarea input with sample data injector (`EXAMPLE_JSON`).
   - Results table rendering per-row validation diagnostics and obligation IDs.
   - Expandable Zapier integration guide.

4. **`BatchesPage.tsx`**:
   - `CreateBatchCard`: Embedded creation form with multi-select table for `VALIDATED` obligations.
   - Summary metric badges: Total Batches, In Progress, Submitted, Completed.
   - Batch cards list with quick links to detail view (`#batch/:id`).
   - Delete/Archive safeguards (batches are permanent financial records).

5. **`BatchDetailPage.tsx`**:
   - `LifecycleStepper`: Bryntum-inspired 5-stage stepper (Ingestion -> Route Analysis -> Dual-Control Approval -> PayPal Sandbox Execution -> Settlement Evidence).
   - `AnalysisPanel`: On-demand financial routing engine trigger with strategy toggle and Gemini AI recommendation display.
   - `ApprovalPanel`: Maker-checker authorization requiring explicit approver ID, strategy selection, confirmed provider, and confirmed total.
   - `ExecutionPanel`: PayPal Sandbox submission CTA with gold styling and idempotency guard.
   - `InstructionsTable`: Lists individual `PaymentInstruction` records with PayPal item IDs and status.
   - `AuditSection`: Batch-specific event history.

6. **`AnalysisPage.tsx`**:
   - Global financial analysis interface with manual batch ID lookup and quick-batch switcher.
   - `ProviderRow`: Renders provider capability, eligibility status, exclusion reasons, fee breakdown, FX spread, total cost, and processing time.
   - `AiPanel`: Gemini AI recommendation card highlighting reason factors, fallback indicator, and disclaimer.

7. **`AuditPage.tsx`**:
   - Quick batch dropdown switcher.
   - Filterable timeline table of audit events.
   - Expandable JSON details inspector (`details_redacted`).

---

## 4. Complete API Endpoint Inventory & Data Structures

All interactions route through `frontend/src/api/client.ts` via base URL `/api/v1`, proxied by Vite to `http://localhost:8000`:

### A. Health Check
- **Endpoint**: `GET /api/v1/health`
- **Request**: None
- **Response**:
  ```json
  {
    "status": "ok",
    "version": "0.1.0",
    "correlation_id": "uuid-string"
  }
  ```

### B. Payment Obligations
- **Endpoint**: `GET /api/v1/obligations?limit=50&offset=0&status=VALIDATED`
- **Query Params**:
  - `limit` (int, default 50)
  - `offset` (int, default 0)
  - `status` (string, optional: `DRAFT`, `VALIDATED`, `ON_HOLD`, `READY`, `CLOSED`, `CANCELLED`)
  - `business_id` (string, optional)
- **Response**:
  ```json
  {
    "items": [
      {
        "id": "uuid",
        "invoice_reference": "INV-2026-001",
        "amount": "3500.0000",
        "currency": "USD",
        "due_at": "2026-11-15",
        "status": "VALIDATED",
        "notes": "Verified against PO-882",
        "created_at": "2026-11-01T10:00:00Z",
        "supplier": {
          "id": "uuid",
          "external_reference": "SUP-001",
          "display_name": "Apex Cloud Systems",
          "country_code": "US"
        }
      }
    ],
    "total": 142,
    "limit": 50,
    "offset": 0,
    "correlation_id": "uuid"
  }
  ```

### C. Import Obligations
- **Endpoint**: `POST /api/v1/obligations/import`
- **Request Body**:
  ```json
  [
    {
      "supplier_reference": "SUP-001",
      "invoice_reference": "INV-2027-001",
      "amount": "1250.00",
      "currency": "USD",
      "due_at": "2027-01-31",
      "notes": "Optional notes"
    }
  ]
  ```
- **Response**:
  ```json
  {
    "total_rows": 1,
    "accepted": 1,
    "duplicate": 0,
    "invalid": 0,
    "results": [
      {
        "row_index": 0,
        "invoice_reference": "INV-2027-001",
        "supplier_reference": "SUP-001",
        "status": "ACCEPTED",
        "reason": null,
        "obligation_id": "uuid"
      }
    ],
    "correlation_id": "uuid"
  }
  ```

### D. Payment Batches
- **Endpoint**: `POST /api/v1/batches`
- **Request Body**:
  ```json
  {
    "batch_reference": "BATCH-2026-101",
    "obligation_ids": ["uuid-1", "uuid-2"],
    "notes": "Weekly vendor payout"
  }
  ```
- **Response**:
  ```json
  {
    "id": "uuid",
    "batch_reference": "BATCH-2026-101",
    "status": "DRAFT",
    "notes": "Weekly vendor payout",
    "created_at": "2026-11-11T08:00:00Z",
    "approved_by": null,
    "approved_at": null,
    "obligation_count": 2,
    "obligations": [
      {
        "obligation_id": "uuid-1",
        "invoice_reference": "INV-001",
        "amount": "1500.00",
        "currency": "USD",
        "supplier_name": "Acme Supplier",
        "added_at": "2026-11-11T08:00:00Z"
      }
    ]
  }
  ```

- **Endpoint**: `GET /api/v1/batches?limit=50&offset=0`
- **Response**: `Batch[]`

- **Endpoint**: `GET /api/v1/batches/{batch_id}`
- **Response**: `Batch`

### E. Financial Route Analysis
- **Endpoint**: `POST /api/v1/batches/{batch_id}/analyze?strategy=LOWEST_COST`
- **Query Params**: `strategy` (`LOWEST_COST` | `FASTEST` | `BALANCED`)
- **Response**:
  ```json
  {
    "batch_id": "uuid",
    "batch_reference": "BATCH-2026-101",
    "total_obligations": 2,
    "total_amount_by_currency": { "USD": "3000.00" },
    "provider_routes": [
      {
        "provider_code": "PAYPAL",
        "display_name": "PayPal Payouts",
        "environment": "SANDBOX",
        "is_simulated": false,
        "eligible": true,
        "exclusion_reasons": [],
        "provider_fee": "0.50",
        "fx_spread_cost": "0.00",
        "total_estimated_cost": "0.50",
        "estimated_recipient_amount": "3000.00",
        "recipient_currency": "USD",
        "quote_rate": "1.000000",
        "effective_rate": "1.000000",
        "quote_label": "LIVE",
        "quote_source": "PayPal Sandbox",
        "quoted_at": "2026-11-11T08:00:00Z",
        "expires_at": "2026-11-11T08:15:00Z",
        "warnings": [],
        "estimated_processing_hours": 1
      }
    ],
    "ai_recommendation": {
      "summary": "PayPal is the optimal route for USD payments within Sandbox limits.",
      "recommended_route": "PAYPAL",
      "reasoning_factors": ["Zero FX spread", "Instant settlement availability"],
      "warnings": [],
      "requires_human_review": false,
      "evidence_fields": ["source_currency=USD", "recipient_type=EMAIL"],
      "fallback_used": false,
      "fallback_reason": null,
      "model_name": "gemini-1.5-pro"
    },
    "routing_strategy": "LOWEST_COST",
    "correlation_id": "uuid",
    "analysis_label": "SIMULATED",
    "funding_snapshot_label": "SIMULATED",
    "disclaimer": "Analysis is advisory only..."
  }
  ```

### F. Approval & Execution
- **Endpoint**: `POST /api/v1/batches/{batch_id}/approve`
- **Request Body**:
  ```json
  {
    "approver_id": "USR-FIN-001",
    "routing_strategy": "LOWEST_COST",
    "selected_provider": "PAYPAL",
    "confirmed_total": "3000.00",
    "confirmed_currency": "USD"
  }
  ```
- **Response**: `ApprovalResponse`

- **Endpoint**: `POST /api/v1/batches/{batch_id}/submit`
- **Response**: `SubmissionResponse` (`sender_batch_id`, `paypal_payout_batch_id`, etc.)

- **Endpoint**: `POST /api/v1/batches/{batch_id}/refresh-status`
- **Response**: `StatusRefreshResponse`

- **Endpoint**: `GET /api/v1/batches/{batch_id}/instructions`
- **Response**: `PaymentInstructionOut[]`

- **Endpoint**: `GET /api/v1/batches/{batch_id}/audit`
- **Response**: `AuditEventOut[]`

---

## 5. State-Management & Data Fetching

- **Server State**: Managed strictly through **TanStack Query** (`@tanstack/react-query` v5.106.0).
  - Query keys: `['health']`, `['obligations', offset, statusFilter]`, `['batches']`, `['batch', id]`, `['analysis', id, strategy]`, `['instructions', id]`, `['audit', id]`.
  - Invalidation triggers: Cache invalidation occurs systematically on import, batch creation, approval, submission, and status refresh mutations.
- **Client State**: Local state via `useState` / `useMemo` for tab selection, drawer toggles, active batch ID, filters, and form inputs.
- **URL Sync**: Hash-based history (`#obligations`, `#batches`, `#batch/:id`, etc.) enabling browser forward/back buttons and bookmarking.

---

## 6. Authentication and Session Handling

- The current prototype runs single-tenant for business ID `BIZ-ACME-001`.
- Approval workflows require an explicit human identifier (`approver_id`, e.g. `USR-FIN-CONTROLLER`).
- In backend `execution.py`, `require_api_key` dependency verifies `X-API-Key` if configured, but defaults open for local sandbox development.
- The redesigned frontend will include a dedicated profile/organization indicator in the top navbar (`ACME Global Treasury · Controller`) with active session status and environment safeguards.

---

## 7. Loading, Error, and Empty States

- **Loading States**: Previously simple text strings ("Loading eligible obligations..."). Redesign will introduce polished shimmer skeletons for metric cards, table rows, and drawer contents.
- **Error States**: Handled with alert banners displaying backend `correlation_id` and error codes (`OBLIGATION_NOT_FOUND`, `BATCH_REFERENCE_EXISTS`). Redesign will introduce structured empty/error components with retry action buttons and correlation ID copy triggers.
- **Empty States**: Present in obligations and batches, but utilitarian. Redesign will feature illustrated empty states guiding the user to the next logical operational workflow.

---

## 8. Implemented vs. Simulated Features

| Feature | Implementation Reality | User Facing Guidance |
|---|---|---|
| Obligation Ingestion & Validation | Real (FastAPI + SQLAlchemy DB) | Authoritative database records with sha256 duplicate detection. |
| Batch Grouping & Constraints | Real (DB relations) | Only `VALIDATED` obligations can be batched; atomic multi-record grouping. |
| Multi-Provider Route Evaluation | Real calculation; Simulated Provider Rates | Real engine logic; rates and fees are synthetic simulations marked `SIMULATED`. |
| Gemini AI Routing Advisory | Real Gemini API call with deterministic fallback | Clearly marked as advisory AI; does NOT execute payments. |
| Dual-Control Approval | Real DB state transition | Enforces confirmed total, currency, and provider consistency. |
| PayPal Sandbox Payouts | Real PayPal Sandbox API call (when creds configured) | Strictly `SANDBOX` test accounts; USD-only restriction; clear visual disclaimers. |
| Audit Trail | Real DB audit log (`audit_events` table) | Captures real actors, event types, correlation IDs, and redacted state diffs. |

---

## 9. Dependency Assessment

- **React**: 19.3.1 (Latest)
- **Vite**: 8.3.5
- **TypeScript**: 7.0.2
- **Lucide React**: 1.71.0 (Comprehensive fintech icons)
- **TanStack Query**: 5.106.0
- **AG Grid Community / React**: 36.3.0
- **PayPal React SDK**: 10.6.1

*Design System Note*: To guarantee absolute stability on React 19 without peer-dependency conflicts or bundler bloat, the redesign will implement custom, highly performant SVG charting components (interactive area graphs, donut distribution charts, comparative provider bars, and sparklines), paired with CSS custom properties for instant light/dark theme switching, and smooth CSS cubic-bezier transitions matching Motion specs.
