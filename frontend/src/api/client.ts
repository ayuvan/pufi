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
// Types
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
