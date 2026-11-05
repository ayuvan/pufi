/**
 * PUFI — Batch Detail Page (Day 4)
 *
 * Shows:
 *  - Batch header (ID, reference, status)
 *  - Analysis panel with link to run analysis
 *  - Approval panel (when analysis exists and batch is in DRAFT/VALIDATED state)
 *  - PayPal execution panel (when batch is APPROVED)
 *  - Payout instructions table (when SUBMITTED/PROCESSING/COMPLETED)
 *  - Audit event log
 *
 * IMPORTANT: All execution is SANDBOX only. No real money moves.
 */

import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  fetchBatch,
  fetchBatchAnalysis,
  approveBatch,
  submitBatch,
  refreshBatchStatus,
  fetchInstructions,
  fetchAuditEvents,
  type Batch,
  type BatchAnalysis,
  type ApproveRequest,
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

function StatusPill({ status }: { status: string }) {
  const cls = `status-badge status-${status.toLowerCase()}`
  return <span className={cls}>{status}</span>
}

function SandboxBadge() {
  return (
    <div className="sandbox-banner" role="note">
      🧪 <strong>SANDBOX ENVIRONMENT</strong> — No real money moves. PayPal Sandbox only.
      HTTP 2xx acceptance does not confirm fund settlement.
    </div>
  )
}

// -------------------------------------------------------------------------
// Analysis panel
// -------------------------------------------------------------------------

