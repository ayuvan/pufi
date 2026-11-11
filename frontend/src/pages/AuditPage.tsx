/**
 * PUFI — Global Audit Trail Page (PayPal Enterprise Edition)
 *
 * Shows all audit events for payment batches with:
 *  - Quick Batch Selector Dropdown (no manual UUID copy-pasting required!)
 *  - Real-time search and filter
 *  - Formatted timestamps, event badges, actor attribution
 *  - Interactive inspection of state transition payloads
 */

import { useState, useEffect, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Search,
  Lock,
  FileText,
  Clock,
  User,
} from 'lucide-react'
import { fetchAuditEvents, fetchBatches, type AuditEventOut, type Batch } from '../api/client'

// -------------------------------------------------------------------------
// Helpers
// -------------------------------------------------------------------------

function eventLabel(eventType: string): { label: string; cls: string } {
  const map: Record<string, { label: string; cls: string }> = {
    APPROVED: { label: '✓ Approved', cls: 'status-approved' },
    SUBMITTED: { label: '→ Submitted', cls: 'status-submitted' },
    STATUS_REFRESHED: { label: '↺ Status Refreshed', cls: 'status-ready' },
    ANALYSIS_COMPLETED: { label: '📊 Route Analysis', cls: 'status-ready' },
    CREATED: { label: '+ Batch Created', cls: 'status-draft' },
    FAILED: { label: '✗ Failed', cls: 'status-failed' },
    'PAYMENT.PAYOUTS-ITEM.SUCCEEDED': { label: '💸 PayPal: Succeeded', cls: 'status-completed' },
    'PAYMENT.PAYOUTS-ITEM.FAILED': { label: '✗ PayPal: Rejected', cls: 'status-failed' },
  }
  return map[eventType] ?? { label: eventType, cls: 'status-draft' }
}

function parseDetails(raw: string | null): Record<string, unknown> | null {
  if (!raw) return null
  try {
    return JSON.parse(raw)
  } catch {
    return null
  }
}

// -------------------------------------------------------------------------
// Audit Event Row
// -------------------------------------------------------------------------

