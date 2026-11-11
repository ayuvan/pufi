/**
 * PUFI API client
 *
 * Typed fetch wrapper for all backend API calls.
 * Base URL is relative so it works through the Vite dev proxy (/api → localhost:8000).
 *
 * Monetary amounts returned by the API are strings.  Never convert to Number — use
 * them as strings for display, or parse with a Decimal library if arithmetic is needed.
 */

const BASE = '/api/v1'

// -------------------------------------------------------------------------
// Shared types
// -------------------------------------------------------------------------

export interface SupplierSummary {
  id: string
  external_reference: string
  display_name: string
  country_code: string
}

export interface Obligation {
  id: string
  invoice_reference: string
  /** Monetary amount as a decimal string, e.g. "3500.0000" */
  amount: string
  currency: string
  /** ISO 8601 date string, e.g. "2026-11-15" */
  due_at: string
  status: ObligationStatus
  notes: string | null
  created_at: string
  supplier: SupplierSummary
}

export type ObligationStatus =
  | 'DRAFT'
  | 'VALIDATED'
  | 'ON_HOLD'
  | 'READY'
  | 'CLOSED'
  | 'CANCELLED'

export interface ObligationListResponse {
  items: Obligation[]
  total: number
  limit: number
  offset: number
  correlation_id: string
}

export interface HealthResponse {
  status: string
  version: string
  correlation_id: string
}

export interface ApiError {
  error: { code: string; message: string }
  correlation_id: string
}

// -------------------------------------------------------------------------
// Day 2: Import types
// -------------------------------------------------------------------------

export interface ObligationImportRow {
  supplier_reference: string
  invoice_reference: string
  amount: string
  currency: string
  due_at: string
  notes?: string
}

export type ImportResultStatus = 'ACCEPTED' | 'DUPLICATE' | 'INVALID'

export interface ImportRowResult {
  row_index: number
  invoice_reference: string
  supplier_reference: string
  status: ImportResultStatus
  reason: string | null
  obligation_id: string | null
}

export interface ImportResponse {
  total_rows: number
  accepted: number
  duplicate: number
  invalid: number
  results: ImportRowResult[]
  correlation_id: string
}

// -------------------------------------------------------------------------
// Day 2: Batch types
// -------------------------------------------------------------------------

export interface BatchObligationSummary {
  obligation_id: string
  invoice_reference: string
  amount: string
  currency: string
  supplier_name: string
  added_at: string
}

export interface Batch {
  id: string
  batch_reference: string
  status: string
  notes: string | null
  created_at: string
  approved_by: string | null
  approved_at: string | null
  obligation_count: number
  obligations: BatchObligationSummary[]
}

export interface BatchCreateRequest {
  batch_reference: string
  obligation_ids: string[]
  notes?: string
}

// -------------------------------------------------------------------------
// Core fetch helper
// -------------------------------------------------------------------------

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({ error: { code: 'UNKNOWN', message: res.statusText } }))
    throw body as ApiError
  }
  return res.json() as Promise<T>
}

// -------------------------------------------------------------------------
// Endpoints
// -------------------------------------------------------------------------

/** Check backend health. */
export const fetchHealth = (): Promise<HealthResponse> =>
  apiFetch<HealthResponse>('/health')

/** List obligations with optional pagination and status filter. */
export const fetchObligations = (params?: {
  limit?: number
  offset?: number
  status?: ObligationStatus
}): Promise<ObligationListResponse> => {
  const qs = new URLSearchParams()
  if (params?.limit != null) qs.set('limit', String(params.limit))
  if (params?.offset != null) qs.set('offset', String(params.offset))
  if (params?.status) qs.set('status', params.status)
  const query = qs.toString() ? `?${qs.toString()}` : ''
  return apiFetch<ObligationListResponse>(`/obligations${query}`)
}

/** Import obligation rows and get per-row validation results. */
export const importObligations = (rows: ObligationImportRow[]): Promise<ImportResponse> =>
  apiFetch<ImportResponse>('/obligations/import', {
    method: 'POST',
    body: JSON.stringify(rows),
  })

