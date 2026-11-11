/**
 * PUFI — Batch Detail Page (PayPal Enterprise Edition)
 *
 * Shows:
 *  - Bryntum-inspired Lifecycle Stepper
 *  - Batch header (ID, reference, status)
 *  - Analysis panel with multi-provider routing & Gemini AI advisor
 *  - Maker-checker approval panel
 *  - PayPal Sandbox execution with official PayPal Gold CTA
 *  - Payout settlement instructions table
 *  - Elastic-searchable immutable audit trail
 */

import { useState, useMemo } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  CheckCircle2,
  ShieldCheck,
  Cpu,
  Search,
  Lock,
} from 'lucide-react'
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
  type ProviderRoute,
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

function formatErrorMessage(err: unknown): string {
  if (!err) return 'Unknown error'
  if (typeof err === 'string') return err
  const obj = err as Record<string, any>
  if (obj.detail) {
    if (typeof obj.detail === 'string') return obj.detail
    if (typeof obj.detail === 'object') {
      if (obj.detail.message) return String(obj.detail.message)
      if (obj.detail.error) return String(obj.detail.error)
      if (Array.isArray(obj.detail)) {
        return obj.detail.map((d: any) => d.msg || JSON.stringify(d)).join(', ')
      }
    }
  }
  if (obj.error?.message) return String(obj.error.message)
  if (obj.message) return String(obj.message)
  return JSON.stringify(err)
}

function StatusPill({ status }: { status: string }) {
  const cls = `status-badge status-${status.toLowerCase()}`
  return <span className={cls}>{status}</span>
}

function SandboxBadge() {
  return (
    <div className="sandbox-live-badge" style={{ marginBottom: 16, padding: '8px 16px', fontSize: '0.8rem', width: 'fit-content' }}>
      <span className="live-dot" />
      <span>
        <strong>PAYPAL SANDBOX ENVIRONMENT</strong> — Prototype demonstration. No real funds move.
      </span>
    </div>
  )
}

// -------------------------------------------------------------------------
// Bryntum-inspired Lifecycle Stepper
// -------------------------------------------------------------------------

