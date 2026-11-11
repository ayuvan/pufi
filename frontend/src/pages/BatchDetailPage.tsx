import { useState, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  fetchBatch,
  fetchBatchAnalysis,
  approveBatch,
  submitBatch,
  refreshBatchStatus,
  fetchInstructions,
  fetchAuditEvents,
  type BatchAnalysis,
  type ProviderRoute,
  type ApproveRequest,
  type PaymentInstructionOut,
  type AuditEventOut,
} from '../api/client'
import { PageHeader } from '../components/layout/PageHeader'
import { StatusBadge } from '../components/common/StatusBadge'
import { ErrorState } from '../components/common/ErrorState'
import { SkeletonBox } from '../components/common/LoadingSkeleton'
import {
  ArrowLeft,
  CheckCircle2,
  Cpu,
  ShieldCheck,
  RefreshCw,
  Clock,
  Sparkles,
  Lock,
  Send,
} from 'lucide-react'

interface BatchDetailPageProps {
  batchId: string
  onBack: () => void
}

function formatAmount(amount: string | null | undefined, currency: string = 'USD'): string {
  if (amount == null) return '—'
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

// ---------------------------------------------------------------------------
// 1. Bryntum-inspired Lifecycle Stepper
// ---------------------------------------------------------------------------

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
    <div
      style={{
        background: 'var(--bg-surface)',
        border: '1px solid var(--border-base)',
        borderRadius: 'var(--radius-lg)',
        padding: '24px 28px',
        boxShadow: 'var(--shadow-card)',
        position: 'relative',
      }}
    >
      <div style={{ position: 'relative', margin: '14px 10px' }}>
        {/* Track Line */}
        <div
          style={{
            position: 'absolute',
            top: 15,
            left: 0,
            right: 0,
            height: 3,
            background: 'var(--bg-subtle)',
            borderRadius: 2,
          }}
        />
        {/* Progress Line */}
        <div
          style={{
            position: 'absolute',
            top: 15,
            left: 0,
            width: `${progressPct}%`,
            height: 3,
            background: 'var(--pufi-primary)',
            borderRadius: 2,
            transition: 'width 0.4s var(--ease-spring)',
          }}
        />

        {/* Step Circles */}
        <div style={{ display: 'flex', justifyContent: 'space-between', position: 'relative' }}>
          {steps.map((s, idx) => {
            const isDone = idx < currentIndex
            const isActive = idx === currentIndex

            return (
              <div
                key={s.key}
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: 8,
                  zIndex: 2,
                }}
              >
                <div
                  style={{
                    width: 32,
                    height: 32,
                    borderRadius: '50%',
                    background: isDone
                      ? 'var(--pufi-success)'
                      : isActive
                      ? 'var(--pufi-primary)'
                      : 'var(--bg-surface)',
                    border: `2px solid ${
                      isDone
                        ? 'var(--pufi-success)'
                        : isActive
                        ? 'var(--pufi-primary)'
                        : 'var(--border-strong)'
                    }`,
                    color: isDone || isActive ? '#FFFFFF' : 'var(--text-muted)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '0.82rem',
                    fontWeight: 750,
                    boxShadow: isActive ? '0 0 0 4px var(--pufi-primary-glow)' : 'none',
                    transition: 'all var(--trans-normal)',
                  }}
                >
                  {isDone ? <CheckCircle2 size={16} /> : idx + 1}
                </div>
                <span
                  style={{
                    fontSize: '0.74rem',
                    fontWeight: isActive ? 750 : 550,
                    color: isActive
                      ? 'var(--text-primary)'
                      : isDone
                      ? 'var(--pufi-success-text)'
                      : 'var(--text-muted)',
                    textAlign: 'center',
                    maxWidth: 120,
                  }}
                >
                  {s.label}
                </span>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export default function BatchDetailPage({ batchId, onBack }: BatchDetailPageProps) {
  const queryClient = useQueryClient()
  const [strategy, setStrategy] = useState<'LOWEST_COST' | 'FASTEST' | 'BALANCED'>('LOWEST_COST')
  const [approverId, setApproverId] = useState('USR-FIN-CONTROLLER')

  // 1. Fetch Batch
  const { data: batch, isLoading: isBatchLoading, isError: isBatchError, error: batchError } = useQuery({
    queryKey: ['batch', batchId],
    queryFn: () => fetchBatch(batchId),
  })

  // 2. Fetch Instructions
  const { data: instructions } = useQuery({
    queryKey: ['instructions', batchId],
    queryFn: () => fetchInstructions(batchId),
    enabled: !!batch,
  })

  // 3. Fetch Audit Events
  const { data: auditEvents } = useQuery({
    queryKey: ['audit', batchId],
    queryFn: () => fetchAuditEvents(batchId),
    enabled: !!batch,
  })

  // Analysis Mutation
  const [analysisResult, setAnalysisResult] = useState<BatchAnalysis | null>(null)
  const analyzeMutation = useMutation({
    mutationFn: () => fetchBatchAnalysis(batchId, strategy),
    onSuccess: (data) => {
      setAnalysisResult(data)
      queryClient.invalidateQueries({ queryKey: ['batch', batchId] })
    },
  })

  // Approve Mutation
  const approveMutation = useMutation({
    mutationFn: (req: ApproveRequest) => approveBatch(batchId, req),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['batch', batchId] })
      queryClient.invalidateQueries({ queryKey: ['audit', batchId] })
    },
  })

  // Submit Mutation
  const submitMutation = useMutation({
    mutationFn: () => submitBatch(batchId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['batch', batchId] })
      queryClient.invalidateQueries({ queryKey: ['instructions', batchId] })
      queryClient.invalidateQueries({ queryKey: ['audit', batchId] })
    },
  })

  // Status Refresh Mutation
  const refreshMutation = useMutation({
    mutationFn: () => refreshBatchStatus(batchId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['batch', batchId] })
      queryClient.invalidateQueries({ queryKey: ['instructions', batchId] })
      queryClient.invalidateQueries({ queryKey: ['audit', batchId] })
    },
  })

  // Compute total obligation sum for the approval payload
  const batchTotal = useMemo(() => {
    if (!batch?.obligations) return '0.00'
    return batch.obligations
      .reduce((sum, o) => sum + parseFloat(o.amount || '0'), 0)
      .toFixed(2)
  }, [batch])

  const batchCurrency = batch?.obligations?.[0]?.currency || 'USD'

  if (isBatchLoading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
        <SkeletonBox height={60} />
        <SkeletonBox height={140} />
        <SkeletonBox height={300} />
      </div>
    )
  }

  if (isBatchError || !batch) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <button onClick={onBack} style={{ display: 'flex', alignItems: 'center', gap: 6, background: 'none', border: 'none', color: 'var(--pufi-primary)', cursor: 'pointer', fontWeight: 650 }}>
          <ArrowLeft size={16} /> Back to Batches
        </button>
        <ErrorState
          title="Payment Batch Not Found"
          message={(batchError as { error?: { message?: string } })?.error?.message || 'Unable to retrieve batch details.'}
          onRetry={() => onBack()}
        />
      </div>
    )
  }

  const isApproved = batch.status === 'APPROVED' || ['SUBMITTED', 'PROCESSING', 'COMPLETED'].includes(batch.status)
  const isSubmitted = ['SUBMITTED', 'PROCESSING', 'COMPLETED', 'PARTIALLY_COMPLETED'].includes(batch.status)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      {/* Back button & Title */}
      <div>
        <button
          onClick={onBack}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 6,
            background: 'none',
            border: 'none',
            color: 'var(--pufi-primary)',
            fontSize: '0.82rem',
            fontWeight: 700,
            cursor: 'pointer',
            padding: 0,
            marginBottom: 12,
          }}
        >
          <ArrowLeft size={15} />
          <span>Back to Batches Explorer</span>
        </button>

        <PageHeader
          title={`Batch: ${batch.batch_reference}`}
          subtitle={`Internal UUID: ${batch.id} • Created ${new Date(batch.created_at).toLocaleString()}`}
          badge={<StatusBadge status={batch.status} size="lg" />}
          actions={
            <div style={{ display: 'flex', gap: 10 }}>
              {isSubmitted && (
                <button
                  onClick={() => refreshMutation.mutate()}
                  disabled={refreshMutation.isPending}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 6,
                    padding: '8px 16px',
                    borderRadius: 'var(--radius-md)',
                    background: 'var(--bg-surface)',
                    border: '1px solid var(--border-base)',
                    color: 'var(--text-primary)',
                    fontSize: '0.82rem',
                    fontWeight: 650,
                    cursor: 'pointer',
                  }}
                >
                  <RefreshCw size={14} className={refreshMutation.isPending ? 'animate-spin' : ''} />
                  <span>Refresh PayPal Status</span>
                </button>
              )}
            </div>
          }
        />
      </div>

      {/* Bryntum Lifecycle Stepper */}
      <LifecycleStepper status={batch.status} hasAnalysis={!!analysisResult} />

      {/* Main Execution Panels Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(460px, 1fr))', gap: 24 }}>
        {/* Step 2: Route Analysis Panel */}
        <div
          style={{
            background: 'var(--bg-surface)',
            border: '1px solid var(--border-base)',
            borderRadius: 'var(--radius-lg)',
            padding: 24,
            boxShadow: 'var(--shadow-card)',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
          }}
        >
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <Cpu size={18} color="var(--pufi-primary)" />
                <h3 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 750, color: 'var(--text-primary)' }}>
                  Multi-Provider Route Analysis
                </h3>
              </div>
              <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontWeight: 600 }}>
                Gemini AI + Deterministic
              </span>
            </div>

            <p style={{ margin: '0 0 16px 0', fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
              Evaluate provider cost, fee spreads, and routing eligibility across PayPal Sandbox and simulated alternatives.
            </p>

            {/* Strategy Selector */}
            <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
              {(['LOWEST_COST', 'FASTEST', 'BALANCED'] as const).map((s) => (
                <button
                  key={s}
                  onClick={() => setStrategy(s)}
                  style={{
                    flex: 1,
                    padding: '7px 10px',
                    borderRadius: 'var(--radius-sm)',
                    border: `1px solid ${strategy === s ? 'var(--pufi-primary)' : 'var(--border-base)'}`,
                    background: strategy === s ? 'var(--pufi-primary-light)' : 'var(--bg-subtle)',
                    color: strategy === s ? 'var(--pufi-primary)' : 'var(--text-secondary)',
                    fontSize: '0.76rem',
                    fontWeight: 700,
                    cursor: 'pointer',
                  }}
                >
                  {s.replace('_', ' ')}
                </button>
              ))}
            </div>

            {/* Analysis Result Display */}
            {analysisResult ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {analysisResult.ai_recommendation && (
                  <div
                    style={{
                      background: 'var(--bg-subtle)',
                      border: '1px solid var(--border-subtle)',
                      borderRadius: 'var(--radius-md)',
                      padding: 14,
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                      <Sparkles size={15} color="var(--pufi-primary)" />
                      <strong style={{ fontSize: '0.84rem', color: 'var(--pufi-primary)' }}>
                        AI Advisory Pick: {analysisResult.ai_recommendation.recommended_route || 'PAYPAL'}
                      </strong>
                    </div>
                    <p style={{ margin: '0 0 6px 0', fontSize: '0.8rem', color: 'var(--text-primary)' }}>
                      {analysisResult.ai_recommendation.summary}
                    </p>
                    <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                      Model: {analysisResult.ai_recommendation.model_name} • Advisory only (requires human approval)
                    </div>
                  </div>
                )}

                {/* Provider List */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {analysisResult.provider_routes.map((route: ProviderRoute) => (
                    <div
                      key={route.provider_code}
                      style={{
                        padding: '10px 14px',
                        borderRadius: 'var(--radius-md)',
                        background: route.eligible ? 'var(--bg-surface)' : 'var(--bg-subtle)',
                        border: `1px solid ${route.eligible ? 'var(--border-base)' : 'var(--border-subtle)'}`,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                      }}
                    >
                      <div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <strong style={{ fontSize: '0.86rem', color: 'var(--text-primary)' }}>
                            {route.display_name}
                          </strong>
                          <span style={{ fontSize: '0.68rem', fontWeight: 700, padding: '1px 6px', borderRadius: 4, background: route.is_simulated ? 'var(--pufi-warning-bg)' : 'var(--pufi-info-bg)', color: route.is_simulated ? 'var(--pufi-warning-text)' : 'var(--pufi-info-text)' }}>
                            {route.environment}
                          </span>
                        </div>
                        <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)', marginTop: 2 }}>
                          {route.eligible ? `Est. Fee: ${formatAmount(route.provider_fee, 'USD')} • ~${route.estimated_processing_hours}h` : route.exclusion_reasons.join(', ')}
                        </div>
                      </div>

                      <strong className="num-tabular" style={{ fontSize: '0.9rem', color: route.eligible ? 'var(--text-primary)' : 'var(--text-muted)' }}>
                        {route.eligible ? formatAmount(route.total_estimated_cost, 'USD') : 'Excluded'}
                      </strong>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div style={{ padding: '24px 0', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.82rem' }}>
                Run route evaluation to preview multi-provider fee breakdowns and AI advisory.
              </div>
            )}
          </div>

          <div style={{ marginTop: 20 }}>
            <button
              onClick={() => analyzeMutation.mutate()}
              disabled={analyzeMutation.isPending}
              style={{
                width: '100%',
                padding: '10px',
                borderRadius: 'var(--radius-md)',
                background: 'var(--pufi-primary)',
                border: 'none',
                color: '#FFFFFF',
                fontSize: '0.84rem',
                fontWeight: 650,
                cursor: analyzeMutation.isPending ? 'not-allowed' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 8,
              }}
            >
              <Cpu size={16} />
              <span>{analyzeMutation.isPending ? 'Running Route Analysis…' : 'Run Route Analysis'}</span>
            </button>
          </div>
        </div>

        {/* Step 3 & 4: Maker-Checker Approval & PayPal Submission */}
        <div
          style={{
            background: 'var(--bg-surface)',
            border: '1px solid var(--border-base)',
            borderRadius: 'var(--radius-lg)',
            padding: 24,
            boxShadow: 'var(--shadow-card)',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
          }}
        >
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
              <ShieldCheck size={18} color={isApproved ? 'var(--pufi-success)' : 'var(--pufi-primary)'} />
              <h3 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 750, color: 'var(--text-primary)' }}>
                Maker-Checker Authorization
              </h3>
            </div>

            <p style={{ margin: '0 0 16px 0', fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
              Dual-control validation requires explicit confirmation of total settlement liability before PayPal submission.
            </p>

            {/* Confirmed Figures Box */}
            <div
              style={{
                background: 'var(--bg-subtle)',
                borderRadius: 'var(--radius-md)',
                padding: '16px 18px',
                border: '1px solid var(--border-subtle)',
                marginBottom: 16,
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Confirmed Batch Total:</span>
                <strong className="num-tabular" style={{ fontSize: '1.15rem', color: 'var(--text-primary)' }}>
                  {formatAmount(batchTotal, batchCurrency)}
                </strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Selected Provider:</span>
                <span style={{ fontSize: '0.82rem', fontWeight: 700, color: '#003087' }}>PayPal Payouts (Sandbox)</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Authorization Status:</span>
                <StatusBadge status={isApproved ? 'APPROVED' : 'PENDING'} size="sm" />
              </div>
            </div>

            {/* Approver ID Input */}
            {!isApproved && (
              <div style={{ marginBottom: 16 }}>
                <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 700, marginBottom: 4, color: 'var(--text-primary)' }}>
                  Authorized Approver ID
                </label>
                <input
                  type="text"
                  value={approverId}
                  onChange={(e) => setApproverId(e.target.value)}
                  placeholder="e.g. USR-FIN-CONTROLLER"
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    borderRadius: 'var(--radius-sm)',
                    border: '1px solid var(--border-base)',
                    background: 'var(--bg-surface)',
                    fontSize: '0.84rem',
                    color: 'var(--text-primary)',
                    boxSizing: 'border-box',
                  }}
                />
              </div>
            )}
          </div>

          {/* Action Buttons: Approve vs Submit */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 20 }}>
            {!isApproved ? (
              <button
                onClick={() =>
                  approveMutation.mutate({
                    approver_id: approverId.trim() || 'USR-FIN-CONTROLLER',
                    routing_strategy: strategy,
                    selected_provider: 'PAYPAL',
                    confirmed_total: batchTotal,
                    confirmed_currency: batchCurrency,
                  })
                }
                disabled={approveMutation.isPending || !batchTotal}
                style={{
                  width: '100%',
                  padding: '11px',
                  borderRadius: 'var(--radius-md)',
                  background: 'var(--pufi-success)',
                  border: 'none',
                  color: '#FFFFFF',
                  fontSize: '0.86rem',
                  fontWeight: 700,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 8,
                }}
              >
                <Lock size={16} />
                <span>{approveMutation.isPending ? 'Signing Approval…' : 'Approve Batch (Maker-Checker)'}</span>
              </button>
            ) : !isSubmitted ? (
              <button
                onClick={() => submitMutation.mutate()}
                disabled={submitMutation.isPending}
                style={{
                  width: '100%',
                  padding: '12px',
                  borderRadius: 'var(--radius-md)',
                  background: 'var(--pp-gold)',
                  border: 'none',
                  color: 'var(--pp-navy)',
                  fontSize: '0.92rem',
                  fontWeight: 800,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 8,
                  boxShadow: 'var(--shadow-gold)',
                }}
              >
                <Send size={18} />
                <span>{submitMutation.isPending ? 'Transmitting to PayPal…' : 'Execute PayPal Sandbox Payout'}</span>
              </button>
            ) : (
              <div
                style={{
                  padding: '12px',
                  borderRadius: 'var(--radius-md)',
                  background: 'var(--pufi-success-bg)',
                  border: '1px solid var(--pufi-success-border)',
                  color: 'var(--pufi-success-text)',
                  fontSize: '0.84rem',
                  fontWeight: 700,
                  textAlign: 'center',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 8,
                }}
              >
                <CheckCircle2 size={16} />
                <span>Submitted to PayPal Payouts API</span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Itemized Payment Instructions Table */}
      <div
        style={{
          background: 'var(--bg-surface)',
          border: '1px solid var(--border-base)',
          borderRadius: 'var(--radius-lg)',
          padding: 24,
          boxShadow: 'var(--shadow-card)',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <div>
            <h3 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 750, color: 'var(--text-primary)' }}>
              Itemized Payment Instructions & Settlement
            </h3>
            <p style={{ margin: '4px 0 0 0', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
              Individual supplier payout items mapped to PayPal transactions and idempotency keys
            </p>
          </div>
          <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
            {instructions?.length || batch.obligations?.length || 0} instructions
          </span>
        </div>

        {instructions && instructions.length > 0 ? (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.82rem' }}>
              <thead>
                <tr style={{ background: 'var(--bg-subtle)', borderBottom: '1px solid var(--border-base)', color: 'var(--text-secondary)' }}>
                  <th style={{ padding: '10px 16px', fontWeight: 700 }}>Instruction Ref</th>
                  <th style={{ padding: '10px 16px', fontWeight: 700 }}>Provider</th>
                  <th style={{ padding: '10px 16px', fontWeight: 700, textAlign: 'right' }}>Amount</th>
                  <th style={{ padding: '10px 16px', fontWeight: 700 }}>Status</th>
                  <th style={{ padding: '10px 16px', fontWeight: 700 }}>PayPal Item ID</th>
                  <th style={{ padding: '10px 16px', fontWeight: 700 }}>Settlement Evidence</th>
                </tr>
              </thead>
              <tbody>
                {instructions.map((inst: PaymentInstructionOut) => (
                  <tr key={inst.id} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                    <td style={{ padding: '12px 16px' }}>
                      <code style={{ fontWeight: 700, color: 'var(--pufi-primary)' }}>{inst.sender_item_id}</code>
                    </td>
                    <td style={{ padding: '12px 16px' }}>{inst.provider_code}</td>
                    <td style={{ padding: '12px 16px', textAlign: 'right', fontWeight: 800 }}>
                      {formatAmount(inst.amount, inst.currency)}
                    </td>
                    <td style={{ padding: '12px 16px' }}>
                      <StatusBadge status={inst.status} size="sm" />
                    </td>
                    <td style={{ padding: '12px 16px' }}>
                      <code style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>
                        {inst.paypal_payout_item_id || 'Pending'}
                      </code>
                    </td>
                    <td style={{ padding: '12px 16px', fontSize: '0.76rem', color: 'var(--text-secondary)' }}>
                      {inst.settlement_evidence}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {batch.obligations.map((o) => (
              <div
                key={o.obligation_id}
                style={{
                  padding: '10px 14px',
                  borderRadius: 'var(--radius-sm)',
                  background: 'var(--bg-subtle)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                }}
              >
                <div>
                  <div style={{ fontWeight: 650, fontSize: '0.84rem' }}>{o.supplier_name}</div>
                  <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                    Inv: <code>{o.invoice_reference}</code>
                  </div>
                </div>
                <strong className="num-tabular" style={{ fontSize: '0.9rem' }}>
                  {formatAmount(o.amount, o.currency)}
                </strong>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Embedded Audit Events */}
      {auditEvents && auditEvents.length > 0 && (
        <div
          style={{
            background: 'var(--bg-surface)',
            border: '1px solid var(--border-base)',
            borderRadius: 'var(--radius-lg)',
            padding: 24,
            boxShadow: 'var(--shadow-card)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
            <Clock size={16} color="var(--pufi-primary)" />
            <h3 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 750, color: 'var(--text-primary)' }}>
              Batch Audit Trail Log
            </h3>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {auditEvents.map((ev: AuditEventOut) => (
              <div
                key={ev.id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '10px 14px',
                  borderRadius: 'var(--radius-sm)',
                  background: 'var(--bg-subtle)',
                  border: '1px solid var(--border-subtle)',
                  fontSize: '0.8rem',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <StatusBadge status={ev.event_type} size="sm" />
                  <span style={{ color: 'var(--text-secondary)' }}>
                    Actor: <strong>{ev.actor}</strong>
                  </span>
                </div>
                <span style={{ color: 'var(--text-muted)', fontSize: '0.74rem' }}>
                  {new Date(ev.created_at).toLocaleString()}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
