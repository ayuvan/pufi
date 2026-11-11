import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  fetchObligations,
  type Obligation,
  type ObligationStatus,
} from '../api/client'
import { PageHeader } from '../components/layout/PageHeader'
import { StatusBadge } from '../components/common/StatusBadge'
import { CurrencyBadge } from '../components/common/CurrencyBadge'
import { Drawer } from '../components/common/Drawer'
import { TableSkeleton } from '../components/common/LoadingSkeleton'
import { EmptyState } from '../components/common/EmptyState'
import { ErrorState } from '../components/common/ErrorState'
import { AgGridReact } from 'ag-grid-react'
import type { ColDef } from 'ag-grid-community'
import {
  Search,
  Grid,
  Table as TableIcon,
  Filter,
  CheckCircle2,
  Clock,
  FileText,
  ChevronRight,
  ShieldCheck,
  Building2,
  Hash,
} from 'lucide-react'

const PAGE_SIZE = 50

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

export default function ObligationsPage() {
  const [offset, setOffset] = useState(0)
  const [statusFilter, setStatusFilter] = useState<ObligationStatus | ''>('')
  const [currencyFilter, setCurrencyFilter] = useState<string>('ALL')
  const [searchQuery, setSearchQuery] = useState('')
  const [viewMode, setViewMode] = useState<'enterprise' | 'aggrid'>('enterprise')
  const [selectedObligation, setSelectedObligation] = useState<Obligation | null>(null)

  // Fetch obligations
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['obligations', offset, statusFilter],
    queryFn: () =>
      fetchObligations({
        limit: PAGE_SIZE,
        offset,
        status: statusFilter || undefined,
      }),
  })

  const rawObligations = data?.items ?? []
  const total = data?.total ?? 0
  const totalPages = Math.ceil(total / PAGE_SIZE)
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1

  // Filter client-side by search query and currency
  const filteredObligations = useMemo(() => {
    return rawObligations.filter((ob) => {
      // Currency filter
      if (currencyFilter !== 'ALL' && ob.currency !== currencyFilter) {
        return false
      }

      // Search query (invoice ref, supplier name, notes)
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase()
        const matchRef = ob.invoice_reference.toLowerCase().includes(q)
        const matchSup = ob.supplier.display_name.toLowerCase().includes(q)
        const matchSupRef = ob.supplier.external_reference.toLowerCase().includes(q)
        const matchNotes = (ob.notes || '').toLowerCase().includes(q)
        if (!matchRef && !matchSup && !matchSupRef && !matchNotes) {
          return false
        }
      }

      return true
    })
  }, [rawObligations, currencyFilter, searchQuery])

  // Count summaries for metrics
  const validatedCount = useMemo(
    () => rawObligations.filter((o) => o.status === 'VALIDATED').length,
    [rawObligations]
  )
  const draftCount = useMemo(
    () => rawObligations.filter((o) => o.status === 'DRAFT').length,
    [rawObligations]
  )

  // AG Grid column definitions
  const agGridColDefs = useMemo<ColDef<Obligation>[]>(
    () => [
      {
        field: 'invoice_reference',
        headerName: 'Invoice Ref',
        pinned: 'left',
        width: 170,
        cellRenderer: (params: { value?: string }) => (
          <code style={{ fontFamily: 'monospace', fontWeight: 800, color: 'var(--pufi-primary)' }}>
            {params.value}
          </code>
        ),
      },
      {
        headerName: 'Supplier Name',
        valueGetter: (params) => params.data?.supplier.display_name,
        minWidth: 220,
        flex: 1.2,
        cellRenderer: (params: { value?: string }) => (
          <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{params.value}</span>
        ),
      },
      {
        headerName: 'Country',
        width: 110,
        valueGetter: (params) => params.data?.supplier.country_code,
        cellRenderer: (params: { value?: string }) => (
          <span style={{ background: 'var(--bg-subtle)', padding: '2px 8px', borderRadius: 4, fontSize: '0.75rem', fontWeight: 700 }}>
            {params.value}
          </span>
        ),
      },
      {
        field: 'amount',
        headerName: 'Obligation Amount',
        width: 160,
        type: 'rightAligned',
        cellRenderer: (params: { data?: Obligation }) => (
          <span style={{ fontWeight: 800, fontVariantNumeric: 'tabular-nums', color: 'var(--text-primary)' }}>
            {params.data ? formatAmount(params.data.amount, params.data.currency) : ''}
          </span>
        ),
      },
      {
        field: 'currency',
        headerName: 'Currency',
        width: 110,
        cellRenderer: (params: { value?: string }) => (
          <CurrencyBadge currency={params.value || 'USD'} size="sm" />
        ),
      },
      {
        field: 'due_at',
        headerName: 'Due Date',
        width: 130,
        cellRenderer: (params: { value?: string }) => (
          <span style={{ color: 'var(--text-secondary)', fontSize: '0.84rem' }}>{params.value}</span>
        ),
      },
      {
        field: 'status',
        headerName: 'Status',
        width: 140,
        cellRenderer: (params: { value?: string }) => (
          <StatusBadge status={(params.value as ObligationStatus) || 'DRAFT'} size="sm" />
        ),
      },
      {
        field: 'notes',
        headerName: 'Audit / Validation Notes',
        minWidth: 240,
        flex: 1.5,
        cellRenderer: (params: { value?: string }) => (
          <span style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
            {params.value || '—'}
          </span>
        ),
      },
    ],
    []
  )

  const currencies = ['ALL', 'USD', 'EUR', 'GBP', 'CAD']

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      {/* Header with KPI chips */}
      <PageHeader
        title="Payment Obligations"
        subtitle="Authoritative multi-currency supplier liabilities with cryptographic duplicate prevention and verification."
        badge={
          <span
            style={{
              fontSize: '0.72rem',
              padding: '3px 10px',
              borderRadius: 'var(--radius-pill)',
              background: 'var(--pufi-primary-light)',
              color: 'var(--pufi-primary)',
              border: '1px solid rgba(22,119,255,0.25)',
              fontWeight: 700,
            }}
          >
            Deterministic Ledger
          </span>
        }
        stats={
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                background: 'var(--bg-surface)',
                border: '1px solid var(--border-base)',
                padding: '6px 14px',
                borderRadius: 'var(--radius-pill)',
                fontSize: '0.8rem',
                fontWeight: 650,
              }}
            >
              <FileText size={14} color="var(--pufi-primary)" />
              <span>Total: <strong>{total}</strong></span>
            </div>

            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                background: 'var(--pufi-success-bg)',
                border: '1px solid var(--pufi-success-border)',
                padding: '6px 14px',
                borderRadius: 'var(--radius-pill)',
                fontSize: '0.8rem',
                fontWeight: 650,
                color: 'var(--pufi-success-text)',
              }}
            >
              <CheckCircle2 size={14} />
              <span>Validated: <strong>{validatedCount}</strong></span>
            </div>

            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                background: 'var(--pufi-warning-bg)',
                border: '1px solid var(--pufi-warning-border)',
                padding: '6px 14px',
                borderRadius: 'var(--radius-pill)',
                fontSize: '0.8rem',
                fontWeight: 650,
                color: 'var(--pufi-warning-text)',
              }}
            >
              <Clock size={14} />
              <span>Draft Queue: <strong>{draftCount}</strong></span>
            </div>
          </div>
        }
      />

      {isError && (
        <ErrorState
          title="Failed to Load Obligations"
          message={(error as { error?: { message?: string } })?.error?.message || 'The backend database or server could not be reached.'}
          onRetry={() => refetch()}
        />
      )}

      {/* Main Content Card */}
      <div
        style={{
          background: 'var(--bg-surface)',
          border: '1px solid var(--border-base)',
          borderRadius: 'var(--radius-lg)',
          boxShadow: 'var(--shadow-card)',
          overflow: 'hidden',
        }}
      >
        {/* Filter & Search Bar */}
        <div
          style={{
            padding: '18px 24px',
            borderBottom: '1px solid var(--border-base)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 16,
            flexWrap: 'wrap',
          }}
        >
          {/* Search Box */}
          <div style={{ position: 'relative', flex: 1, minWidth: 260, maxWidth: 440 }}>
            <Search
              size={15}
              style={{
                position: 'absolute',
                left: 14,
                top: '50%',
                transform: 'translateY(-50%)',
                color: 'var(--text-muted)',
              }}
            />
            <input
              type="text"
              placeholder="Search by invoice ref, supplier, notes..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{
                width: '100%',
                padding: '9px 16px 9px 38px',
                fontSize: '0.84rem',
                borderRadius: 'var(--radius-pill)',
                border: '1px solid var(--border-base)',
                background: 'var(--bg-subtle)',
                color: 'var(--text-primary)',
                outline: 'none',
                boxSizing: 'border-box',
                transition: 'border-color var(--trans-fast)',
              }}
              onFocus={(e) => (e.target.style.borderColor = 'var(--pufi-primary)')}
              onBlur={(e) => (e.target.style.borderColor = 'var(--border-base)')}
            />
          </div>

          {/* Currency Pill Filter */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ fontSize: '0.76rem', color: 'var(--text-muted)', fontWeight: 600 }}>
              Currency:
            </span>
            <div style={{ display: 'flex', gap: 4, background: 'var(--bg-subtle)', padding: 3, borderRadius: 'var(--radius-pill)' }}>
              {currencies.map((curr) => {
                const isSelected = currencyFilter === curr
                return (
                  <button
                    key={curr}
                    onClick={() => setCurrencyFilter(curr)}
                    style={{
                      border: 'none',
                      background: isSelected ? 'var(--bg-surface)' : 'transparent',
                      color: isSelected ? 'var(--pufi-primary)' : 'var(--text-secondary)',
                      fontSize: '0.74rem',
                      fontWeight: 700,
                      padding: '3px 10px',
                      borderRadius: 'var(--radius-pill)',
                      cursor: 'pointer',
                      boxShadow: isSelected ? 'var(--shadow-xs)' : 'none',
                      transition: 'all var(--trans-fast)',
                    }}
                  >
                    {curr}
                  </button>
                )
              })}
            </div>
          </div>

          {/* Status Dropdown Filter */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Filter size={14} color="var(--text-muted)" />
            <select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value as ObligationStatus | '')
                setOffset(0)
              }}
              style={{
                padding: '7px 12px',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--border-base)',
                background: 'var(--bg-surface)',
                color: 'var(--text-primary)',
                fontSize: '0.82rem',
                fontWeight: 600,
                cursor: 'pointer',
                outline: 'none',
              }}
            >
              <option value="">All Statuses</option>
              <option value="VALIDATED">Validated (Ready for Batch)</option>
              <option value="DRAFT">Draft</option>
              <option value="ON_HOLD">On Hold</option>
              <option value="READY">Ready</option>
              <option value="CLOSED">Closed</option>
              <option value="CANCELLED">Cancelled</option>
            </select>
          </div>

          {/* View Mode Toggle (Enterprise Table vs AG Grid) */}
          <div
            style={{
              display: 'flex',
              background: 'var(--bg-subtle)',
              padding: 3,
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-base)',
            }}
          >
            <button
              onClick={() => setViewMode('enterprise')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                padding: '5px 10px',
                borderRadius: 'var(--radius-sm)',
                border: 'none',
                background: viewMode === 'enterprise' ? 'var(--bg-surface)' : 'transparent',
                color: viewMode === 'enterprise' ? 'var(--pufi-primary)' : 'var(--text-secondary)',
                fontSize: '0.76rem',
                fontWeight: 650,
                cursor: 'pointer',
                boxShadow: viewMode === 'enterprise' ? 'var(--shadow-xs)' : 'none',
              }}
              title="Enterprise High-Clarity Table"
            >
              <TableIcon size={14} />
              <span>Fintech Table</span>
            </button>

            <button
              onClick={() => setViewMode('aggrid')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                padding: '5px 10px',
                borderRadius: 'var(--radius-sm)',
                border: 'none',
                background: viewMode === 'aggrid' ? 'var(--bg-surface)' : 'transparent',
                color: viewMode === 'aggrid' ? 'var(--pufi-primary)' : 'var(--text-secondary)',
                fontSize: '0.76rem',
                fontWeight: 650,
                cursor: 'pointer',
                boxShadow: viewMode === 'aggrid' ? 'var(--shadow-xs)' : 'none',
              }}
              title="AG Grid Community View"
            >
              <Grid size={14} />
              <span>AG Grid</span>
            </button>
          </div>
        </div>

        {/* Loading Skeleton */}
        {isLoading && (
          <div style={{ padding: 24 }}>
            <TableSkeleton rows={8} columns={6} />
          </div>
        )}

        {/* Empty State */}
        {!isLoading && filteredObligations.length === 0 && (
          <div style={{ padding: 48 }}>
            <EmptyState
              title="No Payment Obligations Found"
              description={
                searchQuery || statusFilter || currencyFilter !== 'ALL'
                  ? 'No obligations match your current search and filter criteria. Try resetting filters.'
                  : 'Your organization currently has zero obligations registered in the database.'
              }
              action={{
                label: 'Clear Filters',
                onClick: () => {
                  setSearchQuery('')
                  setStatusFilter('')
                  setCurrencyFilter('ALL')
                },
              }}
            />
          </div>
        )}

        {/* View Mode 1: Enterprise Table */}
        {!isLoading && filteredObligations.length > 0 && viewMode === 'enterprise' && (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
              <thead>
                <tr
                  style={{
                    borderBottom: '1px solid var(--border-base)',
                    background: 'var(--bg-subtle)',
                    fontSize: '0.74rem',
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em',
                    color: 'var(--text-secondary)',
                  }}
                >
                  <th style={{ padding: '12px 20px', fontWeight: 700 }}>Invoice Ref</th>
                  <th style={{ padding: '12px 16px', fontWeight: 700 }}>Supplier</th>
                  <th style={{ padding: '12px 16px', fontWeight: 700, textAlign: 'right' }}>Amount</th>
                  <th style={{ padding: '12px 16px', fontWeight: 700 }}>Currency</th>
                  <th style={{ padding: '12px 16px', fontWeight: 700 }}>Due Date</th>
                  <th style={{ padding: '12px 16px', fontWeight: 700 }}>Status</th>
                  <th style={{ padding: '12px 16px', fontWeight: 700 }}>Validation Notes</th>
                  <th style={{ padding: '12px 20px', textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredObligations.map((ob) => (
                  <tr
                    key={ob.id}
                    onClick={() => setSelectedObligation(ob)}
                    style={{
                      borderBottom: '1px solid var(--border-subtle)',
                      cursor: 'pointer',
                      transition: 'background var(--trans-fast)',
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'var(--bg-surface-hover)')}
                    onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
                  >
                    <td style={{ padding: '14px 20px', whiteSpace: 'nowrap' }}>
                      <code
                        style={{
                          fontFamily: 'monospace',
                          fontWeight: 800,
                          color: 'var(--pufi-primary)',
                          fontSize: '0.86rem',
                        }}
                      >
                        {ob.invoice_reference}
                      </code>
                    </td>
                    <td style={{ padding: '14px 16px' }}>
                      <div style={{ fontWeight: 650, color: 'var(--text-primary)', fontSize: '0.88rem' }}>
                        {ob.supplier.display_name}
                      </div>
                      <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>
                        {ob.supplier.external_reference} • {ob.supplier.country_code}
                      </div>
                    </td>
                    <td style={{ padding: '14px 16px', textAlign: 'right' }}>
                      <span
                        className="num-tabular"
                        style={{
                          fontWeight: 800,
                          fontSize: '0.94rem',
                          color: 'var(--text-primary)',
                        }}
                      >
                        {formatAmount(ob.amount, ob.currency)}
                      </span>
                    </td>
                    <td style={{ padding: '14px 16px' }}>
                      <CurrencyBadge currency={ob.currency} size="sm" />
                    </td>
                    <td style={{ padding: '14px 16px', color: 'var(--text-secondary)', fontSize: '0.84rem' }}>
                      {ob.due_at}
                    </td>
                    <td style={{ padding: '14px 16px' }}>
                      <StatusBadge status={ob.status} size="sm" />
                    </td>
                    <td style={{ padding: '14px 16px', maxWidth: 260 }}>
                      <span
                        style={{
                          fontSize: '0.8rem',
                          color: 'var(--text-muted)',
                          whiteSpace: 'nowrap',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          display: 'block',
                        }}
                        title={ob.notes || ''}
                      >
                        {ob.notes || '—'}
                      </span>
                    </td>
                    <td style={{ padding: '14px 20px', textAlign: 'right' }}>
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          setSelectedObligation(ob)
                        }}
                        style={{
                          background: 'transparent',
                          border: 'none',
                          color: 'var(--pufi-primary)',
                          cursor: 'pointer',
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: 4,
                          fontSize: '0.78rem',
                          fontWeight: 650,
                        }}
                      >
                        <span>Details</span>
                        <ChevronRight size={14} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* View Mode 2: AG Grid Community View */}
        {!isLoading && filteredObligations.length > 0 && viewMode === 'aggrid' && (
          <div className="ag-theme-quartz" style={{ height: 500, width: '100%' }}>
            <AgGridReact<Obligation>
              rowData={filteredObligations}
              columnDefs={agGridColDefs}
              pagination={true}
              paginationPageSize={20}
              onRowClicked={(e) => {
                if (e.data) setSelectedObligation(e.data)
              }}
              rowSelection="single"
            />
          </div>
        )}

        {/* Pagination Bar */}
        <div
          style={{
            padding: '14px 24px',
            borderTop: '1px solid var(--border-base)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            fontSize: '0.82rem',
            color: 'var(--text-secondary)',
          }}
        >
          <div>
            Showing <strong>{filteredObligations.length}</strong> of <strong>{total}</strong> total obligations
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <button
              onClick={() => setOffset((p) => Math.max(0, p - PAGE_SIZE))}
              disabled={offset === 0}
              style={{
                padding: '6px 12px',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--border-base)',
                background: 'var(--bg-surface)',
                color: offset === 0 ? 'var(--text-muted)' : 'var(--text-primary)',
                cursor: offset === 0 ? 'not-allowed' : 'pointer',
                fontSize: '0.8rem',
                fontWeight: 600,
              }}
            >
              Previous
            </button>
            <span>
              Page <strong>{currentPage}</strong> of <strong>{totalPages || 1}</strong>
            </span>
            <button
              onClick={() => setOffset((p) => p + PAGE_SIZE)}
              disabled={offset + PAGE_SIZE >= total}
              style={{
                padding: '6px 12px',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--border-base)',
                background: 'var(--bg-surface)',
                color: offset + PAGE_SIZE >= total ? 'var(--text-muted)' : 'var(--text-primary)',
                cursor: offset + PAGE_SIZE >= total ? 'not-allowed' : 'pointer',
                fontSize: '0.8rem',
                fontWeight: 600,
              }}
            >
              Next
            </button>
          </div>
        </div>
      </div>

      {/* Right Slide-over Detail Drawer */}
      <Drawer
        isOpen={!!selectedObligation}
        onClose={() => setSelectedObligation(null)}
        title="Obligation Details"
        subtitle={selectedObligation?.invoice_reference}
        width={500}
      >
        {selectedObligation && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
            {/* Top Amount Banner */}
            <div
              style={{
                background: 'var(--bg-subtle)',
                borderRadius: 'var(--radius-md)',
                padding: '18px 20px',
                border: '1px solid var(--border-subtle)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
              }}
            >
              <div>
                <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 700 }}>
                  Liability Obligation Amount
                </div>
                <div
                  className="num-tabular"
                  style={{ fontSize: '1.65rem', fontWeight: 800, color: 'var(--text-primary)', marginTop: 4 }}
                >
                  {formatAmount(selectedObligation.amount, selectedObligation.currency)}
                </div>
              </div>
              <StatusBadge status={selectedObligation.status} size="lg" />
            </div>

            {/* Supplier Section */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.85rem', fontWeight: 750, color: 'var(--text-primary)' }}>
                <Building2 size={16} color="var(--pufi-primary)" />
                <span>Supplier Master Record</span>
              </div>
              <div
                style={{
                  background: 'var(--bg-surface)',
                  border: '1px solid var(--border-base)',
                  borderRadius: 'var(--radius-md)',
                  padding: 16,
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 10,
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Display Name</span>
                  <strong style={{ fontSize: '0.85rem', color: 'var(--text-primary)' }}>
                    {selectedObligation.supplier.display_name}
                  </strong>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>External Supplier Ref</span>
                  <code style={{ fontSize: '0.82rem', color: 'var(--pufi-primary)' }}>
                    {selectedObligation.supplier.external_reference}
                  </code>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Country ISO Code</span>
                  <span style={{ fontSize: '0.85rem', fontWeight: 650 }}>
                    {selectedObligation.supplier.country_code}
                  </span>
                </div>
              </div>
            </div>

            {/* Obligation Metadata */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.85rem', fontWeight: 750, color: 'var(--text-primary)' }}>
                <Hash size={16} color="var(--pufi-primary)" />
                <span>Financial Properties</span>
              </div>
              <div
                style={{
                  background: 'var(--bg-surface)',
                  border: '1px solid var(--border-base)',
                  borderRadius: 'var(--radius-md)',
                  padding: 16,
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 10,
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Obligation ID</span>
                  <code style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>
                    {selectedObligation.id}
                  </code>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Invoice Reference</span>
                  <strong style={{ fontSize: '0.85rem', color: 'var(--text-primary)' }}>
                    {selectedObligation.invoice_reference}
                  </strong>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Due Date</span>
                  <span style={{ fontSize: '0.85rem', fontWeight: 650 }}>
                    {selectedObligation.due_at}
                  </span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Registered At</span>
                  <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                    {new Date(selectedObligation.created_at).toLocaleString()}
                  </span>
                </div>
              </div>
            </div>

            {/* Audit & Validation Notes */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.85rem', fontWeight: 750, color: 'var(--text-primary)' }}>
                <ShieldCheck size={16} color="var(--pufi-success)" />
                <span>Validation & Audit Trail</span>
              </div>
              <div
                style={{
                  background: 'var(--bg-subtle)',
                  borderRadius: 'var(--radius-md)',
                  padding: 14,
                  fontSize: '0.82rem',
                  color: 'var(--text-secondary)',
                  lineHeight: 1.5,
                  border: '1px solid var(--border-subtle)',
                }}
              >
                {selectedObligation.notes || 'No custom audit notes recorded during ingestion.'}
              </div>
            </div>
          </div>
        )}
      </Drawer>
    </div>
  )
}
