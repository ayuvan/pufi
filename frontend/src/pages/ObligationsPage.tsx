import { useQuery } from '@tanstack/react-query'
import { fetchObligations, fetchHealth, type Obligation, type ObligationStatus } from '../api/client'
import { useState, useMemo } from 'react'
import { AgGridReact } from 'ag-grid-react'
import type { ColDef } from 'ag-grid-community'
import { Search, Grid, Table as TableIcon, Sparkles, Filter, CheckCircle2, AlertCircle, FileText } from 'lucide-react'

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
        <span><strong>PUFI API v{data?.version} Active</strong> • PayPal Sandbox Mode • Deterministic Decimal Ledger</span>
      </div>
      <div style={{ fontSize: '0.78rem', color: '#166534', fontWeight: 600 }}>
        PostgreSQL / SQLite Storage Engine
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

  // Summary counts for quick chips
  const validatedCount = useMemo(
    () => obligations.filter((o) => o.status === 'VALIDATED').length,
    [obligations]
  )
  const draftCount = useMemo(
    () => obligations.filter((o) => o.status === 'DRAFT').length,
    [obligations]
  )

  // AG Grid Column Definitions with generous spacing
  const columnDefs = useMemo<ColDef<Obligation>[]>(() => [
    {
      field: 'invoice_reference',
      headerName: 'Invoice Ref',
      pinned: 'left',
      width: 180,
      cellRenderer: (params: { value?: string }) => (
        <code style={{ fontFamily: 'monospace', fontWeight: 800, color: '#003087', fontSize: '0.85rem' }}>
          {params.value}
        </code>
      ),
    },
    {
      headerName: 'Supplier Name',
      valueGetter: (params) => params.data?.supplier.display_name,
      minWidth: 240,
      flex: 1.2,
      cellRenderer: (params: { value?: string }) => (
        <span style={{ fontWeight: 600, color: '#0F172A' }}>
          {params.value}
        </span>
      ),
    },
    {
      headerName: 'Country',
      width: 110,
      valueGetter: (params) => params.data?.supplier.country_code,
      cellRenderer: (params: { value?: string }) => (
        <span className="country-badge" style={{ padding: '3px 8px', fontSize: '0.75rem' }}>
          {params.value}
        </span>
      ),
    },
    {
      field: 'amount',
      headerName: 'Obligation Amount',
      width: 170,
      type: 'rightAligned',
      cellRenderer: (params: { data?: Obligation }) => (
        <span style={{ fontWeight: 800, fontVariantNumeric: 'tabular-nums', color: '#0F172A', fontSize: '0.92rem' }}>
          {params.data ? formatAmount(params.data.amount, params.data.currency) : ''}
        </span>
      ),
    },
    {
      field: 'currency',
      headerName: 'Currency',
      width: 110,
      cellRenderer: (params: { value?: string }) => (
        <span className={params.value === 'ZZZ' ? 'currency-invalid' : 'currency-code'} style={{ fontSize: '0.85rem' }}>
          {params.value} {params.value === 'ZZZ' && '⚠'}
        </span>
      ),
    },
    {
      field: 'due_at',
      headerName: 'Due Date',
      width: 130,
      cellRenderer: (params: { value?: string }) => (
        <span style={{ color: '#475569', fontSize: '0.84rem' }}>{params.value}</span>
      ),
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
      minWidth: 260,
      flex: 1.5,
      cellRenderer: (params: { value?: string }) => (
        <span style={{ fontSize: '0.82rem', color: '#64748B' }}>
          {params.value || '—'}
        </span>
      ),
    },
  ], [])

  return (
    <div className="page">
      <ConnectionStatus />

      {/* Spacious Header with Metrics */}
      <div className="page-header" style={{ marginBottom: 20 }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <h1 className="page-title" style={{ margin: 0 }}>Payment Obligations</h1>
            <span
              style={{
                fontSize: '0.72rem',
                padding: '4px 12px',
                borderRadius: 999,
                background: '#EBF4FE',
                color: '#003087',
                border: '1px solid #BFDBFE',
                fontWeight: 700,
                display: 'inline-flex',
                alignItems: 'center',
                gap: 5,
              }}
            >
              <Sparkles size={13} color="#0070BA" />
              Powered by AG Grid
            </span>
          </div>
          <p className="page-subtitle" style={{ marginTop: 6 }}>
            Enterprise Financial Registry • Multi-currency obligations with automated validation and duplicate prevention
          </p>
        </div>

        {/* Quick Summary Badges */}
        <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, background: '#FFFFFF', padding: '6px 14px', borderRadius: 20, border: '1px solid #E2E8F0', fontSize: '0.8rem', fontWeight: 600 }}>
            <FileText size={14} color="#0070BA" />
            <span>Total: <strong>{total}</strong></span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, background: '#ECFDF5', padding: '6px 14px', borderRadius: 20, border: '1px solid #A7F3D0', fontSize: '0.8rem', fontWeight: 600, color: '#065F46' }}>
            <CheckCircle2 size={14} color="#059669" />
            <span>Validated: <strong>{validatedCount}</strong></span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, background: '#F1F5F9', padding: '6px 14px', borderRadius: 20, border: '1px solid #CBD5E1', fontSize: '0.8rem', fontWeight: 600, color: '#475569' }}>
            <span>Draft: <strong>{draftCount}</strong></span>
          </div>
        </div>
      </div>

      {isError && (
        <div className="alert alert-error" role="alert">
          <strong>Failed to load obligations.</strong>{' '}
          {(error as { error?: { message?: string } })?.error?.message ?? 'Unknown error'}
        </div>
      )}

      {/* Main Card Container */}
      <div className="card" style={{ padding: 24 }}>
        {/* Single Harmonious Action Bar */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 16,
            marginBottom: 20,
            flexWrap: 'wrap',
          }}
        >
          {/* Search Box */}
          <div style={{ position: 'relative', flex: 1, minWidth: 280, maxWidth: 480 }}>
            <Search size={16} style={{ position: 'absolute', left: 14, top: '50%', transform: 'translateY(-50%)', color: '#94A3B8' }} />
            <input
              type="text"
              className="grid-search-input"
              style={{
                width: '100%',
                padding: '10px 16px 10px 40px',
                fontSize: '0.88rem',
                border: '1px solid #E2E8F0',
                borderRadius: 999,
                background: '#FFFFFF',
                boxSizing: 'border-box',
              }}
              placeholder="Search by supplier, invoice ref, notes..."
              value={quickFilterText}
              onChange={(e) => setQuickFilterText(e.target.value)}
            />
          </div>

          {/* Right Controls Group: Status filter + View toggle */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
            {/* Status Filter Dropdown */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Filter size={15} color="#64748B" />
              <select
                className="select"
                value={statusFilter}
                onChange={(e) => {
                  setStatusFilter(e.target.value as ObligationStatus | '')
                  setOffset(0)
                }}
                aria-label="Filter by status"
                style={{ width: 170 }}
              >
                <option value="">All Statuses</option>
                <option value="DRAFT">Draft</option>
                <option value="VALIDATED">Validated</option>
                <option value="ON_HOLD">On Hold</option>
                <option value="READY">Ready</option>
                <option value="CLOSED">Closed</option>
                <option value="CANCELLED">Cancelled</option>
              </select>
            </div>

            {/* View Switcher Pills */}
            <div style={{ display: 'inline-flex', background: '#F1F5F9', padding: 3, borderRadius: 999, border: '1px solid #E2E8F0' }}>
              <button
                className="btn"
                style={{
                  height: 34,
                  padding: '0 14px',
                  fontSize: '0.78rem',
                  borderRadius: 999,
                  background: useAgGrid ? '#FFFFFF' : 'transparent',
                  color: useAgGrid ? '#003087' : '#64748B',
                  fontWeight: useAgGrid ? 700 : 500,
                  boxShadow: useAgGrid ? '0 1px 3px rgba(0,0,0,0.1)' : 'none',
                  border: 'none',
                }}
                onClick={() => setUseAgGrid(true)}
              >
                <Grid size={14} />
                <span>AG Grid View</span>
              </button>
              <button
                className="btn"
                style={{
                  height: 34,
                  padding: '0 14px',
                  fontSize: '0.78rem',
                  borderRadius: 999,
                  background: !useAgGrid ? '#FFFFFF' : 'transparent',
                  color: !useAgGrid ? '#003087' : '#64748B',
                  fontWeight: !useAgGrid ? 700 : 500,
                  boxShadow: !useAgGrid ? '0 1px 3px rgba(0,0,0,0.1)' : 'none',
                  border: 'none',
                }}
                onClick={() => setUseAgGrid(false)}
              >
                <TableIcon size={14} />
                <span>Standard Table</span>
              </button>
            </div>
          </div>
        </div>

        {isLoading ? (
          <div className="loading-state" aria-live="polite" style={{ padding: 60 }}>
            Loading payment obligations…
          </div>
        ) : obligations.length === 0 ? (
          <div className="empty-state" style={{ padding: 60 }}>
            <AlertCircle size={32} color="#94A3B8" style={{ marginBottom: 12 }} />
            <p style={{ fontWeight: 600, fontSize: '1rem', color: '#334155' }}>No obligations found.</p>
            <p className="empty-hint" style={{ marginTop: 6 }}>
              Run <code>python seed.py</code> in the backend or use the <strong>Import</strong> tab to ingest obligations.
            </p>
          </div>
        ) : (
          <>
            {/* AG Grid View with Generous Spacing */}
            {useAgGrid ? (
              <div
                className="ag-theme-quartz-paypal"
                style={{ height: 560, width: '100%', borderRadius: 10, overflow: 'hidden' }}
              >
                <AgGridReact
                  rowData={obligations}
                  columnDefs={columnDefs}
                  quickFilterText={quickFilterText}
                  pagination={true}
                  paginationPageSize={15}
                  paginationPageSizeSelector={[15, 25, 50, 100]}
                  animateRows={true}
                  headerHeight={48}
                  rowHeight={52}
                />
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

            {/* Server Pagination */}
            {totalPages > 1 && (
              <div className="pagination" role="navigation" aria-label="Pagination" style={{ marginTop: 24 }}>
                <button
                  className="btn btn-secondary"
                  onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
                  disabled={offset === 0}
                  aria-label="Previous page"
                >
                  ← Prev
                </button>
                <span className="pagination-info" style={{ fontWeight: 600 }}>
                  Page {currentPage} of {totalPages} ({total} total obligations)
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
          </>
        )}
      </div>

      <p className="disclaimer" style={{ marginTop: 18 }}>
        ⓘ Amounts displayed for demonstration only. All payments execute in PayPal Sandbox test environment.
      </p>
    </div>
  )
}