function AnalysisPanel({
  batchId,
  analysis,
  onAnalysed,
}: {
  batchId: string
  analysis: BatchAnalysis | null
  onAnalysed: (a: BatchAnalysis) => void
}) {
  const [strategy, setStrategy] = useState<'LOWEST_COST' | 'FASTEST' | 'BALANCED'>('LOWEST_COST')

  const mutation = useMutation({
    mutationFn: () => fetchBatchAnalysis(batchId, strategy),
    onSuccess: onAnalysed,
  })

  if (!analysis) {
    return (
      <div className="panel">
        <h3 className="panel-title">Financial Analysis</h3>
        <p className="text-muted">No analysis yet. Run the routing engine to evaluate providers.</p>
        <div className="form-row" style={{ maxWidth: 300 }}>
          <label className="form-label">Routing Strategy</label>
          <select
            className="form-input"
            value={strategy}
            onChange={(e) => setStrategy(e.target.value as typeof strategy)}
          >
            <option value="LOWEST_COST">Lowest Cost</option>
            <option value="FASTEST">Fastest</option>
            <option value="BALANCED">Balanced</option>
          </select>
        </div>
        {mutation.isError && (
          <div className="alert alert-error">
            Analysis failed: {String((mutation.error as { error?: { message?: string } })?.error?.message ?? 'Unknown error')}
          </div>
        )}
        <button
          className="btn btn-primary"
          onClick={() => mutation.mutate()}
          disabled={mutation.isPending}
        >
          {mutation.isPending ? 'Analysing…' : 'Run Analysis'}
        </button>
      </div>
    )
  }

  const eligible = analysis.provider_routes.filter((r) => r.eligible)
  const excluded = analysis.provider_routes.filter((r) => !r.eligible)
  const ai = analysis.ai_recommendation

  return (
    <div className="panel">
      <h3 className="panel-title">Financial Analysis</h3>
      <div className="analysis-meta">
        <span className="badge badge-info">{analysis.routing_strategy}</span>
        <span className="badge badge-warning">{analysis.funding_snapshot_label}</span>
        <span className="badge badge-info">{analysis.analysis_label}</span>
      </div>

      <div className="currency-summary">
        {Object.entries(analysis.total_amount_by_currency).map(([ccy, amt]) => (
          <div key={ccy} className="currency-item">
            <span className="currency-code">{ccy}</span>
            <span className="currency-amount">{formatAmount(amt, ccy)}</span>
          </div>
        ))}
      </div>

      {/* Eligible providers */}
      {eligible.length > 0 && (
        <div className="route-section">
          <h4 className="route-section-title">✓ Eligible Providers ({eligible.length})</h4>
          <div className="table-wrapper">
            <table className="obligations-table">
              <thead>
                <tr>
                  <th>Provider</th>
                  <th>Environment</th>
                  <th className="col-amount">Fee</th>
                  <th className="col-amount">FX Spread</th>
                  <th className="col-amount">Total Cost</th>
                  <th>Label</th>
                </tr>
              </thead>
              <tbody>
                {eligible.map((r) => (
                  <tr key={r.provider_code}>
                    <td><strong>{r.display_name}</strong></td>
                    <td><span className={`badge badge-${r.environment.toLowerCase()}`}>{r.environment}</span></td>
                    <td className="col-amount">{r.provider_fee ? formatAmount(r.provider_fee, 'USD') : '—'}</td>
                    <td className="col-amount">{r.fx_spread_cost ? formatAmount(r.fx_spread_cost, 'USD') : '—'}</td>
                    <td className="col-amount">{r.total_estimated_cost ? formatAmount(r.total_estimated_cost, 'USD') : '—'}</td>
                    <td><span className={`badge badge-${r.quote_label.toLowerCase()}`}>{r.quote_label}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Excluded providers */}
      {excluded.length > 0 && (
        <div className="route-section">
          <h4 className="route-section-title">✗ Excluded Providers ({excluded.length})</h4>
          {excluded.map((r) => (
            <div key={r.provider_code} className="excluded-route">
              <strong>{r.display_name}</strong>
              <ul>
                {r.exclusion_reasons.map((reason, i) => (
                  <li key={i}>{reason}</li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}

      {/* AI recommendation */}
      {ai && (
        <div className={`ai-recommendation ${ai.fallback_used ? 'ai-fallback' : ''}`}>
          <h4 className="ai-title">
            🤖 AI Advisory
            {ai.fallback_used && <span className="badge badge-warning ml-2">FALLBACK</span>}
            <span className="badge badge-info ml-2">{ai.model_name}</span>
          </h4>
          {ai.fallback_reason && (
            <p className="ai-fallback-reason">Fallback reason: {ai.fallback_reason}</p>
          )}
          <p className="ai-summary">{ai.summary}</p>
          {ai.recommended_route && (
            <p><strong>Recommended route:</strong> <code>{ai.recommended_route}</code></p>
          )}
          {ai.reasoning_factors.length > 0 && (
            <ul className="ai-factors">
              {ai.reasoning_factors.map((f, i) => <li key={i}>{f}</li>)}
            </ul>
          )}
          {ai.warnings.length > 0 && (
            <div className="alert alert-warning">
              {ai.warnings.map((w, i) => <p key={i}>⚠ {w}</p>)}
            </div>
          )}
          {ai.requires_human_review && (
            <div className="alert alert-warning">⚠ This batch requires human review before approval.</div>
          )}
          <p className="ai-disclaimer text-muted">
            AI is advisory only. It cannot approve batches, execute payments, or override eligibility checks.
          </p>
        </div>
      )}

      <p className="disclaimer">{analysis.disclaimer}</p>

      {/* Re-run button */}
      <button
        className="btn btn-secondary"
        onClick={() => mutation.mutate()}
        disabled={mutation.isPending}
      >
        {mutation.isPending ? 'Re-analysing…' : '↺ Re-run Analysis'}
      </button>
    </div>
  )
}

// -------------------------------------------------------------------------
// Approval panel
// -------------------------------------------------------------------------

function ApprovalPanel({
  batchId,
  analysis,
  batch,
  onApproved,
}: {
  batchId: string
  analysis: BatchAnalysis | null
  batch: Batch
  onApproved: () => void
}) {
  const queryClient = useQueryClient()
  const [approverId, setApproverId] = useState('DEMO-APPROVER-001')
  const [confirmed, setConfirmed] = useState(false)

  const eligible = analysis?.provider_routes.filter((r) => r.eligible) ?? []
  const recommended = analysis?.ai_recommendation?.recommended_route ?? eligible[0]?.provider_code ?? ''
  const [selectedProvider, setSelectedProvider] = useState(recommended)
  const [strategy, setStrategy] = useState(analysis?.routing_strategy ?? 'LOWEST_COST')

  // Compute totals from analysis
  const totalByCurrency = analysis?.total_amount_by_currency ?? {}
  const currencies = Object.keys(totalByCurrency)
  const primaryCurrency = currencies[0] ?? 'USD'
  const primaryAmount = totalByCurrency[primaryCurrency] ?? '0.00'

  const mutation = useMutation({
    mutationFn: () => {
      const req: ApproveRequest = {
        approver_id: approverId.trim() || 'DEMO-APPROVER-001',
        routing_strategy: strategy,
        selected_provider_code: selectedProvider,
        confirmed_total_amount: primaryAmount,
        confirmed_currency: primaryCurrency,
        confirmed_recipient_count: batch.obligation_count,
      }
      return approveBatch(batchId, req)
    },
    onSuccess: (resp) => {
      if (resp.success) {
        queryClient.invalidateQueries({ queryKey: ['batch', batchId] })
        onApproved()
      }
    },
  })

  const canApprove =
    !!analysis &&
    eligible.length > 0 &&
    !!selectedProvider &&
    confirmed &&
    !mutation.isPending &&
    batch.status !== 'APPROVED' &&
    batch.status !== 'SUBMITTED'

  if (!analysis || eligible.length === 0) {
    return (
      <div className="panel">
        <h3 className="panel-title">Approve Batch</h3>
        <div className="alert alert-info">
          ⓘ Run financial analysis first. Approval requires at least one eligible provider.
        </div>
      </div>
    )
  }

  if (batch.status === 'APPROVED') {
    return (
      <div className="panel">
        <h3 className="panel-title">Approve Batch</h3>
        <div className="alert alert-success">
          ✓ Batch approved by <strong>{batch.approved_by}</strong> at{' '}
          {batch.approved_at ? new Date(batch.approved_at).toLocaleString() : '—'}.
        </div>
      </div>
    )
  }

  return (
    <div className="panel">
      <h3 className="panel-title">Approve Batch for Submission</h3>

      <div className="alert alert-warning">
        ⚠ Approval authorises submission to PayPal Sandbox. This is a prototype
        demo — no real funds will move. Only SANDBOX test accounts are used.
      </div>

      <div className="form-grid">
        <div className="form-row">
          <label className="form-label">Approver ID</label>
          <input
            className="form-input"
            value={approverId}
            onChange={(e) => setApproverId(e.target.value)}
            placeholder="e.g. DEMO-APPROVER-001"
          />
        </div>

        <div className="form-row">
          <label className="form-label">Routing Strategy</label>
          <select
            className="form-input"
            value={strategy}
            onChange={(e) => setStrategy(e.target.value)}
          >
            <option value="LOWEST_COST">Lowest Cost</option>
            <option value="FASTEST">Fastest</option>
            <option value="BALANCED">Balanced</option>
          </select>
        </div>

        <div className="form-row">
          <label className="form-label">Selected Provider</label>
          <select
            className="form-input"
            value={selectedProvider}
            onChange={(e) => setSelectedProvider(e.target.value)}
          >
            {eligible.map((r) => (
              <option key={r.provider_code} value={r.provider_code}>
                {r.display_name} ({r.environment})
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="approval-summary">
        <strong>Approving:</strong> {batch.obligation_count} obligations ·{' '}
        {formatAmount(primaryAmount, primaryCurrency)} {primaryCurrency}
      </div>

      <label className="checkbox-label">
        <input
          type="checkbox"
          checked={confirmed}
          onChange={(e) => setConfirmed(e.target.checked)}
        />
        I confirm this batch is correct and authorise SANDBOX submission to PayPal.
      </label>

      {mutation.isError && (
        <div className="alert alert-error">
          Approval failed:{' '}
          {String(
            (mutation.error as { error?: { message?: string } })?.error?.message ??
              (mutation.error as { detail?: string })?.detail ??
              'Unknown error'
          )}
        </div>
      )}

      {mutation.data && !mutation.data.success && (
        <div className="alert alert-error">
          Approval rejected: {mutation.data.error_message}
        </div>
      )}

      <button
        className="btn btn-primary"
        onClick={() => mutation.mutate()}
        disabled={!canApprove}
      >
        {mutation.isPending ? 'Approving…' : 'Approve for Sandbox Submission'}
      </button>
    </div>
  )
}

// -------------------------------------------------------------------------
// PayPal execution panel
// -------------------------------------------------------------------------

function ExecutionPanel({ batchId, batch }: { batchId: string; batch: Batch }) {
  const queryClient = useQueryClient()

  const submitMutation = useMutation({
    mutationFn: () => submitBatch(batchId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['batch', batchId] })
      queryClient.invalidateQueries({ queryKey: ['instructions', batchId] })
    },
  })

  const refreshMutation = useMutation({
    mutationFn: () => refreshBatchStatus(batchId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['batch', batchId] })
      queryClient.invalidateQueries({ queryKey: ['instructions', batchId] })
    },
  })

  const { data: instructions } = useQuery({
    queryKey: ['instructions', batchId],
    queryFn: () => fetchInstructions(batchId),
    enabled: ['SUBMITTED', 'PROCESSING', 'COMPLETED', 'PARTIALLY_COMPLETED', 'FAILED'].includes(batch.status),
  })

  const submitResult = submitMutation.data
  const refreshResult = refreshMutation.data

  const canSubmit = batch.status === 'APPROVED' && !submitMutation.isPending
  const canRefresh =
    ['SUBMITTED', 'PROCESSING'].includes(batch.status) && !refreshMutation.isPending

  return (
    <div className="panel">
      <SandboxBadge />

      <h3 className="panel-title">PayPal Sandbox Execution</h3>

      <div className="execution-actions">
        {batch.status === 'APPROVED' && (
          <div>
            <button
              className="btn btn-primary"
              onClick={() => submitMutation.mutate()}
              disabled={!canSubmit}
            >
              {submitMutation.isPending ? 'Submitting…' : 'Submit to PayPal Sandbox'}
            </button>
            <p className="disclaimer">
              Submitting creates PayPal payout items using SANDBOX test accounts. No real money moves.
            </p>
          </div>
        )}

        {canRefresh && (
          <button
            className="btn btn-secondary"
            onClick={() => refreshMutation.mutate()}
            disabled={!canRefresh}
          >
            {refreshMutation.isPending ? 'Refreshing…' : '↺ Refresh Status'}
          </button>
        )}
      </div>

      {/* Submit result */}
      {submitResult && (
        <div className={`alert ${submitResult.success ? 'alert-success' : 'alert-error'}`}>
          {submitResult.success ? (
            <>
              ✓ Batch submitted.{' '}
              {submitResult.paypal_configured ? (
                <>
                  PayPal Payout Batch ID: <code>{submitResult.paypal_payout_batch_id}</code>
                </>
              ) : (
                <span className="badge badge-warning">SIMULATED — PayPal not configured</span>
              )}
            </>
          ) : (
            <>✗ Submission failed: {submitResult.error_message}</>
          )}
          <p className="disclaimer">{submitResult.disclaimer}</p>
        </div>
      )}

      {/* Refresh result */}
      {refreshResult && (
        <div className={`alert ${refreshResult.success ? 'alert-info' : 'alert-error'}`}>
          {refreshResult.success ? (
            <>
              Status refreshed · PayPal status: <code>{refreshResult.paypal_batch_status}</code>
              · Completed: {refreshResult.completed} · Failed: {refreshResult.failed}
              · Pending: {refreshResult.pending}
            </>
          ) : (
            <>✗ Refresh failed: {refreshResult.error_message}</>
          )}
        </div>
      )}

      {/* Instructions table */}
      {instructions && instructions.length > 0 && (
        <div className="route-section">
          <h4 className="route-section-title">Payout Instructions</h4>
          <div className="table-wrapper">
            <table className="obligations-table small">
              <thead>
                <tr>
                  <th>Obligation</th>
                  <th>Provider</th>
                  <th className="col-amount">Amount</th>
                  <th>Ccy</th>
                  <th>Status</th>
                  <th>Settlement</th>
                  <th>PayPal Item ID</th>
                  <th>Txn ID</th>
                  <th>Error</th>
                </tr>
              </thead>
              <tbody>
                {instructions.map((instr) => (
                  <tr key={instr.id}>
                    <td><code style={{ fontSize: '0.7em' }}>{instr.obligation_id.slice(-8)}</code></td>
                    <td>{instr.provider_code}</td>
                    <td className="col-amount">{formatAmount(instr.amount, instr.currency)}</td>
                    <td><span className="currency-code">{instr.currency}</span></td>
                    <td><StatusPill status={instr.status} /></td>
                    <td>
                      <span className={`badge badge-${instr.settlement_evidence === 'PROVIDER_REPORTED_COMPLETE' ? 'success' : 'warning'}`}>
                        {instr.settlement_evidence}
                      </span>
                    </td>
                    <td>{instr.paypal_payout_item_id ?? '—'}</td>
                    <td>{instr.paypal_transaction_id ?? '—'}</td>
                    <td className="text-muted">{instr.error_message ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

// -------------------------------------------------------------------------
// Audit log
// -------------------------------------------------------------------------

function AuditLog({ batchId }: { batchId: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ['audit', batchId],
    queryFn: () => fetchAuditEvents(batchId),
    refetchInterval: 10000,
  })

  if (isLoading) return <div className="loading-state">Loading audit log…</div>
  if (!data || data.length === 0) return null

  return (
    <div className="panel">
      <h3 className="panel-title">Audit Log</h3>
      <div className="table-wrapper">
        <table className="obligations-table small">
          <thead>
            <tr>
              <th>Time</th>
              <th>Event</th>
              <th>Actor</th>
              <th>Details</th>
            </tr>
          </thead>
          <tbody>
            {data.map((ev) => (
              <tr key={ev.id}>
                <td style={{ whiteSpace: 'nowrap' }}>{new Date(ev.created_at).toLocaleString()}</td>
                <td><strong>{ev.event_type}</strong></td>
                <td>{ev.actor}</td>
                <td>
                  {ev.details_redacted && (
                    <details>
                      <summary>view</summary>
                      <pre style={{ fontSize: '0.7em', maxWidth: 400, overflow: 'auto' }}>
                        {JSON.stringify(JSON.parse(ev.details_redacted), null, 2)}
                      </pre>
                    </details>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// -------------------------------------------------------------------------
// Main page
// -------------------------------------------------------------------------

export default function BatchDetailPage({ batchId, onBack }: { batchId: string; onBack: () => void }) {
  const queryClient = useQueryClient()
  const [analysis, setAnalysis] = useState<BatchAnalysis | null>(null)

  const { data: batch, isLoading, isError } = useQuery({
    queryKey: ['batch', batchId],
    queryFn: () => fetchBatch(batchId),
    refetchInterval: 15000,
  })

  if (isLoading) return <div className="loading-state">Loading batch…</div>
  if (isError || !batch) {
    return (
      <div className="page">
        <div className="alert alert-error">Failed to load batch {batchId}.</div>
        <button className="btn btn-secondary" onClick={onBack}>← Back</button>
      </div>
    )
  }

  const showApproval = ['DRAFT', 'VALIDATED', 'ANALYZED'].includes(batch.status)
  const showExecution = ['APPROVED', 'SUBMITTED', 'PROCESSING', 'COMPLETED', 'PARTIALLY_COMPLETED', 'FAILED'].includes(batch.status)

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <div className="breadcrumb">
            <button className="btn-link" onClick={onBack}>← Batches</button>
          </div>
          <h1 className="page-title">{batch.batch_reference}</h1>
          <div className="batch-meta-row">
            <StatusPill status={batch.status} />
            <span className="text-muted">{batch.obligation_count} obligation{batch.obligation_count !== 1 ? 's' : ''}</span>
            <span className="text-muted">Created {new Date(batch.created_at).toLocaleDateString()}</span>
          </div>
          <code className="batch-id-display">{batch.id}</code>
        </div>
      </div>

      {/* Analysis */}
      <AnalysisPanel
        batchId={batchId}
        analysis={analysis}
        onAnalysed={(a) => {
          setAnalysis(a)
          queryClient.invalidateQueries({ queryKey: ['batch', batchId] })
        }}
      />

      {/* Approval */}
      {showApproval && (
        <ApprovalPanel
          batchId={batchId}
          analysis={analysis}
          batch={batch}
          onApproved={() => queryClient.invalidateQueries({ queryKey: ['batch', batchId] })}
        />
      )}

      {/* Execution */}
      {showExecution && (
        <ExecutionPanel batchId={batchId} batch={batch} />
      )}

      {/* Audit log */}
      <AuditLog batchId={batchId} />
    </div>
  )
}
