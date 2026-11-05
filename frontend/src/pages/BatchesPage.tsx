import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  createBatch,
  fetchBatch,
  fetchObligations,
  type Batch,
  type ObligationStatus,
} from '../api/client'

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

// -------------------------------------------------------------------------
// Batch detail panel
// -------------------------------------------------------------------------

function BatchDetail({ batchId }: { batchId: string }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['batch', batchId],
    queryFn: () => fetchBatch(batchId),
  })

  if (isLoading) return <div className="loading-state">Loading batch…</div>
  if (isError || !data) return <div className="alert alert-error">Failed to load batch.</div>

  return (
    <div className="batch-detail">
      <div className="batch-detail-header">
        <div>
          <h2 className="batch-ref">{data.batch_reference}</h2>
          <span className={`status-badge status-${data.status.toLowerCase()}`}>{data.status}</span>
        </div>
        <div className="batch-meta">
          <span>{data.obligation_count} obligation{data.obligation_count !== 1 ? 's' : ''}</span>
          <span>Created: {new Date(data.created_at).toLocaleDateString()}</span>
        </div>
      </div>

      {data.notes && <p className="batch-notes">{data.notes}</p>}

      <div className="table-wrapper">
        <table className="obligations-table">
          <thead>
            <tr>
              <th scope="col">Invoice Ref</th>
              <th scope="col">Supplier</th>
              <th scope="col" className="col-amount">Amount</th>
              <th scope="col">Currency</th>
              <th scope="col">Added</th>
            </tr>
          </thead>
          <tbody>
            {data.obligations.map((ob) => (
              <tr key={ob.obligation_id}>
                <td><code>{ob.invoice_reference}</code></td>
                <td>{ob.supplier_name}</td>
                <td className="col-amount">{formatAmount(ob.amount, ob.currency)}</td>
                <td><span className="currency-code">{ob.currency}</span></td>
                <td>{new Date(ob.added_at).toLocaleDateString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {data.status === 'DRAFT' && (
        <div className="alert alert-info">
          ⓘ This batch is in DRAFT. Approval and submission are enabled on Day 4 (PayPal integration).
        </div>
      )}
    </div>
  )
}

// -------------------------------------------------------------------------
// Create batch form
// -------------------------------------------------------------------------

function CreateBatchForm({ onCreated }: { onCreated: (b: Batch) => void }) {
  const queryClient = useQueryClient()
  const [batchRef, setBatchRef] = useState('')
  const [notes, setNotes] = useState('')
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())

  // Load only VALIDATED obligations (eligible for batching)
  const { data, isLoading } = useQuery({
    queryKey: ['obligations', 0, 'VALIDATED' as ObligationStatus],
    queryFn: () => fetchObligations({ limit: 200, status: 'VALIDATED' }),
  })

  const obligations = data?.items ?? []

  const mutation = useMutation({
    mutationFn: () =>
      createBatch({
        batch_reference: batchRef.trim(),
        obligation_ids: Array.from(selectedIds),
        notes: notes.trim() || undefined,
      }),
    onSuccess: (batch) => {
      queryClient.invalidateQueries({ queryKey: ['obligations'] })
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

  const canSubmit = batchRef.trim().length > 0 && selectedIds.size > 0 && !mutation.isPending

  return (
    <div className="create-batch-form">
      <h2 className="section-title">Create Payment Batch</h2>

      {isLoading && <div className="loading-state">Loading validated obligations…</div>}

      {!isLoading && obligations.length === 0 && (
        <div className="empty-state">
          <p>No VALIDATED obligations available to batch.</p>
          <p className="empty-hint">
            Import obligations first, then validate them on the Obligations page.
          </p>
        </div>
      )}

      {obligations.length > 0 && (
        <>
          <div className="form-row">
            <label htmlFor="batch-ref" className="form-label">
              Batch Reference <span className="required">*</span>
            </label>
            <input
              id="batch-ref"
              className="form-input"
              type="text"
              placeholder="e.g. BATCH-2026-001"
              value={batchRef}
              onChange={(e) => setBatchRef(e.target.value)}
            />
          </div>

          <div className="form-row">
            <label htmlFor="batch-notes" className="form-label">Notes (optional)</label>
            <input
              id="batch-notes"
              className="form-input"
              type="text"
              placeholder="e.g. November payroll run"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
            />
          </div>

          <div className="form-row">
            <div className="form-label-row">
              <span className="form-label">
                Select VALIDATED obligations ({selectedIds.size} of {obligations.length} selected)
              </span>
              <button className="btn-link" onClick={toggleAll}>
                {selectedIds.size === obligations.length ? 'Deselect all' : 'Select all'}
              </button>
            </div>

            <div className="table-wrapper">
              <table className="obligations-table">
                <thead>
                  <tr>
                    <th scope="col" style={{ width: 40 }}>
                      <input
                        type="checkbox"
                        checked={selectedIds.size === obligations.length && obligations.length > 0}
                        onChange={toggleAll}
                        aria-label="Select all"
                      />
                    </th>
                    <th scope="col">Invoice Ref</th>
                    <th scope="col">Supplier</th>
                    <th scope="col" className="col-amount">Amount</th>
                    <th scope="col">Due Date</th>
                  </tr>
                </thead>
                <tbody>
                  {obligations.map((ob) => (
                    <tr
                      key={ob.id}
                      className={selectedIds.has(ob.id) ? 'row-selected' : ''}
                      onClick={() => toggleSelect(ob.id)}
                      style={{ cursor: 'pointer' }}
                    >
                      <td>
                        <input
                          type="checkbox"
                          checked={selectedIds.has(ob.id)}
                          onChange={() => toggleSelect(ob.id)}
                          onClick={(e) => e.stopPropagation()}
                          aria-label={`Select ${ob.invoice_reference}`}
                        />
                      </td>
                      <td><code>{ob.invoice_reference}</code></td>
                      <td>{ob.supplier.display_name}</td>
                      <td className="col-amount">{formatAmount(ob.amount, ob.currency)}</td>
                      <td>{ob.due_at}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {mutation.isError && (
            <div className="alert alert-error" role="alert">
              <strong>Failed to create batch.</strong>{' '}
              {(mutation.error as { detail?: { message?: string } })?.detail?.message ??
                (mutation.error as { error?: { message?: string } })?.error?.message ??
                'Unknown error'}
            </div>
          )}

          <div className="import-actions">
            <button className="btn btn-primary" onClick={() => mutation.mutate()} disabled={!canSubmit}>
              {mutation.isPending ? 'Creating…' : `Create Batch (${selectedIds.size} obligations)`}
            </button>
          </div>

          <p className="disclaimer">
            ⓘ Creating a batch does NOT submit any payments.
            Approval and PayPal Sandbox submission are Day 4 features.
          </p>
        </>
      )}
    </div>
  )
}

// -------------------------------------------------------------------------
// Main page
// -------------------------------------------------------------------------

export default function BatchesPage() {
  const [createdBatch, setCreatedBatch] = useState<Batch | null>(null)

  if (createdBatch) {
    return (
      <div className="page">
        <div className="page-header">
          <div>
            <h1 className="page-title">Payment Batches</h1>
          </div>
          <button className="btn btn-secondary" onClick={() => setCreatedBatch(null)}>
            ← Create Another Batch
          </button>
        </div>

        <div className="alert alert-success" role="status">
          ✓ Batch <strong>{createdBatch.batch_reference}</strong> created with{' '}
          {createdBatch.obligation_count} obligation{createdBatch.obligation_count !== 1 ? 's' : ''}.
        </div>

        <BatchDetail batchId={createdBatch.id} />
      </div>
    )
  }

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Payment Batches</h1>
          <p className="page-subtitle">
            Group validated obligations into a payment batch for review and approval.
            Only VALIDATED obligations can be batched.
          </p>
        </div>
      </div>

      <CreateBatchForm onCreated={setCreatedBatch} />
    </div>
  )
}
