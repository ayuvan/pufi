import { useQuery } from '@tanstack/react-query'
import { fetchObligations, fetchHealth, type Obligation, type ObligationStatus } from '../api/client'
import { useState } from 'react'

// -------------------------------------------------------------------------
// Status badge helpers
// -------------------------------------------------------------------------

const STATUS_LABELS: Record<ObligationStatus, string> = {
  DRAFT: 'Draft',
  VALIDATED: 'Validated',
  ON_HOLD: 'On Hold',
  READY: 'Ready',
  CLOSED: 'Closed',
  CANCELLED: 'Cancelled',
}

const STATUS_CLASSES: Record<ObligationStatus, string> = {
  DRAFT: 'status-draft',
  VALIDATED: 'status-validated',
  ON_HOLD: 'status-hold',
  READY: 'status-ready',
  CLOSED: 'status-closed',
  CANCELLED: 'status-cancelled',
}

function StatusBadge({ status }: { status: ObligationStatus }) {
  return (
    <span className={`status-badge ${STATUS_CLASSES[status] ?? 'status-draft'}`}>
      {STATUS_LABELS[status] ?? status}
    </span>
  )
}

// -------------------------------------------------------------------------
// Amount formatter
// -------------------------------------------------------------------------

/** Format a decimal string amount for display. Never converts to Number for arithmetic. */
function formatAmount(amount: string, currency: string): string {
  // Parse to float for display only — never use this for financial arithmetic.
  const num = parseFloat(amount)
  if (isNaN(num)) return `${amount} ${currency}`
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: currency || 'USD',
    minimumFractionDigits: 2,
  }).format(num)
}

// -------------------------------------------------------------------------
// Connection status bar
// -------------------------------------------------------------------------

function ConnectionStatus() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['health'],
    queryFn: fetchHealth,
    refetchInterval: 30_000,
  })

  if (isLoading) return <div className="connection-bar connecting">Connecting to backend…</div>
  if (isError) return <div className="connection-bar error">⚠ Backend unreachable — is the FastAPI server running?</div>
  return (
    <div className="connection-bar ok">
      ✓ Backend connected — PUFI API v{data?.version}
    </div>
  )
}

// -------------------------------------------------------------------------
// Obligations table
// -------------------------------------------------------------------------

const PAGE_SIZE = 25

export default function ObligationsPage() {
  const [offset, setOffset] = useState(0)
  const [statusFilter, setStatusFilter] = useState<ObligationStatus | ''>('')

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['obligations', offset, statusFilter],
    queryFn: () =>
      fetchObligations({
        limit: PAGE_SIZE,
        offset,
        status: statusFilter || undefined,
      }),
    placeholderData: (prev) => prev,
  })

  const obligations = data?.items ?? []
  const total = data?.total ?? 0
  const totalPages = Math.ceil(total / PAGE_SIZE)
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1

  return (
    <div className="page">
      <ConnectionStatus />

      <div className="page-header">
        <div>
          <h1 className="page-title">Payment Obligations</h1>
          <p className="page-subtitle">
            Synthetic demo data — {total} obligation{total !== 1 ? 's' : ''} loaded
          </p>
        </div>
        <div className="page-actions">
          <select
            className="select"
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value as ObligationStatus | '')
              setOffset(0)
            }}
            aria-label="Filter by status"
          >
            <option value="">All statuses</option>
            <option value="DRAFT">Draft</option>
            <option value="VALIDATED">Validated</option>
            <option value="ON_HOLD">On Hold</option>
            <option value="READY">Ready</option>
            <option value="CLOSED">Closed</option>
            <option value="CANCELLED">Cancelled</option>
          </select>
        </div>
      </div>

      {isError && (
        <div className="alert alert-error" role="alert">
          <strong>Failed to load obligations.</strong>{' '}
          {(error as { error?: { message?: string } })?.error?.message ?? 'Unknown error'}
        </div>
      )}

      {isLoading ? (
        <div className="loading-state" aria-live="polite">Loading obligations…</div>
      ) : obligations.length === 0 ? (
        <div className="empty-state">
          <p>No obligations found.</p>
          <p className="empty-hint">Run <code>python seed.py</code> in the backend to load synthetic data.</p>
        </div>
      ) : (
        <>
          <div className="table-wrapper" role="region" aria-label="Obligations table">
            <table className="obligations-table">
              <thead>
                <tr>
                  <th scope="col">Invoice Ref</th>
                  <th scope="col">Supplier</th>
                  <th scope="col">Country</th>
                  <th scope="col" className="col-amount">Amount</th>
                  <th scope="col">Currency</th>
                  <th scope="col">Due Date</th>
                  <th scope="col">Status</th>
                  <th scope="col">Notes</th>
                </tr>
              </thead>
              <tbody>
                {obligations.map((ob: Obligation) => (
                  <tr key={ob.id} className={ob.currency === 'ZZZ' ? 'row-warning' : ''}>
                    <td className="col-invoice">
                      <code>{ob.invoice_reference}</code>
                    </td>
                    <td>{ob.supplier.display_name}</td>
                    <td>
                      <span className="country-badge" title={ob.supplier.country_code}>
                        {ob.supplier.country_code}
                      </span>
                    </td>
                    <td className="col-amount">
                      {formatAmount(ob.amount, ob.currency)}
                    </td>
                    <td>
                      <span className={ob.currency === 'ZZZ' ? 'currency-invalid' : 'currency-code'}>
                        {ob.currency}
                        {ob.currency === 'ZZZ' && ' ⚠'}
                      </span>
                    </td>
                    <td>{ob.due_at}</td>
                    <td>
                      <StatusBadge status={ob.status as ObligationStatus} />
                    </td>
                    <td className="col-notes">
                      <span className="notes-text" title={ob.notes ?? ''}>
                        {ob.notes ?? '—'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="pagination" role="navigation" aria-label="Pagination">
              <button
                className="btn btn-secondary"
                onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
                disabled={offset === 0}
                aria-label="Previous page"
              >
                ← Prev
              </button>
              <span className="pagination-info">
                Page {currentPage} of {totalPages} ({total} total)
              </span>
              <button
                className="btn btn-secondary"
                onClick={() => setOffset(offset + PAGE_SIZE)}
                disabled={offset + PAGE_SIZE >= total}
                aria-label="Next page"
              >
                Next →
              </button>
            </div>
          )}

          <p className="disclaimer">
            ⓘ Amounts displayed for analysis only. No real money movement.
            Duplicate and invalid records visible for Day 2 validation demo.
          </p>
        </>
      )}
    </div>
  )
}