function AuditEventRow({ ev }: { ev: AuditEventOut }) {
  const [expanded, setExpanded] = useState(false)
  const { label, cls } = eventLabel(ev.event_type)
  const details = parseDetails(ev.details_redacted)

  return (
    <tr style={{ verticalAlign: 'top', borderBottom: '1px solid #E2E8F0' }}>
      <td style={{ whiteSpace: 'nowrap', color: '#64748B', fontSize: '0.82rem', padding: '14px 16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <Clock size={13} color="#94A3B8" />
          <span>{new Date(ev.created_at).toLocaleString()}</span>
        </div>
      </td>
      <td style={{ padding: '14px 16px' }}>
        <span className={`status-badge ${cls}`} style={{ fontSize: '0.74rem' }}>
          {label}
        </span>
      </td>
      <td style={{ padding: '14px 16px' }}>
        <span style={{ fontSize: '0.78rem', color: '#64748B', textTransform: 'uppercase', fontWeight: 700 }}>
          {ev.entity_type}
        </span>
        <code style={{ fontSize: '0.72rem', background: '#F1F5F9', padding: '2px 6px', borderRadius: 4, marginLeft: 6, color: '#003087' }}>
          {ev.entity_id.slice(-8)}
        </code>
      </td>
      <td style={{ padding: '14px 16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <User size={13} color="#0070BA" />
          <strong style={{ fontSize: '0.84rem', color: '#0F172A' }}>{ev.actor}</strong>
        </div>
      </td>
      <td style={{ padding: '14px 16px' }}>
        {details ? (
          <div>
            <button
              className="btn btn-secondary"
              style={{ height: 28, padding: '0 10px', fontSize: '0.74rem' }}
              onClick={() => setExpanded((p) => !p)}
            >
              <span>{expanded ? 'Hide Payload' : 'Inspect Audit Details'}</span>
            </button>
            {expanded && (
              <pre
                style={{
                  fontSize: '0.74rem',
                  background: '#F8FAFC',
                  border: '1px solid #CBD5E1',
                  borderRadius: 6,
                  padding: 10,
                  marginTop: 8,
                  maxWidth: 520,
                  overflowX: 'auto',
                  lineHeight: 1.4,
                  color: '#0F172A',
                }}
              >
                {JSON.stringify(details, null, 2)}
              </pre>
            )}
          </div>
        ) : (
          <span style={{ color: '#94A3B8', fontSize: '0.8rem' }}>—</span>
        )}
      </td>
    </tr>
  )
}

// -------------------------------------------------------------------------
// Main Audit Trail Page
// -------------------------------------------------------------------------

export default function AuditPage() {
  const [selectedBatchId, setSelectedBatchId] = useState<string>('')
  const [customInput, setCustomInput] = useState<string>('')
  const [searchTerm, setSearchTerm] = useState('')

  // Pre-load batches for quick-select dropdown
  const { data: batches } = useQuery({
    queryKey: ['batches'],
    queryFn: () => fetchBatches({ limit: 50 }),
  })

  // Set default batch if available
  useEffect(() => {
    if (batches && batches.length > 0 && !selectedBatchId) {
      setSelectedBatchId(batches[0].id)
    }
  }, [batches, selectedBatchId])

  // Fetch audit events for selected batch
  const { data: events, isLoading, isError } = useQuery({
    queryKey: ['audit', selectedBatchId],
    queryFn: () => fetchAuditEvents(selectedBatchId),
    enabled: !!selectedBatchId,
  })

  function handleBatchSelect(id: string) {
    setSelectedBatchId(id)
    setCustomInput('')
  }

  function handleManualSearch() {
    const trimmed = customInput.trim()
    if (trimmed) {
      setSelectedBatchId(trimmed)
    }
  }

  const filteredEvents = useMemo(() => {
    if (!events) return []
    if (!searchTerm.trim()) return events
    const q = searchTerm.toLowerCase()
    return events.filter(
      (ev) =>
        ev.event_type.toLowerCase().includes(q) ||
        ev.actor.toLowerCase().includes(q) ||
        (ev.details_redacted && ev.details_redacted.toLowerCase().includes(q))
    )
  }, [events, searchTerm])

  return (
    <div className="page">
      {/* Header */}
      <div className="page-header" style={{ marginBottom: 24 }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <h1 className="page-title" style={{ margin: 0 }}>Compliance & Audit Trail</h1>
            <span
              style={{
                fontSize: '0.72rem',
                padding: '3px 10px',
                borderRadius: 999,
                background: '#ECFDF5',
                color: '#065F46',
                border: '1px solid #A7F3D0',
                fontWeight: 700,
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4,
              }}
            >
              <Lock size={12} color="#059669" />
              Immutable Ledger
            </span>
          </div>
          <p className="page-subtitle" style={{ marginTop: 6 }}>
            Chronological audit records of all batch analyses, approvals, submissions, and PayPal provider responses.
          </p>
        </div>
      </div>

      {/* Batch Selector Card */}
      <div className="card" style={{ padding: 24, marginBottom: 24 }}>
        <div style={{ fontSize: '0.82rem', fontWeight: 700, color: '#003087', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 14 }}>
          Select Payment Batch for Audit Inspection
        </div>

        <div style={{ display: 'flex', gap: 16, alignItems: 'center', flexWrap: 'wrap' }}>
          {/* Quick Select Dropdown */}
          <div style={{ flex: 1, minWidth: 300 }}>
            <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: '#475569', marginBottom: 6 }}>
              Quick Select from Active Batches:
            </label>
            <select
              className="select"
              value={selectedBatchId}
              onChange={(e) => handleBatchSelect(e.target.value)}
              style={{ width: '100%' }}
            >
              <option value="">-- Choose a Batch --</option>
              {batches?.map((b: Batch) => (
                <option key={b.id} value={b.id}>
                  {b.batch_reference} ({b.obligation_count} items · {b.status})
                </option>
              ))}
            </select>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', paddingTop: 20, color: '#94A3B8', fontWeight: 600, fontSize: '0.8rem' }}>
            OR
          </div>

          {/* Manual UUID Input */}
          <div style={{ flex: 1, minWidth: 280 }}>
            <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: '#475569', marginBottom: 6 }}>
              Enter Specific Batch UUID:
            </label>
            <div style={{ display: 'flex', gap: 8 }}>
              <input
                type="text"
                className="form-input"
                placeholder="e.g. 4530b907-8887-40ca-b3b3-2ac841d16f56"
                value={customInput}
                onChange={(e) => setCustomInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleManualSearch()}
                style={{ height: 40 }}
              />
              <button
                className="btn btn-secondary"
                onClick={handleManualSearch}
                disabled={!customInput.trim()}
              >
                <span>Load</span>
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Audit Log Results */}
      {selectedBatchId && (
        <div className="card" style={{ padding: 24 }}>
          {/* Toolbar with Search and Stats */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 18, flexWrap: 'wrap', gap: 14 }}>
            <div>
              <div style={{ fontSize: '1.05rem', fontWeight: 800, color: '#003087' }}>
                Batch Event History
              </div>
              <code style={{ fontSize: '0.78rem', color: '#64748B' }}>
                ID: {selectedBatchId}
              </code>
            </div>

            {/* Elastic quick search */}
            <div style={{ position: 'relative', width: 280 }}>
              <Search size={15} style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: '#94A3B8' }} />
              <input
                type="text"
                className="form-input"
                style={{ padding: '8px 12px 8px 34px', fontSize: '0.82rem', borderRadius: 999 }}
                placeholder="Filter events, actors, payloads..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
            </div>
          </div>

          {isLoading ? (
            <div className="loading-state" style={{ padding: 48 }}>
              Loading audit trail records…
            </div>
          ) : isError ? (
            <div className="alert alert-error">
              Failed to load audit events for batch {selectedBatchId}.
            </div>
          ) : filteredEvents.length === 0 ? (
            <div className="empty-state" style={{ padding: 40 }}>
              <FileText size={32} color="#94A3B8" style={{ marginBottom: 10 }} />
              <p style={{ fontWeight: 600, color: '#334155' }}>No audit events found matching query</p>
            </div>
          ) : (
            <div className="table-wrapper" style={{ border: '1px solid #E2E8F0', borderRadius: 8 }}>
              <table className="obligations-table">
                <thead>
                  <tr>
                    <th>Timestamp</th>
                    <th>Event Type</th>
                    <th>Entity Scope</th>
                    <th>Authorized Actor</th>
                    <th>Transition Payload</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredEvents.map((ev) => (
                    <AuditEventRow key={ev.id} ev={ev} />
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <p className="disclaimer" style={{ marginTop: 18 }}>
            ⓘ Audit events are recorded chronologically and signed with internal idempotency correlation IDs.
          </p>
        </div>
      )}
    </div>
  )
}
