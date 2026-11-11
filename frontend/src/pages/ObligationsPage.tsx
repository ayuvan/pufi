import { useQuery } from '@tanstack/react-query'
import { fetchObligations, fetchHealth, type Obligation, type ObligationStatus } from '../api/client'
import { useState, useMemo } from 'react'
import { AgGridReact } from 'ag-grid-react'
import type { ColDef } from 'ag-grid-community'
import { Search, Grid, Table as TableIcon, Sparkles } from 'lucide-react'

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
  const num = parseFloat(amount)
  if (isNaN(num)) return `${amount} ${currency}`
  try {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency || 'USD',
      minimumFractionDigits: 2,
    }).format(num)
  } catch {
    return `${num.toFixed(2)} ${currency}`
  }
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
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', background: '#007934' }} />
        <span><strong>PUFI API v{data?.version} Connected</strong> • Environment: PayPal Sandbox</span>
      </div>
      <div style={{ fontSize: '0.76rem', color: '#166534' }}>
        Database: SQLite / PostgreSQL Target • AI Advisor: Active
      </div>
    </div>
  )
}

// -------------------------------------------------------------------------
// Obligations Page
// -------------------------------------------------------------------------

const PAGE_SIZE = 100

export default function ObligationsPage() {
  const [offset, setOffset] = useState(0)
  const [statusFilter, setStatusFilter] = useState<ObligationStatus | ''>('')
  const [useAgGrid, setUseAgGrid] = useState(true)
  const [quickFilterText, setQuickFilterText] = useState('')

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

  // AG Grid Column Definitions
  const columnDefs = useMemo<ColDef<Obligation>[]>(() => [
    {
      field: 'invoice_reference',
      headerName: 'Invoice Ref',
      pinned: 'left',
      width: 170,
      cellRenderer: (params: { value?: string }) => (
        <code style={{ fontFamily: 'monospace', fontWeight: 700, color: '#003087' }}>
          {params.value}
        </code>
      ),
    },
    {
      headerName: 'Supplier Name',
      valueGetter: (params) => params.data?.supplier.display_name,
      minWidth: 200,
      flex: 1,
    },
    {
      headerName: 'Country',
      width: 110,
      valueGetter: (params) => params.data?.supplier.country_code,
      cellRenderer: (params: { value?: string }) => (
        <span className="country-badge">{params.value}</span>
      ),
    },
    {
      field: 'amount',
      headerName: 'Obligation Amount',
      width: 160,
      type: 'rightAligned',
      cellRenderer: (params: { data?: Obligation }) => (
        <span style={{ fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>
          {params.data ? formatAmount(params.data.amount, params.data.currency) : ''}
        </span>
      ),
    },
    {
      field: 'currency',
      headerName: 'Currency',
      width: 110,
      cellRenderer: (params: { value?: string }) => (
        <span className={params.value === 'ZZZ' ? 'currency-invalid' : 'currency-code'}>
          {params.value} {params.value === 'ZZZ' && '⚠'}
        </span>
      ),
    },
    {
      field: 'due_at',
      headerName: 'Due Date',
      width: 130,
    },
    {
      field: 'status',
      headerName: 'Status',
      width: 140,
      cellRenderer: (params: { value?: string }) => (
        <StatusBadge status={(params.value as ObligationStatus) || 'DRAFT'} />
      ),
    },
    {
      field: 'notes',
      headerName: 'Audit / Validation Notes',
      minWidth: 220,
      flex: 1,
      cellRenderer: (params: { value?: string }) => (
        <span style={{ fontSize: '0.8rem', color: '#64748B' }}>
          {params.value || '—'}
        </span>
      ),
    },
  ], [])

  return (
    <div className="page">
      <ConnectionStatus />

      {/* Header */}
      <div className="page-header">
        <div>
          <h1 className="page-title" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span>Payment Obligations</span>
            <span
              style={{
                fontSize: '0.72rem',
                padding: '3px 10px',
                borderRadius: 999,
                background: '#F1F5F9',
                color: '#003087',
                border: '1px solid #CBD5E1',
                fontWeight: 700,
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4,
              }}
            >
              <Sparkles size={12} color="#0070BA" />
              AG Grid Explorer
            </span>
          </h1>
          <p className="page-subtitle">
            Enterprise Financial Registry • {total} synthetic obligation{total !== 1 ? 's' : ''} loaded
          </p>
        </div>

        <div className="page-actions">
          {/* View Toggle */}
          <div style={{ display: 'inline-flex', background: '#E2E8F0', padding: 2, borderRadius: 8 }}>
            <button
              className="btn"
              style={{
                padding: '5px 12px',
                fontSize: '0.78rem',
                borderRadius: 6,
                background: useAgGrid ? '#FFFFFF' : 'transparent',
                color: useAgGrid ? '#003087' : '#64748B',
                boxShadow: useAgGrid ? '0 1px 3px rgba(0,0,0,0.1)' : 'none',
              }}
              onClick={() => setUseAgGrid(true)}
            >
              <Grid size={14} />
              AG Grid
            </button>
            <button
              className="btn"
              style={{
                padding: '5px 12px',
                fontSize: '0.78rem',
                borderRadius: 6,
                background: !useAgGrid ? '#FFFFFF' : 'transparent',
                color: !useAgGrid ? '#003087' : '#64748B',
                boxShadow: !useAgGrid ? '0 1px 3px rgba(0,0,0,0.1)' : 'none',
              }}
              onClick={() => setUseAgGrid(false)}
            >
              <TableIcon size={14} />
              Standard
            </button>
          </div>

          {/* Status Filter */}
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
          {/* AG Grid View */}
          {useAgGrid ? (
            <div>
              <div className="grid-toolbar">
                <div className="grid-search-box">
                  <Search size={16} className="grid-search-icon" />
                  <input
                    type="text"
                    className="grid-search-input"
                    placeholder="Quick search across suppliers, invoices, notes..."
                    value={quickFilterText}
                    onChange={(e) => setQuickFilterText(e.target.value)}
                  />
                </div>
                <div className="grid-meta-tag">
                  <span>Displaying <strong>{obligations.length}</strong> items in AG Grid</span>
                  <span>•</span>
                  <span>Click column headers to sort</span>
                </div>
              </div>

              <div
                className="ag-theme-quartz-paypal"
                style={{ height: 520, width: '100%', marginBottom: 20 }}
              >
                <AgGridReact
                  rowData={obligations}
                  columnDefs={columnDefs}
                  quickFilterText={quickFilterText}
                  pagination={true}
                  paginationPageSize={15}
                  paginationPageSizeSelector={[10, 15, 25, 50]}
                  animateRows={true}
                />
              </div>
            </div>
          ) : (
            /* Standard Table View */
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
          )}

          {/* Pagination for server queries */}
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
            ⓘ Amounts displayed for demonstration only. All payments execute in PayPal Sandbox test environment.
          </p>
        </>
      )}
    </div>
  )
}
