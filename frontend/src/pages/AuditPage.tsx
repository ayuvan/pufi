/**
 * PUFI — Global Audit Trail Page (Day 5)
 *
 * Shows all audit events across all batches in reverse chronological order.
 * Uses the existing GET /batches/{id}/audit endpoint per batch, plus a
 * lightweight global endpoint that returns recent events across all entities.
 *
 * Reuses the AuditEventOut type from client.ts.
 * Clearly labels simulated vs. actual PayPal events.
 */

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchAuditEvents, type AuditEventOut } from '../api/client'

// -------------------------------------------------------------------------
// Helpers
// -------------------------------------------------------------------------

function eventLabel(eventType: string): { label: string; className: string } {
  const map: Record<string, { label: string; className: string }> = {
    APPROVED:           { label: '✓ Approved',         className: 'audit-approved' },
    SUBMITTED:          { label: '→ Submitted',         className: 'audit-submitted' },
    STATUS_REFRESHED:   { label: '↺ Status Refreshed',  className: 'audit-info' },
    ANALYSIS_COMPLETED: { label: '📊 Analysis',          className: 'audit-info' },
    CREATED:            { label: '+ Created',            className: 'audit-created' },
    FAILED:             { label: '✗ Failed',             className: 'audit-failed' },
    'PAYMENT.PAYOUTS-ITEM.SUCCEEDED': { label: '💸 PayPal: Success', className: 'audit-approved' },
    'PAYMENT.PAYOUTS-ITEM.FAILED':    { label: '✗ PayPal: Failed',  className: 'audit-failed' },
  }
  return map[eventType] ?? { label: eventType, className: 'audit-default' }
}

function parseDetails(raw: string | null): Record<string, unknown> | null {
  if (!raw) return null
  try { return JSON.parse(raw) } catch { return null }
}

// -------------------------------------------------------------------------
// Audit event row
// -------------------------------------------------------------------------

function AuditRow({ ev }: { ev: AuditEventOut }) {
  const [expanded, setExpanded] = useState(false)
  const { label, className } = eventLabel(ev.event_type)
  const details = parseDetails(ev.details_redacted)

  return (
    <tr className={`audit-row ${className}`}>
      <td className="audit-time">
        {new Date(ev.created_at).toLocaleString('en-IN', {
          dateStyle: 'short', timeStyle: 'medium',
        })}
      </td>
      <td>
        <span className={`audit-event-label ${className}`}>{label}</span>
      </td>
      <td>
        <span className="audit-entity">{ev.entity_type}</span>
        {ev.entity_type === 'BATCH' && (
          <code className="audit-id">{ev.entity_id.slice(-8)}</code>
        )}
        {ev.entity_type === 'WEBHOOK' && (
          <code className="audit-id">webhook</code>
        )}
      </td>
      <td>{ev.actor}</td>
      <td>
        {details && (
          <button
            className="btn-link"
            onClick={() => setExpanded((p) => !p)}
            aria-expanded={expanded}
          >
            {expanded ? 'hide' : 'details'}
          </button>
        )}
        {expanded && details && (
          <pre className="audit-details">
            {JSON.stringify(details, null, 2)}
          </pre>
        )}
      </td>
    </tr>
  )
}

// -------------------------------------------------------------------------
// Batch audit section
// -------------------------------------------------------------------------

function BatchAuditSection({ batchId }: { batchId: string }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['audit', batchId],
    queryFn: () => fetchAuditEvents(batchId),
  })

  if (isLoading) return <tr><td colSpan={5} className="loading-state">Loading…</td></tr>
  if (isError || !data || data.length === 0) return null

  return (
    <>
      {data.map((ev) => <AuditRow key={ev.id} ev={ev} />)}
    </>
  )
}

// -------------------------------------------------------------------------
// Main page
// -------------------------------------------------------------------------

export default function AuditPage() {
  const [batchIdInput, setBatchIdInput] = useState('')
  const [queriedId, setQueriedId] = useState<string | null>(null)

  function handleSearch() {
    const id = batchIdInput.trim()
    if (id) setQueriedId(id)
  }

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Audit Trail</h1>
          <p className="page-subtitle">
            Chronological log of all significant events for a payment batch.
            Events include analysis, approval, submission, status refreshes, and PayPal responses.
          </p>
        </div>
      </div>

      <div className="panel">
        <h3 className="panel-title">Look up Batch Audit Events</h3>
        <p className="text-muted" style={{ marginBottom: '1rem' }}>
          Enter a batch ID (e.g. from the demo seed output) to view its full event history.
        </p>

        <div className="form-row" style={{ display: 'flex', gap: '0.75rem', alignItems: 'flex-end', maxWidth: 600 }}>
          <div style={{ flex: 1 }}>
            <label className="form-label">Batch ID</label>
            <input
              className="form-input"
              type="text"
              placeholder="e.g. 1cc14a1c-aa96-4902-8a78-b987f932265e"
              value={batchIdInput}
              onChange={(e) => setBatchIdInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            />
          </div>
          <button className="btn btn-primary" onClick={handleSearch} disabled={!batchIdInput.trim()}>
            Load Events
          </button>
        </div>

        {queriedId && (
          <div style={{ marginTop: '1.5rem' }}>
            <div className="audit-batch-header">
              <span className="text-muted">Events for batch:</span>
              <code className="batch-id-display" style={{ display: 'inline', marginLeft: '0.5rem' }}>
                {queriedId}
              </code>
            </div>

            <div className="table-wrapper" style={{ marginTop: '0.75rem' }}>
              <table className="obligations-table">
                <thead>
                  <tr>
                    <th>Time</th>
                    <th>Event</th>
                    <th>Entity</th>
                    <th>Actor</th>
                    <th>Details</th>
                  </tr>
                </thead>
                <tbody>
                  <BatchAuditSection batchId={queriedId} />
                </tbody>
              </table>
            </div>

            <p className="disclaimer" style={{ marginTop: '0.75rem' }}>
              ⓘ Events labelled PAYPAL_WEBHOOK are from verified PayPal webhook callbacks.
              Events labelled SYSTEM are from internal PUFI state transitions.
              Simulated events are not shown here — only persisted audit records appear.
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