function LifecycleStepper({ status, hasAnalysis }: { status: string; hasAnalysis: boolean }) {
  const steps = [
    { key: 'DRAFT', label: '1. Ingestion & Batching' },
    { key: 'ANALYZED', label: '2. AI Route Analysis' },
    { key: 'APPROVED', label: '3. Dual-Control Approval' },
    { key: 'SUBMITTED', label: '4. PayPal Sandbox Execution' },
    { key: 'COMPLETED', label: '5. Settlement Evidence' },
  ]

  let currentIndex = 0
  if (status === 'DRAFT' && hasAnalysis) currentIndex = 1
  else if (status === 'ANALYZED') currentIndex = 1
  else if (status === 'APPROVED') currentIndex = 2
  else if (['SUBMITTED', 'PROCESSING'].includes(status)) currentIndex = 3
  else if (['COMPLETED', 'PARTIALLY_COMPLETED'].includes(status)) currentIndex = 4

  const progressPct = (currentIndex / (steps.length - 1)) * 100

  return (
    <div className="lifecycle-stepper">
      <div className="stepper-track">
        <div className="stepper-progress" style={{ width: `${progressPct}%` }} />
      </div>
      {steps.map((step, idx) => {
        const isDone = idx < currentIndex
        const isActive = idx === currentIndex
        return (
          <div
            key={step.key}
            className={`stepper-step ${isDone ? 'completed' : ''} ${isActive ? 'active' : ''}`}
          >
            <div className="step-circle">
              {isDone ? <CheckCircle2 size={16} /> : idx + 1}
            </div>
            <span className="step-label">{step.label}</span>
          </div>
        )
      })}
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

  const eligibleRoutes: ProviderRoute[] = useMemo(
    () => (analysis?.provider_routes ?? []).filter((r) => r.eligible),
    [analysis]
  )

  const excludedRoutes: ProviderRoute[] = useMemo(
    () => (analysis?.provider_routes ?? []).filter((r) => !r.eligible),
    [analysis]
  )

  return (
    <div className="panel">
      <div className="panel-title">
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <Cpu size={20} color="#0070BA" />
          <span>Financial Route Analysis & AI Advisory</span>
        </div>
        {analysis && (
          <span className="ai-header-badge">
            {analysis.ai_recommendation?.model_name ?? 'Gemini 3.8 Flash'} • Deterministic Fallback
          </span>
        )}
      </div>

      <p style={{ fontSize: '0.84rem', color: '#64748B', marginBottom: 16 }}>
        Multi-provider routing engine compares eligible settlement rails, converts FX quotes, and generates an AI advisory summary.
      </p>

      {/* Query controls */}
      <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap', marginBottom: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <label style={{ fontSize: '0.82rem', fontWeight: 600, color: '#334155' }}>Optimization Strategy:</label>
          <select
            className="select"
            value={strategy}
            onChange={(e) => setStrategy(e.target.value as any)}
            style={{ width: 'auto', minWidth: 160 }}
          >
            <option value="LOWEST_COST">Lowest Cost (Fee & FX)</option>
            <option value="FASTEST">Fastest Settlement Speed</option>
            <option value="BALANCED">Balanced Optimization</option>
          </select>
        </div>

        <button
          className="btn btn-paypal-blue"
          onClick={() => mutation.mutate()}
          disabled={mutation.isPending}
        >
          {mutation.isPending ? 'Analyzing Routes…' : 'Run Route Analysis'}
        </button>
      </div>

      {mutation.isError && (
        <div className="alert alert-error">
          Analysis failed: {formatErrorMessage(mutation.error)}
        </div>
      )}

      {/* Analysis results */}
      {analysis && (
        <div>
          {/* Currency summary chips */}
          <div style={{ display: 'flex', gap: 12, marginBottom: 16, flexWrap: 'wrap' }}>
            {Object.entries(analysis.total_amount_by_currency).map(([ccy, totalAmt]) => (
              <div
                key={ccy}
                style={{
                  background: '#F8FAFC',
                  border: '1px solid #CBD5E1',
                  borderRadius: 8,
                  padding: '10px 16px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 12,
                }}
              >
                <div>
                  <div style={{ fontSize: '0.72rem', color: '#64748B', fontWeight: 700, textTransform: 'uppercase' }}>
                    {ccy} Total
                  </div>
                  <div style={{ fontSize: '1.25rem', fontWeight: 800, color: '#003087' }}>
                    {formatAmount(totalAmt, ccy)}
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Route Comparison Grid */}
          <h4 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#0F172A', marginBottom: 12 }}>
            Evaluated Provider Routes ({eligibleRoutes.length} Eligible)
          </h4>

          <div className="route-cards-grid">
            {eligibleRoutes.map((r, i) => {
              const isBest = i === 0
              return (
                <div key={r.provider_code} className={`route-card ${isBest ? 'recommended' : ''}`}>
                  {isBest && <span className="route-badge-recommended">Top Ranked</span>}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
                    <div>
                      <div style={{ fontWeight: 800, fontSize: '1rem', color: '#003087' }}>{r.display_name}</div>
                      <span className="env-badge env-badge-sandbox">{r.environment}</span>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <div style={{ fontSize: '1.1rem', fontWeight: 800, color: '#0F172A' }}>
                        {formatAmount(r.total_estimated_cost ?? '0.00', 'USD')}
                      </div>
                      <span style={{ fontSize: '0.72rem', color: '#64748B' }}>Est. Total Cost</span>
                    </div>
                  </div>

                  <div style={{ borderTop: '1px solid #E2E8F0', paddingTop: 10, marginTop: 10, fontSize: '0.78rem', color: '#475569', display: 'flex', flexDirection: 'column', gap: 4 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span>Estimated Fee:</span>
                      <strong>{formatAmount(r.provider_fee ?? '0.00', 'USD')}</strong>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span>FX Spread:</span>
                      <strong>{formatAmount(r.fx_spread_cost ?? '0.00', 'USD')}</strong>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span>Estimated Processing:</span>
                      <strong>{r.estimated_processing_hours ? `${r.estimated_processing_hours} hours` : 'Standard'}</strong>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>

          {/* Excluded routes */}
          {excludedRoutes.length > 0 && (
            <div style={{ marginTop: 20 }}>
              <div style={{ fontSize: '0.82rem', fontWeight: 700, color: '#64748B', textTransform: 'uppercase', marginBottom: 8 }}>
                Excluded Providers ({excludedRoutes.length})
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {excludedRoutes.map((ex) => (
                  <div
                    key={ex.provider_code}
                    style={{
                      padding: '8px 14px',
                      background: '#FFF5F5',
                      border: '1px solid #FECACA',
                      borderRadius: 6,
                      fontSize: '0.82rem',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                    }}
                  >
                    <span style={{ fontWeight: 600, color: '#991B1B' }}>{ex.display_name}</span>
                    <span style={{ color: '#7F1D1D', fontSize: '0.75rem' }}>
                      {ex.exclusion_reasons.join(', ')}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* AI Advisor Panel */}
          {analysis.ai_recommendation && (
            <div className={`ai-recommendation ${analysis.ai_recommendation.fallback_used ? 'ai-fallback' : ''}`}>
              <div className="ai-title">
                <Cpu size={18} color="#6D28D9" />
                <span>{analysis.ai_recommendation.model_name} Advisory</span>
                {analysis.ai_recommendation.fallback_used ? (
                  <span className="status-badge status-hold">Deterministic Fallback</span>
                ) : (
                  <span className="status-badge status-ready">AI Synthesized</span>
                )}
              </div>

              <div className="ai-summary" style={{ fontWeight: 500, color: '#1E293B' }}>
                {analysis.ai_recommendation.summary}
              </div>

              {analysis.ai_recommendation.recommended_route && (
                <div className="ai-recommendation-box">
                  <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#6D28D9', textTransform: 'uppercase' }}>
                    Recommended Settlement Rail
                  </div>
                  <div style={{ fontSize: '1.05rem', fontWeight: 800, color: '#003087', marginTop: 2 }}>
                    {analysis.ai_recommendation.recommended_route}
                  </div>
                </div>
              )}

              {analysis.ai_recommendation.reasoning_factors && analysis.ai_recommendation.reasoning_factors.length > 0 && (
                <div>
                  <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#64748B', textTransform: 'uppercase', marginBottom: 4 }}>
                    Key Decision Factors:
                  </div>
                  <ul className="ai-factors">
                    {analysis.ai_recommendation.reasoning_factors.map((f: string, i: number) => (
                      <li key={i}>{f}</li>
                    ))}
                  </ul>
                </div>
              )}

              <p className="ai-disclaimer" style={{ color: '#64748B' }}>
                Advisory only. Artificial intelligence cannot execute, approve, or bypass deterministic financial controls.
              </p>
            </div>
          )}
        </div>
      )}
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
  const [approverId, setApproverId] = useState('DEMO-APPROVER-001')
  const [strategy, setStrategy] = useState<'LOWEST_COST' | 'FASTEST' | 'BALANCED'>('LOWEST_COST')
  const [selectedProvider, setSelectedProvider] = useState<string>('')
  const [confirmed, setConfirmed] = useState(false)

  const eligibleRoutes: ProviderRoute[] = useMemo(
    () => (analysis?.provider_routes ?? []).filter((r) => r.eligible),
    [analysis]
  )

  const primaryCurrency = Object.keys(analysis?.total_amount_by_currency ?? {})[0] ?? 'USD'
  const primaryAmount = analysis?.total_amount_by_currency[primaryCurrency] ?? '0.00'

  const mutation = useMutation({
    mutationFn: () => {
      const payload: ApproveRequest = {
        approver_id: approverId,
        selected_provider: selectedProvider || eligibleRoutes[0]?.provider_code || 'PAYPAL_PAYOUTS',
        routing_strategy: strategy,
        confirmed_total: primaryAmount,
        confirmed_currency: primaryCurrency,
      }
      return approveBatch(batchId, payload)
    },
    onSuccess: onApproved,
  })

  // Default provider selection
  if (eligibleRoutes.length > 0 && !selectedProvider) {
    setSelectedProvider(eligibleRoutes[0].provider_code)
  }

  const canApprove =
    !!analysis &&
    eligibleRoutes.length > 0 &&
    !!selectedProvider &&
    confirmed &&
    !mutation.isPending &&
    batch.status !== 'APPROVED' &&
    batch.status !== 'SUBMITTED'

  if (!analysis || eligibleRoutes.length === 0) {
    return (
      <div className="panel">
        <h3 className="panel-title">Dual-Control Approval (Maker-Checker)</h3>
        <div className="alert alert-info">
          ⓘ Execute financial route analysis above before initiating maker-checker approval.
        </div>
      </div>
    )
  }

  if (batch.status === 'APPROVED') {
    return (
      <div className="panel">
        <h3 className="panel-title">Dual-Control Approval (Maker-Checker)</h3>
        <div className="alert alert-success">
          ✓ Batch authorized by <strong>{batch.approved_by}</strong> at{' '}
          {batch.approved_at ? new Date(batch.approved_at).toLocaleString() : '—'}.
        </div>
      </div>
    )
  }

  return (
    <div className="panel">
      <div className="panel-title">
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <ShieldCheck size={20} color="#007934" />
          <span>Authorize Batch for PayPal Submission</span>
        </div>
      </div>

      <div className="alert alert-warning">
        ⚠ Dual-control authorization permits submission to PayPal Sandbox. No real funds move.
      </div>

      <div className="form-grid">
        <div className="form-row">
          <label className="form-label">Approver Identity (Checker)</label>
          <input
            className="form-input"
            value={approverId}
            onChange={(e) => setApproverId(e.target.value)}
            placeholder="e.g. DEMO-APPROVER-001"
          />
        </div>

        <div className="form-row">
          <label className="form-label">Selected Strategy</label>
          <select
            className="select"
            value={strategy}
            onChange={(e) => setStrategy(e.target.value as any)}
          >
            <option value="LOWEST_COST">Lowest Cost</option>
            <option value="FASTEST">Fastest</option>
            <option value="BALANCED">Balanced</option>
          </select>
        </div>

        <div className="form-row">
          <label className="form-label">Approved Settlement Rail</label>
          <select
            className="select"
            value={selectedProvider}
            onChange={(e) => setSelectedProvider(e.target.value)}
          >
            {eligibleRoutes.map((r: ProviderRoute) => (
              <option key={r.provider_code} value={r.provider_code}>
                {r.display_name} ({r.environment})
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="approval-summary" style={{ background: '#ECFDF5', border: '1px solid #A7F3D0', borderRadius: 8, padding: 14 }}>
        <strong>Authorizing:</strong> {batch.obligation_count} obligations totaling{' '}
        <strong>{formatAmount(primaryAmount, primaryCurrency)} {primaryCurrency}</strong>
      </div>

      <div style={{ margin: '16px 0' }}>
        <label className="checkbox-label" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <input
            type="checkbox"
            checked={confirmed}
            onChange={(e) => setConfirmed(e.target.checked)}
            style={{ width: 18, height: 18, accentColor: '#0070BA' }}
          />
          <span style={{ fontWeight: 600, color: '#0F172A' }}>
            I confirm financial parameters and authorize submission to PayPal Sandbox Payouts.
          </span>
        </label>
      </div>

      {mutation.isError && (
        <div className="alert alert-error">
          Approval failed: {formatErrorMessage(mutation.error)}
        </div>
      )}

      <button
        className="btn btn-paypal-blue"
        onClick={() => mutation.mutate()}
        disabled={!canApprove}
        style={{ padding: '10px 24px', fontSize: '0.95rem' }}
      >
        {mutation.isPending ? 'Authorizing…' : 'Approve for Sandbox Submission'}
      </button>
    </div>
  )
}

// -------------------------------------------------------------------------
// PayPal execution panel with Signature PayPal Gold Button
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

      <div className="panel-title">
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          {/* Official PayPal Monogram Logo */}
          <svg style={{ width: 22, height: 26 }} viewBox="0 0 36 42" fill="none">
            <path
              d="M9.74 36.57L13.85 10.52C14.14 8.7 15.68 7.37 17.53 7.37H26.36C31.6 7.37 35.22 10.78 34.49 16.28C33.78 21.64 29.27 24.82 24.03 24.82H19.75L17.93 36.33C17.8 37.15 17.09 37.75 16.26 37.75H10.97C10.04 37.75 9.6 36.9 9.74 36.57Z"
              fill="#003087"
            />
            <path
              d="M4.38 34.32L8.49 8.27C8.78 6.45 10.32 5.12 12.17 5.12H21C26.24 5.12 29.86 8.53 29.13 14.03C28.42 19.39 23.91 22.57 18.67 22.57H14.39L12.57 34.08C12.44 34.9 11.73 35.5 10.9 35.5H5.61C4.68 35.5 4.24 34.65 4.38 34.32Z"
              fill="#0070BA"
            />
            <path
              d="M14.39 22.57H18.67C23.91 22.57 28.42 19.39 29.13 14.03C29.24 13.23 29.24 12.48 29.13 11.77C28.05 15.56 24.44 18.42 19.75 18.42H15.47L13.85 28.68L14.39 22.57Z"
              fill="#001C64"
            />
          </svg>
          <span>PayPal Sandbox Execution</span>
        </div>
      </div>

      <div className="execution-actions" style={{ marginBottom: 20 }}>
        {batch.status === 'APPROVED' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {/* Signature PayPal Gold Button */}
            <button
              className="btn btn-paypal-gold"
              onClick={() => submitMutation.mutate()}
              disabled={!canSubmit}
              style={{
                fontSize: '1rem',
                padding: '12px 28px',
                minWidth: 260,
                display: 'inline-flex',
                alignItems: 'center',
                gap: 10,
              }}
            >
              <svg style={{ width: 18, height: 22 }} viewBox="0 0 36 42" fill="none">
                <path
                  d="M4.38 34.32L8.49 8.27C8.78 6.45 10.32 5.12 12.17 5.12H21C26.24 5.12 29.86 8.53 29.13 14.03C28.42 19.39 23.91 22.57 18.67 22.57H14.39L12.57 34.08C12.44 34.9 11.73 35.5 10.9 35.5H5.61C4.68 35.5 4.24 34.65 4.38 34.32Z"
                  fill="#003087"
                />
              </svg>
              <span>{submitMutation.isPending ? 'Transmitting to PayPal…' : 'Submit to PayPal Payouts'}</span>
            </button>
            <p style={{ fontSize: '0.78rem', color: '#64748B' }}>
              Transmits payout items directly to PayPal Sandbox Payouts API v1.
            </p>
          </div>
        )}

        {canRefresh && (
          <button
            className="btn btn-secondary"
            onClick={() => refreshMutation.mutate()}
            disabled={!canRefresh}
          >
            {refreshMutation.isPending ? 'Querying PayPal…' : '↺ Refresh Settlement Status'}
          </button>
        )}
      </div>

      {/* Submit outcome */}
      {submitResult && (
        <div className={`alert ${submitResult.success ? 'alert-success' : 'alert-error'}`}>
          {submitResult.success ? (
            <>
              ✓ Batch successfully submitted.{' '}
              {submitResult.paypal_configured ? (
                <>
                  PayPal Payout Batch ID: <code>{submitResult.paypal_payout_batch_id}</code>
                </>
              ) : (
                <span className="badge badge-warning">SIMULATED — PayPal test mode</span>
              )}
            </>
          ) : (
            <div>
              <p>
                <strong>
                  {submitResult.error_message?.includes('country') || submitResult.error_message?.includes('PAYOUT_NOT_AVAILABLE')
                    ? 'BLOCKED — PAYPAL COUNTRY ELIGIBILITY'
                    : '✗ Submission failed:'}
                </strong>{' '}
                {submitResult.error_message}
              </p>
              {submitResult.error_message?.includes('PAYOUT_NOT_AVAILABLE') && (
                <p className="text-muted" style={{ fontSize: '0.82rem', marginTop: '0.4rem' }}>
                  ℹ <strong>Why did this happen?</strong> PayPal Sandbox requires sender accounts to reside in
                  a Payouts-eligible country. Indian PayPal accounts currently support receive/withdraw only.
                  Retrying will not resolve account country eligibility; the audit trail records this provider outcome.
                </p>
              )}
            </div>
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
        <div className="route-section" style={{ marginTop: 20 }}>
          <h4 className="route-section-title">Settlement Instructions ({instructions.length})</h4>
          <div className="table-wrapper">
            <table className="obligations-table small">
              <thead>
                <tr>
                  <th>Obligation</th>
                  <th>Provider</th>
                  <th className="col-amount">Amount</th>
                  <th>Ccy</th>
                  <th>Status</th>
                  <th>Settlement Evidence</th>
                  <th>PayPal Item ID</th>
                  <th>Txn ID</th>
                  <th>Outcome / Error</th>
                </tr>
              </thead>
              <tbody>
                {instructions.map((instr) => (
                  <tr key={instr.id}>
                    <td><code style={{ fontSize: '0.75rem' }}>{instr.obligation_id.slice(-8)}</code></td>
                    <td>{instr.provider_code}</td>
                    <td className="col-amount">{formatAmount(instr.amount, instr.currency)}</td>
                    <td><span className="currency-code">{instr.currency}</span></td>
                    <td><StatusPill status={instr.status} /></td>
                    <td>
                      <span className={`status-badge ${instr.settlement_evidence === 'PROVIDER_REPORTED_COMPLETE' ? 'status-completed' : 'status-hold'}`}>
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
// Audit log with Elastic-inspired Search Filter
// -------------------------------------------------------------------------

function AuditLog({ batchId }: { batchId: string }) {
  const [searchTerm, setSearchTerm] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['audit', batchId],
    queryFn: () => fetchAuditEvents(batchId),
    refetchInterval: 10000,
  })

  const filteredEvents = useMemo(() => {
    if (!data) return []
    if (!searchTerm.trim()) return data
    const q = searchTerm.toLowerCase()
    return data.filter(
      (ev) =>
        ev.event_type.toLowerCase().includes(q) ||
        ev.actor.toLowerCase().includes(q) ||
        (ev.details_redacted && ev.details_redacted.toLowerCase().includes(q))
    )
  }, [data, searchTerm])

  if (isLoading) return <div className="loading-state">Loading audit events…</div>
  if (!data || data.length === 0) return null

  return (
    <div className="panel">
      <div className="panel-title">
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <Lock size={18} color="#003087" />
          <span>Immutable Audit Log</span>
          <span style={{ fontSize: '0.72rem', color: '#64748B', fontWeight: 500 }}>
            Powered by Elastic Search Pattern • {data.length} recorded events
          </span>
        </div>

        {/* Elastic quick search */}
        <div style={{ position: 'relative', width: 240 }}>
          <Search size={14} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: '#94A3B8' }} />
          <input
            type="text"
            className="form-input"
            style={{ padding: '6px 10px 6px 30px', fontSize: '0.78rem', borderRadius: 999 }}
            placeholder="Search events, actors..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
      </div>

      <div className="table-wrapper">
        <table className="obligations-table small">
          <thead>
            <tr>
              <th>Timestamp</th>
              <th>Event Type</th>
              <th>Actor</th>
              <th>State Transition Details</th>
            </tr>
          </thead>
          <tbody>
            {filteredEvents.map((ev) => (
              <tr key={ev.id}>
                <td style={{ whiteSpace: 'nowrap', color: '#64748B' }}>
                  {new Date(ev.created_at).toLocaleString()}
                </td>
                <td>
                  <span className="status-badge status-ready" style={{ fontSize: '0.72rem' }}>
                    {ev.event_type}
                  </span>
                </td>
                <td><strong>{ev.actor}</strong></td>
                <td>
                  {ev.details_redacted && (
                    <details>
                      <summary style={{ cursor: 'pointer', color: '#0070BA', fontSize: '0.75rem', fontWeight: 600 }}>
                        Inspect Audit Payload
                      </summary>
                      <pre style={{ fontSize: '0.72rem', background: '#F8FAFC', padding: 8, borderRadius: 6, border: '1px solid #E2E8F0', marginTop: 4, maxWidth: 450, overflow: 'auto' }}>
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
          <div className="breadcrumb" style={{ marginBottom: 8 }}>
            <button className="btn-link" onClick={onBack}>← Back to Batches</button>
          </div>
          <h1 className="page-title" style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span>{batch.batch_reference}</span>
            <StatusPill status={batch.status} />
          </h1>
          <div className="batch-meta-row" style={{ marginTop: 6 }}>
            <span className="text-muted">{batch.obligation_count} obligation{batch.obligation_count !== 1 ? 's' : ''}</span>
            <span className="text-muted">•</span>
            <span className="text-muted">Created {new Date(batch.created_at).toLocaleDateString()}</span>
            <span className="text-muted">•</span>
            <code className="batch-id-display" style={{ margin: 0 }}>UUID: {batch.id}</code>
          </div>
        </div>
      </div>

      {/* Bryntum Lifecycle Stepper */}
      <LifecycleStepper status={batch.status} hasAnalysis={!!analysis} />

      {/* Route Analysis Panel */}
      <AnalysisPanel
        batchId={batchId}
        analysis={analysis}
        onAnalysed={(a) => {
          setAnalysis(a)
          queryClient.invalidateQueries({ queryKey: ['batch', batchId] })
        }}
      />

      {/* Maker-Checker Approval Panel */}
      {showApproval && (
        <ApprovalPanel
          batchId={batchId}
          analysis={analysis}
          batch={batch}
          onApproved={() => queryClient.invalidateQueries({ queryKey: ['batch', batchId] })}
        />
      )}

      {/* PayPal Execution Panel */}
      {showExecution && (
        <ExecutionPanel batchId={batchId} batch={batch} />
      )}

      {/* Audit Log */}
      <AuditLog batchId={batchId} />
    </div>
  )
}
