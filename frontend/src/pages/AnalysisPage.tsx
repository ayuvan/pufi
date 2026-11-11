import { useState, useEffect, useMemo } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import {
  fetchBatches,
  fetchBatchAnalysis,
  type BatchAnalysis,
  type ProviderRoute,
} from '../api/client'
import { PageHeader } from '../components/layout/PageHeader'
import { StatusBadge } from '../components/common/StatusBadge'
import { ErrorState } from '../components/common/ErrorState'
import { SkeletonBox } from '../components/common/LoadingSkeleton'
import {
  ComparativeRouteBarChart,
  type RouteBarItem,
} from '../components/common/FinancialChart'
import {
  Sparkles,
  Zap,
  TrendingDown,
  Layers,
  CheckCircle2,
  Info,
} from 'lucide-react'

type Strategy = 'LOWEST_COST' | 'FASTEST' | 'BALANCED'

function formatMoney(val: string | null | undefined, currency: string = 'USD'): string {
  if (val == null) return '—'
  const num = parseFloat(val)
  if (isNaN(num)) return `${val} ${currency}`
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: currency || 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(num)
}

export default function AnalysisPage() {
  const [selectedBatchId, setSelectedBatchId] = useState<string>('')
  const [strategy, setStrategy] = useState<Strategy>('LOWEST_COST')

  // Fetch batches for selector
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

  // Run analysis mutation
  const analysisMutation = useMutation({
    mutationFn: (vars: { id: string; strat: Strategy }) =>
      fetchBatchAnalysis(vars.id, vars.strat),
  })

  // Automatically analyze when batch or strategy changes
  useEffect(() => {
    if (selectedBatchId) {
      analysisMutation.mutate({ id: selectedBatchId, strat: strategy })
    }
  }, [selectedBatchId, strategy])

  const analysis: BatchAnalysis | undefined = analysisMutation.data

  // Prepare chart comparison data
  const comparisonItems: RouteBarItem[] = useMemo(() => {
    if (!analysis?.provider_routes) return []
    return analysis.provider_routes.map((r: ProviderRoute) => ({
      name: r.display_name,
      cost: parseFloat(r.total_estimated_cost || '0'),
      fee: parseFloat(r.provider_fee || '0'),
      speedHours: r.estimated_processing_hours || 24,
      eligible: r.eligible,
      isRecommended: analysis.ai_recommendation?.recommended_route === r.provider_code,
    }))
  }, [analysis])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      {/* Header */}
      <PageHeader
        title="Multi-Provider Route Analysis"
        subtitle="Intelligent financial routing combining deterministic provider eligibility, real-time FX evaluation, and Gemini AI advisory recommendations."
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
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
            }}
          >
            <Sparkles size={13} />
            Gemini Advisory Active
          </span>
        }
      />

      {/* Control Strip: Batch Selector & Strategy */}
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
        {/* Batch Select */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, flex: 1, minWidth: 280 }}>
          <Layers size={18} color="var(--pufi-primary)" />
          <div style={{ flex: 1 }}>
            <label style={{ display: 'block', fontSize: '0.74rem', color: 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase' }}>
              Select Active Batch
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
                  {b.batch_reference} ({b.obligation_count} obligations • {b.status})
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Strategy Selector Tabs */}
        <div>
          <label style={{ display: 'block', fontSize: '0.74rem', color: 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase', marginBottom: 6 }}>
            Routing Policy Objective
          </label>
          <div style={{ display: 'flex', gap: 6, background: 'var(--bg-subtle)', padding: 3, borderRadius: 'var(--radius-md)' }}>
            {(
              [
                { id: 'LOWEST_COST', label: 'Lowest Cost', icon: <TrendingDown size={14} /> },
                { id: 'FASTEST', label: 'Fastest Settlement', icon: <Zap size={14} /> },
                { id: 'BALANCED', label: 'Balanced Policy', icon: <Sparkles size={14} /> },
              ] as const
            ).map((s) => (
              <button
                key={s.id}
                onClick={() => setStrategy(s.id)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                  padding: '6px 14px',
                  borderRadius: 'var(--radius-sm)',
                  border: 'none',
                  background: strategy === s.id ? 'var(--bg-surface)' : 'transparent',
                  color: strategy === s.id ? 'var(--pufi-primary)' : 'var(--text-secondary)',
                  fontSize: '0.78rem',
                  fontWeight: 700,
                  cursor: 'pointer',
                  boxShadow: strategy === s.id ? 'var(--shadow-xs)' : 'none',
                  transition: 'all var(--trans-fast)',
                }}
              >
                {s.icon}
                <span>{s.label}</span>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Loading state */}
      {analysisMutation.isPending && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
          <SkeletonBox height={120} />
          <SkeletonBox height={260} />
        </div>
      )}

      {/* Error state */}
      {analysisMutation.isError && (
        <ErrorState
          title="Analysis Execution Failed"
          message={(analysisMutation.error as { error?: { message?: string } })?.error?.message || 'Could not analyze routes for the selected batch.'}
          onRetry={() => selectedBatchId && analysisMutation.mutate({ id: selectedBatchId, strat: strategy })}
        />
      )}

      {/* Main Analysis Display */}
      {analysis && !analysisMutation.isPending && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
          {/* AI Recommendation Banner */}
          {analysis.ai_recommendation && (
            <div
              style={{
                background: analysis.ai_recommendation.fallback_used
                  ? 'var(--pufi-warning-bg)'
                  : 'linear-gradient(135deg, rgba(22, 119, 255, 0.08) 0%, rgba(0, 207, 222, 0.08) 100%)',
                border: `1px solid ${
                  analysis.ai_recommendation.fallback_used
                    ? 'var(--pufi-warning-border)'
                    : 'rgba(22, 119, 255, 0.25)'
                }`,
                borderRadius: 'var(--radius-lg)',
                padding: '24px 28px',
                boxShadow: 'var(--shadow-card)',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12, marginBottom: 12 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <div
                    style={{
                      width: 36,
                      height: 36,
                      borderRadius: 'var(--radius-md)',
                      background: 'var(--pufi-primary)',
                      color: '#FFFFFF',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                  >
                    <Sparkles size={18} />
                  </div>
                  <div>
                    <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 800, color: 'var(--text-primary)' }}>
                      AI Routing Advisory: {analysis.ai_recommendation.recommended_route || 'Deterministic Selection'}
                    </h3>
                    <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)', marginTop: 2 }}>
                      Model: <strong>{analysis.ai_recommendation.model_name}</strong> • Strategy: {analysis.routing_strategy}
                    </div>
                  </div>
                </div>

                {analysis.ai_recommendation.fallback_used && (
                  <span
                    style={{
                      background: 'var(--pufi-warning-bg)',
                      color: 'var(--pufi-warning-text)',
                      border: '1px solid var(--pufi-warning-border)',
                      padding: '4px 10px',
                      borderRadius: 'var(--radius-pill)',
                      fontSize: '0.74rem',
                      fontWeight: 700,
                    }}
                  >
                    Deterministic Fallback Used
                  </span>
                )}
              </div>

              <p style={{ margin: '0 0 16px 0', fontSize: '0.88rem', color: 'var(--text-primary)', lineHeight: 1.55 }}>
                {analysis.ai_recommendation.summary}
              </p>

              {/* Reasoning factors pills */}
              {analysis.ai_recommendation.reasoning_factors?.length > 0 && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 14 }}>
                  <span style={{ fontSize: '0.74rem', color: 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase' }}>
                    Reasoning Factors Considered:
                  </span>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                    {analysis.ai_recommendation.reasoning_factors.map((f, i) => (
                      <span
                        key={i}
                        style={{
                          background: 'var(--bg-surface)',
                          border: '1px solid var(--border-base)',
                          padding: '3px 10px',
                          borderRadius: 'var(--radius-pill)',
                          fontSize: '0.76rem',
                          color: 'var(--text-secondary)',
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: 6,
                        }}
                      >
                        <CheckCircle2 size={12} color="var(--pufi-success)" />
                        <span>{f}</span>
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Disclaimer */}
              <div
                style={{
                  paddingTop: 12,
                  borderTop: '1px solid rgba(0,0,0,0.06)',
                  fontSize: '0.72rem',
                  color: 'var(--text-muted)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                }}
              >
                <Info size={13} />
                <span>
                  <strong>Advisory Guardrail:</strong> AI recommendations are advisory and require explicit human Maker-Checker approval. They never execute payment transfers.
                </span>
              </div>
            </div>
          )}

          {/* Comparative Route Cost Bar Chart */}
          <div
            style={{
              background: 'var(--bg-surface)',
              border: '1px solid var(--border-base)',
              borderRadius: 'var(--radius-lg)',
              padding: '24px 28px',
              boxShadow: 'var(--shadow-card)',
            }}
          >
            <div style={{ marginBottom: 18 }}>
              <h3 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 750, color: 'var(--text-primary)' }}>
                Cost & Execution Comparison
              </h3>
              <p style={{ margin: '4px 0 0 0', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                Relative estimated commitment and processing hours across candidate rails
              </p>
            </div>

            <ComparativeRouteBarChart items={comparisonItems} currency="USD" />
          </div>

          {/* Detailed Provider Route Cards */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 20 }}>
            {analysis.provider_routes.map((route: ProviderRoute) => {
              const isRecommended = analysis.ai_recommendation?.recommended_route === route.provider_code

              return (
                <div
                  key={route.provider_code}
                  style={{
                    background: 'var(--bg-surface)',
                    border: `1px solid ${
                      isRecommended
                        ? 'var(--pufi-primary)'
                        : route.eligible
                        ? 'var(--border-base)'
                        : 'var(--border-subtle)'
                    }`,
                    borderRadius: 'var(--radius-lg)',
                    padding: 24,
                    boxShadow: isRecommended ? 'var(--shadow-card-hover)' : 'var(--shadow-card)',
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'space-between',
                    opacity: route.eligible ? 1 : 0.6,
                    position: 'relative',
                  }}
                >
                  {isRecommended && (
                    <div
                      style={{
                        position: 'absolute',
                        top: 14,
                        right: 16,
                        background: 'var(--pufi-primary)',
                        color: '#FFFFFF',
                        fontSize: '0.68rem',
                        fontWeight: 800,
                        padding: '2px 8px',
                        borderRadius: 'var(--radius-pill)',
                        letterSpacing: '0.04em',
                      }}
                    >
                      ★ RECOMMENDED
                    </div>
                  )}

                  <div>
                    {/* Header */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                      <h4 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 800, color: 'var(--text-primary)' }}>
                        {route.display_name}
                      </h4>
                    </div>
                    <div style={{ display: 'flex', gap: 6, marginBottom: 16 }}>
                      <StatusBadge status={route.environment} size="sm" />
                      <StatusBadge status={route.eligible ? 'ELIGIBLE' : 'EXCLUDED'} size="sm" />
                    </div>

                    {/* Financial Figures */}
                    {route.eligible ? (
                      <div
                        style={{
                          background: 'var(--bg-subtle)',
                          borderRadius: 'var(--radius-md)',
                          padding: 14,
                          display: 'flex',
                          flexDirection: 'column',
                          gap: 8,
                          marginBottom: 16,
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                          <span style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>Total Cost:</span>
                          <strong className="num-tabular" style={{ fontSize: '1.05rem', color: 'var(--text-primary)' }}>
                            {formatMoney(route.total_estimated_cost, 'USD')}
                          </strong>
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                          <span style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>Provider Fee:</span>
                          <span className="num-tabular" style={{ fontSize: '0.84rem' }}>
                            {formatMoney(route.provider_fee, 'USD')}
                          </span>
                        </div>
                        {route.fx_spread_cost && route.fx_spread_cost !== '0.00' && (
                          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                            <span style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>FX Spread Cost:</span>
                            <span className="num-tabular" style={{ fontSize: '0.84rem' }}>
                              {formatMoney(route.fx_spread_cost, 'USD')}
                            </span>
                          </div>
                        )}
                        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                          <span style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>Speed:</span>
                          <span style={{ fontSize: '0.84rem', fontWeight: 650 }}>
                            ~{route.estimated_processing_hours} hours
                          </span>
                        </div>
                      </div>
                    ) : (
                      <div
                        style={{
                          padding: 14,
                          background: 'var(--pufi-danger-bg)',
                          borderRadius: 'var(--radius-md)',
                          marginBottom: 16,
                        }}
                      >
                        <div style={{ fontSize: '0.78rem', fontWeight: 700, color: 'var(--pufi-danger-text)', marginBottom: 4 }}>
                          Exclusion Reasons:
                        </div>
                        <ul style={{ margin: 0, paddingLeft: 18, fontSize: '0.76rem', color: 'var(--pufi-danger-text)' }}>
                          {route.exclusion_reasons.map((r, i) => (
                            <li key={i}>{r}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>

                  {/* Quote expiry */}
                  <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', paddingTop: 10, borderTop: '1px solid var(--border-subtle)' }}>
                    Quote: {route.quote_label} • {route.quote_source}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
