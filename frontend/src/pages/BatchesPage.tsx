import { useState, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  fetchBatches,
  createBatch,
  fetchObligations,
  type Batch,
} from '../api/client'
import { PageHeader } from '../components/layout/PageHeader'
import { StatusBadge } from '../components/common/StatusBadge'
import { TableSkeleton } from '../components/common/LoadingSkeleton'
import { EmptyState } from '../components/common/EmptyState'
import { ErrorState } from '../components/common/ErrorState'
import { Drawer } from '../components/common/Drawer'
import {
  Layers,
  PlusCircle,
  Search,
  Filter,
  ArrowRight,
  Clock,
  ShieldCheck,
  CheckCircle2,
} from 'lucide-react'

interface BatchesPageProps {
  onOpenBatchDetail?: (batchId: string) => void
}

function formatAmount(amount: string | number, currency: string = 'USD'): string {
  const num = typeof amount === 'number' ? amount : parseFloat(amount)
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

export default function BatchesPage({ onOpenBatchDetail }: BatchesPageProps) {
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('ALL')
  const [isCreateOpen, setIsCreateOpen] = useState(false)

  // Creation form state
  const [batchRef, setBatchRef] = useState(
    `BATCH-${new Date().getFullYear()}-${Math.floor(100 + Math.random() * 900)}`
  )
  const [notes, setNotes] = useState('')
  const [selectedObligationIds, setSelectedObligationIds] = useState<Set<string>>(new Set())

  const queryClient = useQueryClient()

  // Batches query
  const { data: batches, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['batches'],
    queryFn: () => fetchBatches({ limit: 100 }),
  })

  // Validated obligations query for creation drawer
  const { data: validatedData, isLoading: isValidatedLoading } = useQuery({
    queryKey: ['obligations', 0, 'VALIDATED'],
    queryFn: () => fetchObligations({ limit: 200, status: 'VALIDATED' }),
    enabled: isCreateOpen,
  })

  const validatedObligations = validatedData?.items || []

  // Create batch mutation
  const createMutation = useMutation({
    mutationFn: () =>
      createBatch({
        batch_reference: batchRef.trim(),
        obligation_ids: Array.from(selectedObligationIds),
        notes: notes.trim() || undefined,
      }),
    onSuccess: (newBatch) => {
      queryClient.invalidateQueries({ queryKey: ['batches'] })
      queryClient.invalidateQueries({ queryKey: ['obligations'] })
      setIsCreateOpen(false)
      setSelectedObligationIds(new Set())
      if (onOpenBatchDetail) {
        onOpenBatchDetail(newBatch.id)
      }
    },
  })

  // Filter batches
  const filteredBatches = useMemo(() => {
    if (!batches) return []
    return batches.filter((b: Batch) => {
      if (statusFilter !== 'ALL' && b.status !== statusFilter) return false
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase()
        const matchRef = b.batch_reference.toLowerCase().includes(q)
        const matchNotes = (b.notes || '').toLowerCase().includes(q)
        const matchId = b.id.toLowerCase().includes(q)
        if (!matchRef && !matchNotes && !matchId) return false
      }
      return true
    })
  }, [batches, statusFilter, searchQuery])

  // Aggregate stats
  const metrics = useMemo(() => {
    if (!batches) return { total: 0, draft: 0, submitted: 0, completed: 0 }
    let draft = 0
    let submitted = 0
    let completed = 0

    batches.forEach((b: Batch) => {
      if (['DRAFT', 'ANALYZED', 'APPROVED'].includes(b.status)) draft++
      if (['SUBMITTED', 'PROCESSING'].includes(b.status)) submitted++
      if (['COMPLETED', 'PARTIALLY_COMPLETED'].includes(b.status)) completed++
    })

    return { total: batches.length, draft, submitted, completed }
  }, [batches])

  const toggleSelectObligation = (id: string) => {
    setSelectedObligationIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const toggleSelectAll = () => {
    if (selectedObligationIds.size === validatedObligations.length) {
      setSelectedObligationIds(new Set())
    } else {
      setSelectedObligationIds(new Set(validatedObligations.map((o) => o.id)))
    }
  }

  // Calculate selected total
  const selectedSum = useMemo(() => {
    return validatedObligations
      .filter((o) => selectedObligationIds.has(o.id))
      .reduce((sum, o) => sum + parseFloat(o.amount || '0'), 0)
  }, [validatedObligations, selectedObligationIds])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      {/* Header */}
      <PageHeader
        title="Payment Batches"
        subtitle="Consolidate validated supplier liabilities into atomic payment runs with maker-checker controls and PayPal Sandbox execution."
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
            Maker-Checker Governed
          </span>
        }
        actions={
          <button
            onClick={() => {
              setBatchRef(`BATCH-${new Date().getFullYear()}-${Math.floor(100 + Math.random() * 900)}`)
              setIsCreateOpen(true)
            }}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 8,
              padding: '9px 18px',
              borderRadius: 'var(--radius-md)',
              background: 'var(--pufi-primary)',
              border: 'none',
              color: '#FFFFFF',
              fontSize: '0.84rem',
              fontWeight: 650,
              cursor: 'pointer',
              boxShadow: 'var(--shadow-sm)',
              transition: 'all var(--trans-fast)',
            }}
          >
            <PlusCircle size={16} />
            <span>Create Payment Batch</span>
          </button>
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
              <Layers size={14} color="var(--pufi-primary)" />
              <span>Total Batches: <strong>{metrics.total}</strong></span>
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
              <span>In Preparation: <strong>{metrics.draft}</strong></span>
            </div>

            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                background: 'var(--pufi-info-bg)',
                border: '1px solid var(--pufi-info-border)',
                padding: '6px 14px',
                borderRadius: 'var(--radius-pill)',
                fontSize: '0.8rem',
                fontWeight: 650,
                color: 'var(--pufi-info-text)',
              }}
            >
              <ShieldCheck size={14} />
              <span>Submitted: <strong>{metrics.submitted}</strong></span>
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
              <span>Settled: <strong>{metrics.completed}</strong></span>
            </div>
          </div>
        }
      />

      {isError && (
        <ErrorState
          title="Failed to Load Payment Batches"
          message={(error as { error?: { message?: string } })?.error?.message || 'Database could not retrieve batches.'}
          onRetry={() => refetch()}
        />
      )}

      {/* Main Batches Card */}
      <div
        style={{
          background: 'var(--bg-surface)',
          border: '1px solid var(--border-base)',
          borderRadius: 'var(--radius-lg)',
          boxShadow: 'var(--shadow-card)',
          overflow: 'hidden',
        }}
      >
        {/* Search & Filter Bar */}
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
              placeholder="Search by batch reference, ID, notes..."
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
              }}
            />
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Filter size={14} color="var(--text-muted)" />
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              style={{
                padding: '7px 12px',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--border-base)',
                background: 'var(--bg-surface)',
                color: 'var(--text-primary)',
                fontSize: '0.82rem',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              <option value="ALL">All Batch Statuses</option>
              <option value="DRAFT">Draft</option>
              <option value="ANALYZED">Analyzed</option>
              <option value="APPROVED">Approved</option>
              <option value="SUBMITTED">Submitted to PayPal</option>
              <option value="COMPLETED">Completed</option>
            </select>
          </div>
        </div>

        {/* Loading */}
        {isLoading && (
          <div style={{ padding: 24 }}>
            <TableSkeleton rows={5} columns={5} />
          </div>
        )}

        {/* Empty */}
        {!isLoading && filteredBatches.length === 0 && (
          <div style={{ padding: 48 }}>
            <EmptyState
              title="No Payment Batches Found"
              description="No batches match your criteria. Create a new batch from validated obligations to proceed."
              action={{
                label: 'Create Payment Batch',
                onClick: () => setIsCreateOpen(true),
                icon: <PlusCircle size={15} />,
              }}
            />
          </div>
        )}

        {/* Batches Table */}
        {!isLoading && filteredBatches.length > 0 && (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
              <thead>
                <tr
                  style={{
                    background: 'var(--bg-subtle)',
                    borderBottom: '1px solid var(--border-base)',
                    fontSize: '0.74rem',
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em',
                    color: 'var(--text-secondary)',
                  }}
                >
                  <th style={{ padding: '12px 20px', fontWeight: 700 }}>Batch Reference</th>
                  <th style={{ padding: '12px 16px', fontWeight: 700 }}>Lifecycle Status</th>
                  <th style={{ padding: '12px 16px', fontWeight: 700, textAlign: 'center' }}>Obligations</th>
                  <th style={{ padding: '12px 16px', fontWeight: 700 }}>Created Timestamp</th>
                  <th style={{ padding: '12px 16px', fontWeight: 700 }}>Approval Metadata</th>
                  <th style={{ padding: '12px 16px', fontWeight: 700 }}>Notes</th>
                  <th style={{ padding: '12px 20px', textAlign: 'right' }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {filteredBatches.map((b: Batch) => (
                  <tr
                    key={b.id}
                    onClick={() => onOpenBatchDetail && onOpenBatchDetail(b.id)}
                    style={{
                      borderBottom: '1px solid var(--border-subtle)',
                      cursor: 'pointer',
                      transition: 'background var(--trans-fast)',
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'var(--bg-surface-hover)')}
                    onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
                  >
                    <td style={{ padding: '14px 20px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <code style={{ fontWeight: 800, color: 'var(--pufi-primary)', fontSize: '0.88rem' }}>
                          {b.batch_reference}
                        </code>
                      </div>
                      <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: 2 }}>
                        ID: {b.id.slice(-8)}
                      </div>
                    </td>
                    <td style={{ padding: '14px 16px' }}>
                      <StatusBadge status={b.status} size="sm" />
                    </td>
                    <td style={{ padding: '14px 16px', textAlign: 'center' }}>
                      <span
                        style={{
                          background: 'var(--bg-subtle)',
                          padding: '3px 10px',
                          borderRadius: 'var(--radius-pill)',
                          fontWeight: 750,
                          fontSize: '0.8rem',
                          color: 'var(--text-primary)',
                        }}
                      >
                        {b.obligation_count} items
                      </span>
                    </td>
                    <td style={{ padding: '14px 16px', fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
                      {new Date(b.created_at).toLocaleString()}
                    </td>
                    <td style={{ padding: '14px 16px', fontSize: '0.82rem' }}>
                      {b.approved_by ? (
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--pufi-success-text)' }}>
                          <CheckCircle2 size={13} />
                          <span>Approved by {b.approved_by}</span>
                        </div>
                      ) : (
                        <span style={{ color: 'var(--text-muted)' }}>Pending Maker-Checker</span>
                      )}
                    </td>
                    <td style={{ padding: '14px 16px', maxWidth: 200 }}>
                      <span
                        style={{
                          fontSize: '0.8rem',
                          color: 'var(--text-muted)',
                          whiteSpace: 'nowrap',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          display: 'block',
                        }}
                      >
                        {b.notes || '—'}
                      </span>
                    </td>
                    <td style={{ padding: '14px 20px', textAlign: 'right' }}>
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          if (onOpenBatchDetail) onOpenBatchDetail(b.id)
                        }}
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: 6,
                          padding: '6px 12px',
                          borderRadius: 'var(--radius-sm)',
                          background: 'var(--pufi-primary-light)',
                          color: 'var(--pufi-primary)',
                          border: 'none',
                          fontSize: '0.78rem',
                          fontWeight: 700,
                          cursor: 'pointer',
                        }}
                      >
                        <span>Manage Batch</span>
                        <ArrowRight size={13} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Creation Drawer */}
      <Drawer
        isOpen={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
        title="Create Payment Batch"
        subtitle="Group verified obligations into an executable payout package"
        width={620}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          {/* Reference Input */}
          <div>
            <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 700, marginBottom: 6, color: 'var(--text-primary)' }}>
              Batch Reference Identifier
            </label>
            <input
              type="text"
              value={batchRef}
              onChange={(e) => setBatchRef(e.target.value)}
              placeholder="e.g. BATCH-2026-001"
              style={{
                width: '100%',
                padding: '10px 14px',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--border-base)',
                background: 'var(--bg-subtle)',
                color: 'var(--text-primary)',
                fontFamily: 'monospace',
                fontWeight: 700,
                fontSize: '0.88rem',
                outline: 'none',
                boxSizing: 'border-box',
              }}
            />
          </div>

          {/* Notes */}
          <div>
            <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 700, marginBottom: 6, color: 'var(--text-primary)' }}>
              Operational Notes (Optional)
            </label>
            <input
              type="text"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="e.g. Weekly vendor disbursement cycle"
              style={{
                width: '100%',
                padding: '10px 14px',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--border-base)',
                background: 'var(--bg-subtle)',
                color: 'var(--text-primary)',
                fontSize: '0.84rem',
                outline: 'none',
                boxSizing: 'border-box',
              }}
            />
          </div>

          {/* Obligations Selector */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
              <div>
                <span style={{ fontSize: '0.85rem', fontWeight: 750, color: 'var(--text-primary)' }}>
                  Select Validated Obligations
                </span>
                <span style={{ fontSize: '0.74rem', color: 'var(--text-muted)', marginLeft: 8 }}>
                  ({selectedObligationIds.size} of {validatedObligations.length} selected)
                </span>
              </div>
              {validatedObligations.length > 0 && (
                <button
                  type="button"
                  onClick={toggleSelectAll}
                  style={{
                    background: 'transparent',
                    border: 'none',
                    color: 'var(--pufi-primary)',
                    fontSize: '0.78rem',
                    fontWeight: 650,
                    cursor: 'pointer',
                  }}
                >
                  {selectedObligationIds.size === validatedObligations.length ? 'Deselect All' : 'Select All'}
                </button>
              )}
            </div>

            {isValidatedLoading ? (
              <div style={{ padding: 20, textAlign: 'center', color: 'var(--text-muted)' }}>
                Loading eligible validated obligations…
              </div>
            ) : validatedObligations.length === 0 ? (
              <div
                style={{
                  padding: 24,
                  borderRadius: 'var(--radius-md)',
                  background: 'var(--pufi-warning-bg)',
                  border: '1px solid var(--pufi-warning-border)',
                  color: 'var(--pufi-warning-text)',
                  fontSize: '0.82rem',
                }}
              >
                <div style={{ fontWeight: 700, marginBottom: 4 }}>No VALIDATED obligations found</div>
                Only obligations in <code>VALIDATED</code> status can be added to a batch. Validate draft invoices in Payment Obligations first.
              </div>
            ) : (
              <div
                style={{
                  maxHeight: 280,
                  overflowY: 'auto',
                  border: '1px solid var(--border-base)',
                  borderRadius: 'var(--radius-md)',
                }}
              >
                {validatedObligations.map((ob) => {
                  const isChecked = selectedObligationIds.has(ob.id)
                  return (
                    <div
                      key={ob.id}
                      onClick={() => toggleSelectObligation(ob.id)}
                      style={{
                        padding: '10px 14px',
                        borderBottom: '1px solid var(--border-subtle)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        background: isChecked ? 'var(--pufi-primary-light)' : 'var(--bg-surface)',
                        cursor: 'pointer',
                        transition: 'background var(--trans-fast)',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={() => {}} // Controlled by container onClick
                          style={{ cursor: 'pointer' }}
                        />
                        <div>
                          <div style={{ fontWeight: 650, fontSize: '0.84rem', color: 'var(--text-primary)' }}>
                            {ob.supplier.display_name}
                          </div>
                          <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                            Inv: <code>{ob.invoice_reference}</code> • Due {ob.due_at}
                          </div>
                        </div>
                      </div>

                      <strong className="num-tabular" style={{ fontSize: '0.88rem', color: 'var(--text-primary)' }}>
                        {formatAmount(ob.amount, ob.currency)}
                      </strong>
                    </div>
                  )
                })}
              </div>
            )}
          </div>

          {/* Running Total Strip */}
          <div
            style={{
              padding: '14px 18px',
              borderRadius: 'var(--radius-md)',
              background: 'var(--bg-subtle)',
              border: '1px solid var(--border-subtle)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <span style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
              Total Batch Commitment:
            </span>
            <strong className="num-tabular" style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--text-primary)' }}>
              {formatAmount(selectedSum, 'USD')}
            </strong>
          </div>

          {/* Mutation error */}
          {createMutation.isError && (
            <div
              style={{
                padding: '10px 14px',
                borderRadius: 'var(--radius-sm)',
                background: 'var(--pufi-danger-bg)',
                border: '1px solid var(--pufi-danger-border)',
                color: 'var(--pufi-danger-text)',
                fontSize: '0.8rem',
              }}
            >
              ⚠ Failed to create batch: {(createMutation.error as { error?: { message?: string } })?.error?.message || 'Check validation status of selected obligations.'}
            </div>
          )}

          {/* Action Button */}
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 10 }}>
            <button
              onClick={() => setIsCreateOpen(false)}
              style={{
                padding: '8px 16px',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--border-base)',
                background: 'var(--bg-surface)',
                color: 'var(--text-secondary)',
                fontSize: '0.82rem',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              Cancel
            </button>
            <button
              onClick={() => createMutation.mutate()}
              disabled={createMutation.isPending || selectedObligationIds.size === 0 || !batchRef.trim()}
              style={{
                padding: '8px 22px',
                borderRadius: 'var(--radius-sm)',
                border: 'none',
                background: 'var(--pufi-primary)',
                color: '#FFFFFF',
                fontSize: '0.84rem',
                fontWeight: 650,
                cursor: createMutation.isPending || selectedObligationIds.size === 0 ? 'not-allowed' : 'pointer',
                opacity: createMutation.isPending || selectedObligationIds.size === 0 ? 0.6 : 1,
                boxShadow: 'var(--shadow-sm)',
              }}
            >
              {createMutation.isPending ? 'Grouping Batch…' : `Create Batch (${selectedObligationIds.size} Obligations)`}
            </button>
          </div>
        </div>
      </Drawer>
    </div>
  )
}
