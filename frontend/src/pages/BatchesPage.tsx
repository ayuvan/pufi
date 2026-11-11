import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  PlusCircle,
  CheckCircle2,
  Inbox,
  AlertCircle,
} from 'lucide-react'
import {
  createBatch,
  fetchBatches,
  fetchObligations,
  type Batch,
  type ObligationStatus,
} from '../api/client'

// -------------------------------------------------------------------------
// Props
// -------------------------------------------------------------------------

interface BatchesPageProps {
  onOpenBatchDetail?: (batchId: string) => void
}

// -------------------------------------------------------------------------
// Helpers
// -------------------------------------------------------------------------

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

function StatusPill({ status }: { status: string }) {
  const cls = `status-badge status-${status.toLowerCase()}`
  return <span className={cls}>{status}</span>
}

// -------------------------------------------------------------------------
// Create batch form inside Executive Card
// -------------------------------------------------------------------------

function CreateBatchCard({
  onCreated,
  onCancel,
}: {
  onCreated: (b: Batch) => void
  onCancel: () => void
}) {
  const queryClient = useQueryClient()
  const [batchRef, setBatchRef] = useState(`BATCH-${new Date().getFullYear()}-${Math.floor(100 + Math.random() * 900)}`)
  const [notes, setNotes] = useState('')
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())

  // Load only VALIDATED obligations (eligible for batching)
  const { data, isLoading } = useQuery({
    queryKey: ['obligations', 0, 'VALIDATED' as ObligationStatus],
    queryFn: () => fetchObligations({ limit: 200, status: 'VALIDATED' }),
  })

  const obligations = data?.items ?? []

  // Pre-select all validated obligations by default if available
  useState(() => {
    if (obligations.length > 0 && selectedIds.size === 0) {
      setSelectedIds(new Set(obligations.map((o) => o.id)))
    }
  })

  const mutation = useMutation({
    mutationFn: () =>
      createBatch({
        batch_reference: batchRef.trim(),
        obligation_ids: Array.from(selectedIds),
        notes: notes.trim() || undefined,
      }),
    onSuccess: (batch) => {
      queryClient.invalidateQueries({ queryKey: ['obligations'] })
      queryClient.invalidateQueries({ queryKey: ['batches'] })
      onCreated(batch)
    },
  })

  function toggleSelect(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  function toggleAll() {
    if (selectedIds.size === obligations.length) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(obligations.map((o) => o.id)))
    }
  }

  // Calculate total selected amount
  const selectedTotal = obligations
    .filter((o) => selectedIds.has(o.id))
    .reduce((sum, o) => sum + parseFloat(o.amount || '0'), 0)

  const canSubmit = batchRef.trim().length > 0 && selectedIds.size > 0 && !mutation.isPending

  return (
    <div className="card" style={{ padding: 28, maxWidth: 960, margin: '0 auto' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid #E2E8F0', paddingBottom: 16, marginBottom: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ width: 36, height: 36, borderRadius: '50%', background: '#EBF4FE', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <PlusCircle size={20} color="#0070BA" />
          </div>
          <div>
            <h2 style={{ fontSize: '1.2rem', fontWeight: 800, color: '#003087', margin: 0 }}>Create Payment Batch</h2>
            <p style={{ fontSize: '0.8rem', color: '#64748B', margin: 0 }}>
              Group verified supplier obligations into a consolidated payment instruction.
            </p>
          </div>
        </div>
        <button className="btn btn-secondary" onClick={onCancel}>
          Cancel
        </button>
      </div>

      {isLoading && <div className="loading-state">Loading eligible validated obligations…</div>}

      {!isLoading && obligations.length === 0 && (
        <div className="empty-state" style={{ padding: 40 }}>
          <AlertCircle size={32} color="#D97706" style={{ marginBottom: 12 }} />
          <p style={{ fontWeight: 700, color: '#1E293B', fontSize: '1rem' }}>No VALIDATED obligations found</p>
          <p className="empty-hint" style={{ marginTop: 6 }}>
            Only obligations in <code>VALIDATED</code> status can be grouped into batches.
            Go to the <strong>Obligations</strong> tab to review and validate draft obligations.
          </p>
        </div>
      )}

      {obligations.length > 0 && (
        <>
          {/* Section 1: Batch Configuration */}
          <div style={{ marginBottom: 24 }}>
            <div style={{ fontSize: '0.82rem', fontWeight: 700, color: '#003087', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 12 }}>
              1. Batch Identification & Reference
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 16 }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: '#334155', marginBottom: 6 }}>
                  Batch Reference Code <span style={{ color: '#DC2626' }}>*</span>
                </label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="e.g. BATCH-2027-001"
                  value={batchRef}
                  onChange={(e) => setBatchRef(e.target.value)}
                />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: '#334155', marginBottom: 6 }}>
                  Operational Notes (Optional)
                </label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="e.g. Q1 Global Vendor Settlement Run"
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                />
              </div>
            </div>
          </div>

          {/* Section 2: Obligations Selection */}
          <div style={{ marginBottom: 24 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12, flexWrap: 'wrap', gap: 10 }}>
              <div style={{ fontSize: '0.82rem', fontWeight: 700, color: '#003087', textTransform: 'uppercase', letterSpacing: 0.5 }}>
                2. Select Validated Obligations ({selectedIds.size} of {obligations.length} Selected)
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <span style={{ fontSize: '0.84rem', fontWeight: 700, color: '#059669' }}>
                  Total: ${selectedTotal.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} USD
                </span>
                <button
                  type="button"
                  className="btn btn-secondary"
                  style={{ height: 32, padding: '0 12px', fontSize: '0.75rem' }}
                  onClick={toggleAll}
                >
                  {selectedIds.size === obligations.length ? 'Deselect All' : 'Select All'}
                </button>
              </div>
            </div>

            <div className="table-wrapper" style={{ maxHeight: 320, overflowY: 'auto', border: '1px solid #E2E8F0', borderRadius: 8 }}>
              <table className="obligations-table">
                <thead>
                  <tr>
                    <th style={{ width: 44, textAlign: 'center' }}>
                      <input
                        type="checkbox"
                        checked={selectedIds.size === obligations.length && obligations.length > 0}
                        onChange={toggleAll}
                        style={{ width: 16, height: 16, accentColor: '#0070BA', cursor: 'pointer' }}
                        aria-label="Select all"
                      />
                    </th>
                    <th>Invoice Ref</th>
                    <th>Supplier Name</th>
                    <th className="col-amount">Amount</th>
                    <th>Due Date</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {obligations.map((ob) => {
                    const isSelected = selectedIds.has(ob.id)
                    return (
                      <tr
                        key={ob.id}
                        style={{ cursor: 'pointer', background: isSelected ? '#F0F7FF' : 'transparent' }}
                        onClick={() => toggleSelect(ob.id)}
                      >
                        <td style={{ textAlign: 'center' }} onClick={(e) => e.stopPropagation()}>
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={() => toggleSelect(ob.id)}
                            style={{ width: 16, height: 16, accentColor: '#0070BA', cursor: 'pointer' }}
                          />
                        </td>
                        <td>
                          <code style={{ fontWeight: 700, color: '#003087' }}>{ob.invoice_reference}</code>
                        </td>
                        <td>
                          <span style={{ fontWeight: 600, color: '#0F172A' }}>{ob.supplier.display_name}</span>
                        </td>
                        <td className="col-amount" style={{ fontWeight: 800, color: '#0F172A' }}>
                          {formatAmount(ob.amount, ob.currency)}
                        </td>
                        <td style={{ color: '#475569', fontSize: '0.84rem' }}>{ob.due_at}</td>
                        <td>
                          <span className="status-badge status-validated">VALIDATED</span>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {mutation.isError && (
            <div className="alert alert-error" style={{ marginBottom: 16 }}>
              <strong>Failed to create batch:</strong>{' '}
              {(mutation.error as any)?.detail?.message ||
                (mutation.error as any)?.error?.message ||
                'Validation error'}
            </div>
          )}

          {/* Action Footer */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderTop: '1px solid #E2E8F0', paddingTop: 18 }}>
            <div style={{ fontSize: '0.82rem', color: '#64748B' }}>
              Selected <strong>{selectedIds.size}</strong> obligations totaling{' '}
              <strong>${selectedTotal.toFixed(2)} USD</strong>
            </div>
            <button
              className="btn btn-paypal-blue"
              onClick={() => mutation.mutate()}
              disabled={!canSubmit}
              style={{ padding: '0 24px', fontSize: '0.92rem' }}
            >
              <CheckCircle2 size={16} />
              <span>{mutation.isPending ? 'Creating Batch…' : `Create Payment Batch (${selectedIds.size})`}</span>
            </button>
          </div>
        </>
      )}
    </div>
  )
}

