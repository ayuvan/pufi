/**
 * PUFI — Financial Analysis Page (Day 3)
 *
 * Shows deterministic provider routing analysis and AI advisory for a batch.
 *
 * DISCLAIMER labels:
 *   SIMULATED — synthetic rate / provider / estimate
 *   SANDBOX   — real PayPal Sandbox API, test accounts only
 *   AI ADVISORY — Gemini output, requires human approval
 */

import { useState } from 'react'
import {
  fetchBatchAnalysis,
  type BatchAnalysis,
  type ProviderRoute,
  type AiRecommendation,
} from '../api/client'

// ─── Helpers ──────────────────────────────────────────────────────────────

function fmtMoney(val: string | null | undefined, currency?: string | null): string {
  if (val == null) return '—'
  const num = parseFloat(val)
  if (isNaN(num)) return val
  return currency
    ? `${num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 4 })} ${currency}`
    : num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 4 })
}

function fmtRate(val: string | null | undefined): string {
  if (val == null) return '—'
  const num = parseFloat(val)
  return isNaN(num) ? val : num.toFixed(6)
}

type Strategy = 'LOWEST_COST' | 'FASTEST' | 'BALANCED'

// ─── Sub-components ───────────────────────────────────────────────────────

function EnvBadge({ env }: { env: string }) {
  const cls =
    env === 'SANDBOX'
      ? 'env-badge env-badge-sandbox'
      : env === 'SIMULATED'
      ? 'env-badge env-badge-simulated'
      : 'env-badge env-badge-unknown'
  return <span className={cls}>{env}</span>
}

function QuoteBadge({ label }: { label: string }) {
  const cls =
    label === 'SIMULATED'
      ? 'quote-badge quote-label-simulated'
      : label === 'LIVE'
      ? 'quote-badge quote-label-live'
      : 'quote-badge quote-label-na'
  return <span className={cls}>{label}</span>
}

function ProviderRow({ route, isRecommended }: { route: ProviderRoute; isRecommended: boolean }) {
  const rowCls = route.eligible
    ? `provider-row provider-row-eligible${isRecommended ? ' provider-row-recommended' : ''}`
    : 'provider-row provider-row-excluded'

  return (
    <tr className={rowCls}>
      <td>
        <div className="provider-name">
          {isRecommended && <span className="recommended-star" title="AI-recommended">★ </span>}
          <strong>{route.display_name}</strong>
        </div>
        <EnvBadge env={route.environment} />
      </td>
      <td className="text-center">
        {route.eligible ? (
          <span className="status-pill status-eligible">ELIGIBLE</span>
        ) : (
          <span className="status-pill status-excluded">EXCLUDED</span>
        )}
      </td>
      <td>
        {route.eligible ? (
          <>
            <div>{fmtMoney(route.provider_fee, route.recipient_currency ? undefined : 'src')}</div>
            {route.fx_spread_cost && route.fx_spread_cost !== '0.00' && (
              <div className="text-muted text-sm">FX spread: {fmtMoney(route.fx_spread_cost)}</div>
            )}
          </>
        ) : (
          <div className="exclusion-reasons">
            {route.exclusion_reasons.map((r) => (
              <span key={r} className="reason-code">{r}</span>
            ))}
          </div>
        )}
      </td>
      <td>
        {route.eligible ? (
          <div>
            <span className="cost-total">{fmtMoney(route.total_estimated_cost)}</span>
            <div className="text-muted text-sm">(source currency)</div>
          </div>
        ) : '—'}
      </td>
      <td>
        {route.eligible && route.estimated_recipient_amount ? (
          <div>
            {fmtMoney(route.estimated_recipient_amount, route.recipient_currency)}
            <div className="text-sm">
              {route.quote_rate && (
                <>
                  <QuoteBadge label={route.quote_label} />
                  {' '}{fmtRate(route.effective_rate)} eff. rate
                </>
              )}
            </div>
          </div>
        ) : '—'}
      </td>
      <td className="text-center">
        {route.eligible && route.estimated_processing_hours != null
          ? `~${route.estimated_processing_hours}h`
          : '—'}
      </td>
      <td>
        {route.warnings && route.warnings.length > 0 && (
          <ul className="warning-list">
            {route.warnings.map((w, i) => (
              <li key={i} className="warning-item">⚠ {w}</li>
            ))}
          </ul>
        )}
      </td>
    </tr>
  )
}