/** Create a payment batch from validated obligation IDs. */
export const createBatch = (req: BatchCreateRequest): Promise<Batch> =>
  apiFetch<Batch>('/batches', {
    method: 'POST',
    body: JSON.stringify(req),
  })

/** List all payment batches. */
export const fetchBatches = (params?: { limit?: number; offset?: number }): Promise<Batch[]> => {
  const qs = new URLSearchParams()
  if (params?.limit != null) qs.set('limit', String(params.limit))
  if (params?.offset != null) qs.set('offset', String(params.offset))
  const query = qs.toString() ? `?${qs.toString()}` : ''
  return apiFetch<Batch[]>(`/batches${query}`)
}

/** Get batch detail by ID. */
export const fetchBatch = (id: string): Promise<Batch> =>
  apiFetch<Batch>(`/batches/${id}`)

// -------------------------------------------------------------------------
// Day 3: Financial Analysis types
// -------------------------------------------------------------------------

export interface ProviderRoute {
  provider_code: string
  display_name: string
  environment: string
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
  quote_label: string
  quote_source: string
  quoted_at: string | null
  expires_at: string | null
  warnings: string[]
  estimated_processing_hours: number | null
}

export interface AiRecommendation {
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

export interface BatchAnalysis {
  batch_id: string
  batch_reference: string
  total_obligations: number
  total_amount_by_currency: Record<string, string>
  provider_routes: ProviderRoute[]
  ai_recommendation: AiRecommendation | null
  routing_strategy: string
  correlation_id: string
  analysis_label: string
  funding_snapshot_label: string
  disclaimer: string
}

/** Run financial analysis for a batch (POST — triggers deterministic routing + AI advisory). */
export const fetchBatchAnalysis = (
  batchId: string,
  strategy: 'LOWEST_COST' | 'FASTEST' | 'BALANCED' = 'LOWEST_COST'
): Promise<BatchAnalysis> =>
  apiFetch<BatchAnalysis>(
    `/batches/${batchId}/analyze?strategy=${strategy}`,
    { method: 'POST' }
  )

// -------------------------------------------------------------------------
// Day 4: Approval & execution types
// -------------------------------------------------------------------------

export interface ApproveRequest {
  approver_id: string
  routing_strategy: string
  /** Must match backend field name: selected_provider */
  selected_provider: string
  /** Must match backend field name: confirmed_total (Decimal string) */
  confirmed_total: string
  confirmed_currency: string
}

export interface ApprovalResponse {
  batch_id: string
  status: string
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

export interface SubmissionResponse {
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

export interface StatusRefreshResponse {
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

export interface PaymentInstructionOut {
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

export interface AuditEventOut {
  id: string
  entity_type: string
  entity_id: string
  event_type: string
  actor: string
  correlation_id: string | null
  details_redacted: string | null
  created_at: string
}

// -------------------------------------------------------------------------
// Day 4: Endpoints
// -------------------------------------------------------------------------

/** Approve a batch for PayPal Sandbox submission. */
export const approveBatch = (
  batchId: string,
  body: ApproveRequest
): Promise<ApprovalResponse> =>
  apiFetch<ApprovalResponse>(`/batches/${batchId}/approve`, {
    method: 'POST',
    body: JSON.stringify(body),
  })

/** Submit an approved batch to PayPal Sandbox. */
export const submitBatch = (batchId: string): Promise<SubmissionResponse> =>
  apiFetch<SubmissionResponse>(`/batches/${batchId}/submit`, { method: 'POST' })

/** Refresh batch and item statuses from PayPal. */
export const refreshBatchStatus = (batchId: string): Promise<StatusRefreshResponse> =>
  apiFetch<StatusRefreshResponse>(`/batches/${batchId}/refresh-status`, { method: 'POST' })

/** Get payment instructions for a batch. */
export const fetchInstructions = (batchId: string): Promise<PaymentInstructionOut[]> =>
  apiFetch<PaymentInstructionOut[]>(`/batches/${batchId}/instructions`)

/** Get audit events for a batch. */
export const fetchAuditEvents = (batchId: string): Promise<AuditEventOut[]> =>
  apiFetch<AuditEventOut[]>(`/batches/${batchId}/audit`)