// -------------------------------------------------------------------------
// Main Batches Page (List of Batches + Creation Trigger)
// -------------------------------------------------------------------------

export default function BatchesPage({ onOpenBatchDetail }: BatchesPageProps = {}) {
  const [showCreateForm, setShowCreateForm] = useState(false)

  const { data: batches, isLoading, isError } = useQuery({
    queryKey: ['batches'],
    queryFn: () => fetchBatches({ limit: 50 }),
    refetchInterval: 15000,
  })

  return (
    <div className="page">
      {/* Header */}
      <div className="page-header" style={{ marginBottom: 24 }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <h1 className="page-title" style={{ margin: 0 }}>Payment Batches</h1>
            <span
              style={{
                fontSize: '0.72rem',
                padding: '3px 10px',
                borderRadius: 999,
                background: '#F1F5F9',
                color: '#003087',
                border: '1px solid #CBD5E1',
                fontWeight: 700,
              }}
            >
              Maker-Checker Dual Control
            </span>
          </div>
          <p className="page-subtitle" style={{ marginTop: 6 }}>
            Consolidated payment instructions grouped for multi-rail routing, approval, and PayPal Sandbox execution.
          </p>
        </div>

        <div className="page-actions">
          {!showCreateForm && (
            <button
              className="btn btn-paypal-blue"
              onClick={() => setShowCreateForm(true)}
            >
              <PlusCircle size={16} />
              <span>+ Create New Batch</span>
            </button>
          )}
        </div>
      </div>

      {/* Creation Mode */}
      {showCreateForm ? (
        <CreateBatchCard
          onCreated={(newBatch) => {
            setShowCreateForm(false)
            if (onOpenBatchDetail) {
              onOpenBatchDetail(newBatch.id)
            }
          }}
          onCancel={() => setShowCreateForm(false)}
        />
      ) : (
        /* Batches List Mode */
        <div>
          {isLoading && (
            <div className="loading-state" style={{ padding: 60 }}>
              Loading payment batches…
            </div>
          )}

          {isError && (
            <div className="alert alert-error">
              Failed to load batches list.
            </div>
          )}

          {!isLoading && (!batches || batches.length === 0) ? (
            <div className="card" style={{ padding: 60, textAlign: 'center' }}>
              <Inbox size={40} color="#94A3B8" style={{ margin: '0 auto 16px' }} />
              <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#1E293B', marginBottom: 6 }}>
                No Payment Batches Created Yet
              </h3>
              <p style={{ fontSize: '0.85rem', color: '#64748B', maxWidth: 440, margin: '0 auto 20px' }}>
                Batches consolidate validated obligations for fee analysis, AI decision support, and PayPal Sandbox payout submission.
              </p>
              <button
                className="btn btn-paypal-blue"
                onClick={() => setShowCreateForm(true)}
              >
                <PlusCircle size={16} />
                <span>Create Your First Batch</span>
              </button>
            </div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))', gap: 20 }}>
              {batches?.map((batch) => {
                const isApproved = batch.status === 'APPROVED'
                const isSubmitted = ['SUBMITTED', 'PROCESSING', 'COMPLETED'].includes(batch.status)

                return (
                  <div
                    key={batch.id}
                    className="card"
                    style={{
                      margin: 0,
                      display: 'flex',
                      flexDirection: 'column',
                      justifyContent: 'space-between',
                      borderLeft: `4px solid ${isApproved ? '#007934' : isSubmitted ? '#0070BA' : '#CBD5E1'}`,
                    }}
                  >
                    <div>
                      {/* Batch Header */}
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
                        <code style={{ fontSize: '1rem', fontWeight: 800, color: '#003087' }}>
                          {batch.batch_reference}
                        </code>
                        <StatusPill status={batch.status} />
                      </div>

                      {/* Notes / Description */}
                      <p style={{ fontSize: '0.82rem', color: '#64748B', marginBottom: 16, minHeight: 36 }}>
                        {batch.notes || 'No description provided for this batch run.'}
                      </p>

                      {/* Metrics Pill Grid */}
                      <div style={{ background: '#F8FAFC', border: '1px solid #E2E8F0', borderRadius: 8, padding: 12, marginBottom: 16, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                        <div>
                          <div style={{ fontSize: '0.72rem', textTransform: 'uppercase', color: '#64748B', fontWeight: 700 }}>
                            Obligations
                          </div>
                          <div style={{ fontSize: '1.05rem', fontWeight: 800, color: '#0F172A' }}>
                            {batch.obligation_count} items
                          </div>
                        </div>
                        <div>
                          <div style={{ fontSize: '0.72rem', textTransform: 'uppercase', color: '#64748B', fontWeight: 700 }}>
                            Created Date
                          </div>
                          <div style={{ fontSize: '0.85rem', fontWeight: 600, color: '#334155', marginTop: 2 }}>
                            {new Date(batch.created_at).toLocaleDateString()}
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Action Footer */}
                    <div style={{ borderTop: '1px solid #E2E8F0', paddingTop: 14, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <code style={{ fontSize: '0.7rem', color: '#94A3B8' }}>
                        ID: {batch.id.slice(0, 8)}…
                      </code>

                      {onOpenBatchDetail && (
                        <button
                          className={isApproved ? 'btn btn-paypal-gold' : 'btn btn-secondary'}
                          style={{ height: 34, fontSize: '0.78rem', padding: '0 14px' }}
                          onClick={() => onOpenBatchDetail(batch.id)}
                        >
                          <span>{isApproved ? 'Execute PayPal Payout →' : 'Review & Route →'}</span>
                        </button>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