function AiPanel({ ai }: { ai: AiRecommendation }) {
  return (
    <section className={`ai-panel ${ai.fallback_used ? 'ai-fallback' : ''}`}>
      <div className="ai-panel-header">
        <span className="ai-label">🤖 AI Advisory</span>
        <span className="ai-badge">Gemini · {ai.model_name}</span>
        {ai.fallback_used && (
          <span className="ai-fallback-badge">FALLBACK — AI unavailable</span>
        )}
      </div>

      <div className="ai-disclaimer">
        ⚠ AI recommendation is advisory only. Human approval is required before any payment.
        AI cannot approve, execute, or modify payments.
      </div>

      <div className="ai-summary">{ai.summary}</div>

      {ai.recommended_route && (
        <div className="ai-recommended">
          Recommended route: <strong>{ai.recommended_route}</strong>
        </div>
      )}

      {ai.reasoning_factors.length > 0 && (
        <div className="ai-section">
          <div className="ai-section-title">Reasoning factors</div>
          <ul className="ai-list">
            {ai.reasoning_factors.map((f, i) => <li key={i}>{f}</li>)}
          </ul>
        </div>
      )}

      {ai.warnings.length > 0 && (
        <div className="ai-section">
          <div className="ai-section-title">AI warnings</div>
          <ul className="ai-list ai-warnings">
            {ai.warnings.map((w, i) => <li key={i}>⚠ {w}</li>)}
          </ul>
        </div>
      )}

      {ai.requires_human_review && (
        <div className="ai-review-flag">
          🔍 Human review required before proceeding
        </div>
      )}

      {ai.fallback_reason && (
        <div className="ai-fallback-reason text-muted text-sm">
          Fallback reason: {ai.fallback_reason}
        </div>
      )}
    </section>
  )
}

// ─── Main Page ────────────────────────────────────────────────────────────

