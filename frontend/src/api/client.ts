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

/** Get batch detail by ID. */
export const fetchBatch = (id: string): Promise<Batch> =>
  apiFetch<Batch>(`/batches/${id}`)
