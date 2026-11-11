import React, { useState, useEffect, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  fetchAuditEvents,
  fetchBatches,
  type AuditEventOut,
} from '../api/client'
import { PageHeader } from '../components/layout/PageHeader'
import { StatusBadge } from '../components/common/StatusBadge'
import { ErrorState } from '../components/common/ErrorState'
import { EmptyState } from '../components/common/EmptyState'
import { TableSkeleton } from '../components/common/LoadingSkeleton'
import {
  ShieldCheck,
  Search,
  Filter,
  Layers,
  Clock,
  User,
  ChevronDown,
  ChevronUp,
  Copy,
  Check,
  Code,
} from 'lucide-react'

function parseDetails(raw: string | null): Record<string, unknown> | null {
  if (!raw) return null
  try {
    return JSON.parse(raw)
  } catch {
    return null
  }
}

export default function AuditPage() {
  const [selectedBatchId, setSelectedBatchId] = useState<string>('')
  const [customInputId, setCustomInputId] = useState<string>('')
  const [searchQuery, setSearchQuery] = useState('')
  const [eventTypeFilter, setEventTypeFilter] = useState('ALL')
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set())
  const [copiedId, setCopiedId] = useState<string | null>(null)

  // Fetch batches for quick-select
  const { data: batches } = useQuery({
    queryKey: ['batches'],
    queryFn: () => fetchBatches({ limit: 50 }),
  })

  // Set default batch
  useEffect(() => {
    if (batches && batches.length > 0 && !selectedBatchId) {
      setSelectedBatchId(batches[0].id)
    }
  }, [batches, selectedBatchId])

  // Fetch audit events for selected batch
  const {
    data: events,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ['audit', selectedBatchId],
    queryFn: () => fetchAuditEvents(selectedBatchId),
    enabled: !!selectedBatchId,
  })

  const toggleExpand = (id: string) => {
    setExpandedRows((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const handleCopy = (text: string, id: string) => {
    navigator.clipboard.writeText(text)
    setCopiedId(id)
    setTimeout(() => setCopiedId(null), 2000)
  }

  // Filter events
  const filteredEvents = useMemo(() => {
    if (!events) return []
    return events.filter((ev: AuditEventOut) => {
      if (eventTypeFilter !== 'ALL' && ev.event_type !== eventTypeFilter) {
        return false
      }
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase()
        const matchActor = ev.actor.toLowerCase().includes(q)
        const matchType = ev.event_type.toLowerCase().includes(q)
        const matchEntity = ev.entity_id.toLowerCase().includes(q)
        const matchPayload = (ev.details_redacted || '').toLowerCase().includes(q)
        const matchCorr = (ev.correlation_id || '').toLowerCase().includes(q)
        if (!matchActor && !matchType && !matchEntity && !matchPayload && !matchCorr) {
          return false
        }
      }
      return true
    })
  }, [events, eventTypeFilter, searchQuery])

  // Unique event types for filter
  const eventTypes = useMemo(() => {
    if (!events) return ['ALL']
    const set = new Set<string>(events.map((e) => e.event_type))
    return ['ALL', ...Array.from(set)]
  }, [events])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      {/* Header */}
      <PageHeader
        title="Compliance & Audit Trail"
        subtitle="Tamper-evident chronological record of financial state transitions, dual-control approvals, and PayPal settlement receipts."
        badge={
          <span
            style={{
              fontSize: '0.72rem',
              padding: '3px 10px',
              borderRadius: 'var(--radius-pill)',
              background: 'var(--pufi-success-bg)',
              color: 'var(--pufi-success-text)',
              border: '1px solid var(--pufi-success-border)',
              fontWeight: 700,
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
            }}
          >
            <ShieldCheck size={13} />
            Append-Only Audit Engine
          </span>
        }
      />

      {/* Batch Selector & Direct Lookup Strip */}
      <div
        style={{
          background: 'var(--bg-surface)',
          border: '1px solid var(--border-base)',
          borderRadius: 'var(--radius-lg)',
          padding: '20px 24px',
          boxShadow: 'var(--shadow-card)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: 16,
        }}
      >
        {/* Quick Batch Selector */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, flex: 1, minWidth: 280 }}>
          <Layers size={18} color="var(--pufi-primary)" />
          <div style={{ flex: 1 }}>
            <label style={{ display: 'block', fontSize: '0.74rem', color: 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase' }}>
              Select Payment Batch
            </label>
            <select
              value={selectedBatchId}
              onChange={(e) => setSelectedBatchId(e.target.value)}
              style={{
                width: '100%',
                padding: '8px 12px',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--border-base)',
                background: 'var(--bg-subtle)',
                color: 'var(--text-primary)',
                fontSize: '0.86rem',
                fontWeight: 700,
                outline: 'none',
                cursor: 'pointer',
              }}
            >
              {batches?.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.batch_reference} ({b.obligation_count} items • {b.status})
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Direct UUID Lookup */}
        <div style={{ display: 'flex', alignItems: 'flex-end', gap: 8 }}>
          <div>
            <label style={{ display: 'block', fontSize: '0.74rem', color: 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase', marginBottom: 4 }}>
              Direct UUID Lookup
            </label>
            <input
              type="text"
              placeholder="Paste exact batch ID..."
              value={customInputId}
              onChange={(e) => setCustomInputId(e.target.value)}
              style={{
                padding: '8px 12px',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--border-base)',
                background: 'var(--bg-subtle)',
                fontSize: '0.82rem',
                color: 'var(--text-primary)',
                fontFamily: 'monospace',
                width: 220,
              }}
            />
          </div>
          <button
            onClick={() => {
              if (customInputId.trim()) setSelectedBatchId(customInputId.trim())
            }}
            style={{
              padding: '8px 14px',
              borderRadius: 'var(--radius-sm)',
              border: 'none',
              background: 'var(--pufi-primary)',
              color: '#FFFFFF',
              fontSize: '0.82rem',
              fontWeight: 650,
              cursor: 'pointer',
            }}
          >
            Lookup
          </button>
        </div>
      </div>

      {isError && (
        <ErrorState
          title="Failed to Load Audit Trail"
          message={(error as { error?: { message?: string } })?.error?.message || 'Unable to retrieve audit events for this batch.'}
          onRetry={() => refetch()}
        />
      )}

      {/* Main Audit Records Container */}
      <div
        style={{
          background: 'var(--bg-surface)',
          border: '1px solid var(--border-base)',
          borderRadius: 'var(--radius-lg)',
          boxShadow: 'var(--shadow-card)',
          overflow: 'hidden',
        }}
      >
        {/* Search & Filter Header */}
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
              placeholder="Search actors, event types, payloads, correlation IDs..."
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

          {/* Event Type Filter */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Filter size={14} color="var(--text-muted)" />
            <select
              value={eventTypeFilter}
              onChange={(e) => setEventTypeFilter(e.target.value)}
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
              {eventTypes.map((t) => (
                <option key={t} value={t}>
                  {t === 'ALL' ? 'All Event Types' : t}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Loading skeleton */}
        {isLoading && (
          <div style={{ padding: 24 }}>
            <TableSkeleton rows={6} columns={5} />
          </div>
        )}

        {/* Empty State */}
        {!isLoading && filteredEvents.length === 0 && (
          <div style={{ padding: 48 }}>
            <EmptyState
              title="No Audit Events Recorded"
              description="No state transitions have been recorded yet for the selected batch."
            />
          </div>
        )}

        {/* Chronological Audit Table */}
        {!isLoading && filteredEvents.length > 0 && (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.82rem' }}>
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
                  <th style={{ padding: '12px 20px', fontWeight: 700 }}>Timestamp (UTC)</th>
                  <th style={{ padding: '12px 16px', fontWeight: 700 }}>Event Classification</th>
                  <th style={{ padding: '12px 16px', fontWeight: 700 }}>Scope Entity</th>
                  <th style={{ padding: '12px 16px', fontWeight: 700 }}>Authorised Actor</th>
                  <th style={{ padding: '12px 16px', fontWeight: 700 }}>Correlation ID</th>
                  <th style={{ padding: '12px 20px', textAlign: 'right' }}>Payload Diff</th>
                </tr>
              </thead>
              <tbody>
                {filteredEvents.map((ev: AuditEventOut) => {
                  const isExpanded = expandedRows.has(ev.id)
                  const details = parseDetails(ev.details_redacted)

                  return (
                    <React.Fragment key={ev.id}>
                      <tr
                        style={{
                          borderBottom: isExpanded ? 'none' : '1px solid var(--border-subtle)',
                          transition: 'background var(--trans-fast)',
                        }}
                        onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'var(--bg-surface-hover)')}
                        onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
                      >
                        <td style={{ padding: '14px 20px', whiteSpace: 'nowrap', color: 'var(--text-secondary)' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                            <Clock size={13} color="var(--text-muted)" />
                            <span>{new Date(ev.created_at).toLocaleString()}</span>
                          </div>
                        </td>

                        <td style={{ padding: '14px 16px' }}>
                          <StatusBadge status={ev.event_type} size="sm" />
                        </td>

                        <td style={{ padding: '14px 16px' }}>
                          <span style={{ fontSize: '0.74rem', fontWeight: 700, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>
                            {ev.entity_type}
                          </span>
                          <code style={{ fontSize: '0.72rem', background: 'var(--bg-subtle)', padding: '2px 6px', borderRadius: 4, marginLeft: 6, color: 'var(--pufi-primary)' }}>
                            {ev.entity_id.slice(-8)}
                          </code>
                        </td>

                        <td style={{ padding: '14px 16px' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                            <User size={13} color="var(--pufi-primary)" />
                            <strong style={{ color: 'var(--text-primary)' }}>{ev.actor}</strong>
                          </div>
                        </td>

                        <td style={{ padding: '14px 16px' }}>
                          {ev.correlation_id ? (
                            <code
                              style={{
                                fontSize: '0.74rem',
                                color: 'var(--text-muted)',
                                cursor: 'pointer',
                              }}
                              onClick={() => handleCopy(ev.correlation_id!, ev.id)}
                              title="Click to copy correlation ID"
                            >
                              {copiedId === ev.id ? '✓ Copied' : ev.correlation_id.slice(-8)}
                            </code>
                          ) : (
                            <span style={{ color: 'var(--text-muted)' }}>—</span>
                          )}
                        </td>

                        <td style={{ padding: '14px 20px', textAlign: 'right' }}>
                          {details ? (
                            <button
                              onClick={() => toggleExpand(ev.id)}
                              style={{
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: 4,
                                padding: '4px 10px',
                                borderRadius: 'var(--radius-sm)',
                                background: isExpanded ? 'var(--pufi-primary-light)' : 'var(--bg-subtle)',
                                color: isExpanded ? 'var(--pufi-primary)' : 'var(--text-secondary)',
                                border: '1px solid var(--border-base)',
                                fontSize: '0.74rem',
                                fontWeight: 650,
                                cursor: 'pointer',
                              }}
                            >
                              <Code size={12} />
                              <span>{isExpanded ? 'Hide Payload' : 'Inspect JSON'}</span>
                              {isExpanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                            </button>
                          ) : (
                            <span style={{ color: 'var(--text-muted)', fontSize: '0.74rem' }}>No diff</span>
                          )}
                        </td>
                      </tr>

                      {/* Expanded JSON diff row */}
                      {isExpanded && details && (
                        <tr style={{ borderBottom: '1px solid var(--border-subtle)', background: 'var(--bg-subtle)' }}>
                          <td colSpan={6} style={{ padding: '14px 24px' }}>
                            <div
                              style={{
                                background: 'var(--bg-surface)',
                                border: '1px solid var(--border-base)',
                                borderRadius: 'var(--radius-md)',
                                padding: 14,
                                position: 'relative',
                              }}
                            >
                              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                                <span style={{ fontSize: '0.74rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                                  Redacted Transition Payload Diff
                                </span>
                                <button
                                  onClick={() => handleCopy(JSON.stringify(details, null, 2), `payload-${ev.id}`)}
                                  style={{
                                    display: 'inline-flex',
                                    alignItems: 'center',
                                    gap: 4,
                                    background: 'transparent',
                                    border: 'none',
                                    color: 'var(--pufi-primary)',
                                    fontSize: '0.74rem',
                                    fontWeight: 650,
                                    cursor: 'pointer',
                                  }}
                                >
                                  {copiedId === `payload-${ev.id}` ? <Check size={12} /> : <Copy size={12} />}
                                  <span>{copiedId === `payload-${ev.id}` ? 'Copied' : 'Copy JSON'}</span>
                                </button>
                              </div>
                              <pre
                                style={{
                                  margin: 0,
                                  fontSize: '0.75rem',
                                  fontFamily: 'monospace',
                                  lineHeight: 1.45,
                                  color: 'var(--text-primary)',
                                  maxHeight: 260,
                                  overflowY: 'auto',
                                }}
                              >
                                {JSON.stringify(details, null, 2)}
                              </pre>
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