export default function AnalysisPage() {
  const [batchId, setBatchId] = useState('')
  const [strategy, setStrategy] = useState<Strategy>('LOWEST_COST')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<BatchAnalysis | null>(null)

  async function runAnalysis() {
    const id = batchId.trim()
    if (!id) {
      setError('Please enter a Batch ID.')
      return
    }
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const data = await fetchBatchAnalysis(id, strategy)
      setResult(data)
    } catch (err: unknown) {
      const e = err as { error?: { message?: string }; detail?: string }
      setError(
        e?.error?.message ?? e?.detail ?? 'Analysis failed. Check the batch ID and try again.'
      )
    } finally {
      setLoading(false)
    }
  }

  const eligibleRoutes = result?.provider_routes.filter((r) => r.eligible) ?? []
  const excludedRoutes = result?.provider_routes.filter((r) => !r.eligible) ?? []
  const recommendedCode = result?.ai_recommendation?.recommended_route ?? null

  return (
    <div className="analysis-page">
      {/* ── Global disclaimer ── */}
      <div className="analysis-disclaimer">
        <strong>⚠ PROTOTYPE NOTICE:</strong> All cost estimates are{' '}
        <span className="label-simulated">SIMULATED</span>. No real money movement occurs.
        PayPal estimates apply to the{' '}
        <span className="label-sandbox">SANDBOX</span> environment only.
        AI recommendations require human approval.
      </div>

      {/* ── Query form ── */}
      <section className="analysis-form card">
        <h2 className="section-title">Financial Route Analysis</h2>
        <div className="form-row">
          <div className="form-group">
            <label htmlFor="batch-id-input">Batch ID</label>
            <input
              id="batch-id-input"
              className="form-input"
              type="text"
              placeholder="e.g. 3fa85f64-5717-4562-b3fc-2c963f66afa6"
              value={batchId}
              onChange={(e) => setBatchId(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && runAnalysis()}
            />
          </div>
          <div className="form-group">
            <label htmlFor="strategy-select">Ranking Strategy</label>
            <select
              id="strategy-select"
              className="form-input"
              value={strategy}
              onChange={(e) => setStrategy(e.target.value as Strategy)}
            >
              <option value="LOWEST_COST">Lowest Cost</option>
              <option value="FASTEST">Fastest</option>
              <option value="BALANCED">Balanced</option>
            </select>
          </div>
          <div className="form-group form-group-action">
            <button
              className="btn btn-primary"
              onClick={runAnalysis}
              disabled={loading}
            >
              {loading ? 'Analysing…' : 'Analyse Batch'}
            </button>
          </div>
        </div>
        {error && <div className="error-banner">{error}</div>}
      </section>

      {/* ── Results ── */}
      {result && (
        <>
          {/* Batch summary */}
          <section className="card">
            <h2 className="section-title">
              Batch Summary
              <span className="label-simulated ml-2">SIMULATED</span>
            </h2>
            <div className="summary-grid">
              <div className="summary-item">
                <div className="summary-label">Batch Reference</div>
                <div className="summary-value">{result.batch_reference}</div>
              </div>
              <div className="summary-item">
                <div className="summary-label">Obligations</div>
                <div className="summary-value">{result.total_obligations}</div>
              </div>
              <div className="summary-item">
                <div className="summary-label">Strategy</div>
                <div className="summary-value">{result.routing_strategy}</div>
              </div>
              <div className="summary-item">
                <div className="summary-label">Funding Snapshot</div>
                <div className="summary-value">
                  <span className="label-simulated">{result.funding_snapshot_label}</span>
                </div>
              </div>
            </div>

            {/* Currency totals */}
            <div className="currency-totals">
              <div className="currency-totals-title">Total by Currency</div>
              <div className="currency-chips">
                {Object.entries(result.total_amount_by_currency).map(([ccy, amt]) => (
                  <div key={ccy} className="currency-chip">
                    <span className="currency-code">{ccy}</span>
                    <span className="currency-amount">{fmtMoney(amt)}</span>
                  </div>
                ))}
              </div>
            </div>
          </section>

          {/* Provider comparison table */}
          <section className="card">
            <h2 className="section-title">Provider Comparison</h2>
            <div className="provider-table-wrapper">
              <table className="provider-table">
                <thead>
                  <tr>
                    <th>Provider</th>
                    <th>Status</th>
                    <th>Fees / Reason</th>
                    <th>Est. Total Cost</th>
                    <th>Recipient Receives</th>
                    <th>Est. Time</th>
                    <th>Warnings</th>
                  </tr>
                </thead>
                <tbody>
                  {/* Eligible first */}
                  {eligibleRoutes.map((r) => (
                    <ProviderRow
                      key={r.provider_code}
                      route={r}
                      isRecommended={r.provider_code === recommendedCode}
                    />
                  ))}
                  {/* Excluded */}
                  {excludedRoutes.map((r) => (
                    <ProviderRow
                      key={r.provider_code}
                      route={r}
                      isRecommended={false}
                    />
                  ))}
                </tbody>
              </table>
            </div>
            <p className="table-note">
              All estimates are <span className="label-simulated">SIMULATED</span>.
              FX rates are synthetic demo values, not live market rates.
              Fees are illustrative based on published documentation.
            </p>
          </section>

          {/* AI Advisory panel */}
          {result.ai_recommendation && (
            <AiPanel ai={result.ai_recommendation} />
          )}

          {/* Disclaimer */}
          <div className="analysis-footer-disclaimer">
            {result.disclaimer}
          </div>
        </>
      )}
    </div>
  )
}
