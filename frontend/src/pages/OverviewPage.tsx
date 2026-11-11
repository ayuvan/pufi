import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  fetchObligations,
  fetchBatches,
  type Obligation,
  type Batch,
} from '../api/client'
import { PageHeader } from '../components/layout/PageHeader'
import { MetricCard } from '../components/common/MetricCard'
import { StatusBadge } from '../components/common/StatusBadge'
import { CurrencyBadge } from '../components/common/CurrencyBadge'
import { SkeletonBox } from '../components/common/LoadingSkeleton'
import {
  AreaTrendChart,
  StatusDonutChart,
  type TrendDataPoint,
  type DonutSegment,
} from '../components/common/FinancialChart'
import {
  FileText,
  CheckCircle2,
  Clock,
  Layers,
  ArrowRight,
  UploadCloud,
  Cpu,
  ShieldCheck,
  TrendingUp,
} from 'lucide-react'

interface OverviewPageProps {
  onNavigate: (page: string) => void
  onOpenBatchDetail?: (id: string) => void
}

function formatAmount(amount: string | number, currency: string = 'USD'): string {
  const num = typeof amount === 'number' ? amount : parseFloat(amount)
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

export const OverviewPage: React.FC<OverviewPageProps> = ({
  onNavigate,
  onOpenBatchDetail,
}) => {
  // 1. Obligations query
  const { data: obligationsData, isLoading: isObligationsLoading } = useQuery({
    queryKey: ['obligations', 0, ''],
    queryFn: () => fetchObligations({ limit: 200, offset: 0 }),
  })

  // 2. Batches query
  const { data: batches, isLoading: isBatchesLoading } = useQuery({
    queryKey: ['batches'],
    queryFn: () => fetchBatches({ limit: 50 }),
  })

  const obligations: Obligation[] = obligationsData?.items ?? []
  const totalCount = obligationsData?.total ?? 0

  // Derived financial statistics from actual data
  const {
    validatedCount,
    draftCount,
    totalVolumeUSD,
    validatedVolumeUSD,
    statusSegments,
    trendData,
  } = useMemo(() => {
    let validated = 0
    let draft = 0
    let totalUsd = 0
    let validatedUsd = 0

    const statusCounts: Record<string, number> = {
      VALIDATED: 0,
      DRAFT: 0,
      ON_HOLD: 0,
      READY: 0,
      CLOSED: 0,
    }

    const dateBuckets: Record<string, { amount: number; count: number }> = {}

    obligations.forEach((ob) => {
      const val = parseFloat(ob.amount) || 0
      totalUsd += val

      if (statusCounts[ob.status] !== undefined) {
        statusCounts[ob.status]++
      } else {
        statusCounts[ob.status] = 1
      }

      if (ob.status === 'VALIDATED') {
        validated++
        validatedUsd += val
      } else if (ob.status === 'DRAFT') {
        draft++
      }

      // Group into trend dates by due_at or created_at
      const dateKey = ob.due_at ? ob.due_at.slice(5) : 'Nov'
      if (!dateBuckets[dateKey]) {
        dateBuckets[dateKey] = { amount: 0, count: 0 }
      }
      dateBuckets[dateKey].amount += val
      dateBuckets[dateKey].count += 1
    })

    const statusColors: Record<string, string> = {
      VALIDATED: 'var(--pufi-success)',
      DRAFT: 'var(--pufi-warning)',
      READY: 'var(--pufi-info)',
      ON_HOLD: '#F59E0B',
      CLOSED: 'var(--text-muted)',
    }

    const segments: DonutSegment[] = Object.entries(statusCounts)
      .filter(([_, count]) => count > 0)
      .map(([label, count]) => ({
        label,
        count,
        color: statusColors[label] || '#94A3B8',
      }))

    const trend: TrendDataPoint[] = Object.entries(dateBuckets)
      .sort(([a], [b]) => a.localeCompare(b))
      .slice(-7)
      .map(([date, item]) => ({
        date,
        amount: item.amount,
        count: item.count,
      }))

    return {
      validatedCount: validated,
      draftCount: draft,
      totalVolumeUSD: totalUsd,
      validatedVolumeUSD: validatedUsd,
      statusSegments: segments,
      trendData: trend,
    }
  }, [obligations])

  const activeBatchesCount = useMemo(() => {
    return batches?.filter((b: Batch) => ['DRAFT', 'ANALYZED', 'APPROVED', 'PROCESSING'].includes(b.status)).length || 0
  }, [batches])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 28 }}>
      {/* Header with Quick Actions */}
      <PageHeader
        title="Treasury Overview"
        subtitle="Global payment coordination, obligation status verification, and multi-provider settlement status."
        badge={
          <span
            style={{
              fontSize: '0.74rem',
              fontWeight: 700,
              padding: '3px 10px',
              borderRadius: 'var(--radius-pill)',
              background: 'var(--pufi-primary-light)',
              color: 'var(--pufi-primary)',
              border: '1px solid rgba(22,119,255,0.25)',
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
            }}
          >
            <TrendingUp size={13} />
            Live Treasury Ledger
          </span>
        }
        actions={
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            <button
              onClick={() => onNavigate('import')}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                padding: '8px 16px',
                borderRadius: 'var(--radius-md)',
                background: 'var(--bg-surface)',
                border: '1px solid var(--border-base)',
                fontSize: '0.84rem',
                fontWeight: 650,
                color: 'var(--text-primary)',
                cursor: 'pointer',
                transition: 'all var(--trans-fast)',
              }}
            >
              <UploadCloud size={15} color="var(--pufi-primary)" />
              <span>Import Invoices</span>
            </button>

            <button
              onClick={() => onNavigate('batches')}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                padding: '8px 16px',
                borderRadius: 'var(--radius-md)',
                background: 'var(--pufi-primary)',
                border: 'none',
                fontSize: '0.84rem',
                fontWeight: 650,
                color: '#FFFFFF',
                cursor: 'pointer',
                boxShadow: 'var(--shadow-sm)',
                transition: 'all var(--trans-fast)',
              }}
            >
              <Layers size={15} />
              <span>Create Payment Batch</span>
            </button>
          </div>
        }
      />

      {/* KPI Cards Row */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
          gap: 18,
        }}
      >
        <MetricCard
          title="Total Payment Obligations"
          value={isObligationsLoading ? '…' : totalCount}
          subtext={`Cumulative: ${formatAmount(totalVolumeUSD)}`}
          icon={<FileText size={20} />}
          highlightColor="#1677FF"
          trend={{ label: `${obligations.length} Sampled`, isNeutral: true }}
          onClick={() => onNavigate('obligations')}
        />

        <MetricCard
          title="Validated Obligations"
          value={isObligationsLoading ? '…' : validatedCount}
          subtext={`Ready for batching: ${formatAmount(validatedVolumeUSD)}`}
          icon={<CheckCircle2 size={20} />}
          highlightColor="#16A779"
          trend={{ label: 'Eligible', isPositive: true }}
          onClick={() => onNavigate('obligations')}
        />

        <MetricCard
          title="Draft & Review Queue"
          value={isObligationsLoading ? '…' : draftCount}
          subtext="Requires verification"
          icon={<Clock size={20} />}
          highlightColor="#E9A23B"
          trend={{ label: 'Pending validation', isNeutral: true }}
          onClick={() => onNavigate('obligations')}
        />

        <MetricCard
          title="Active Payment Batches"
          value={isBatchesLoading ? '…' : activeBatchesCount}
          subtext={`${batches?.length || 0} total lifetime batches`}
          icon={<Layers size={20} />}
          highlightColor="#0284C7"
          trend={{ label: 'PayPal Sandbox', isPositive: true }}
          onClick={() => onNavigate('batches')}
        />
      </div>

      {/* Analytics Charts Grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))',
          gap: 24,
        }}
      >
        {/* Chart 1: Obligations Volume Trend */}
        <div
          style={{
            background: 'var(--bg-surface)',
            border: '1px solid var(--border-base)',
            borderRadius: 'var(--radius-lg)',
            padding: '24px 26px',
            boxShadow: 'var(--shadow-card)',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
            <div>
              <h3 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 750, color: 'var(--text-primary)' }}>
                Obligation Volume & Schedule
              </h3>
              <p style={{ margin: '4px 0 0 0', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                Distribution of supplier payment liabilities scheduled by due window
              </p>
            </div>
            <span
              style={{
                fontSize: '0.72rem',
                fontWeight: 700,
                color: 'var(--text-muted)',
                background: 'var(--bg-subtle)',
                padding: '3px 8px',
                borderRadius: 'var(--radius-sm)',
              }}
            >
              Authoritative Decimal Data
            </span>
          </div>

          <AreaTrendChart data={trendData} height={200} currency="USD" />
        </div>

        {/* Chart 2: Status Breakdown Donut */}
        <div
          style={{
            background: 'var(--bg-surface)',
            border: '1px solid var(--border-base)',
            borderRadius: 'var(--radius-lg)',
            padding: '24px 26px',
            boxShadow: 'var(--shadow-card)',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
            <div>
              <h3 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 750, color: 'var(--text-primary)' }}>
                Lifecycle Status Distribution
              </h3>
              <p style={{ margin: '4px 0 0 0', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                Breakdown of obligations across validation and settlement stages
              </p>
            </div>
            <button
              onClick={() => onNavigate('obligations')}
              style={{
                background: 'transparent',
                border: 'none',
                color: 'var(--pufi-primary)',
                cursor: 'pointer',
                fontSize: '0.78rem',
                fontWeight: 650,
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4,
              }}
            >
              <span>Explore All</span>
              <ArrowRight size={13} />
            </button>
          </div>

          <StatusDonutChart segments={statusSegments} totalLabel="Obligations" size={190} />
        </div>
      </div>

      {/* Operational Modules Quick Access Strip */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
          gap: 16,
        }}
      >
        <div
          onClick={() => onNavigate('import')}
          style={{
            background: 'var(--bg-surface)',
            border: '1px solid var(--border-base)',
            borderRadius: 'var(--radius-md)',
            padding: '18px 20px',
            display: 'flex',
            alignItems: 'center',
            gap: 14,
            cursor: 'pointer',
            transition: 'all var(--trans-fast)',
            boxShadow: 'var(--shadow-xs)',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.transform = 'translateY(-2px)'
            e.currentTarget.style.borderColor = 'var(--pufi-primary)'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.transform = 'translateY(0)'
            e.currentTarget.style.borderColor = 'var(--border-base)'
          }}
        >
          <div
            style={{
              width: 40,
              height: 40,
              borderRadius: 'var(--radius-md)',
              background: 'var(--pufi-primary-light)',
              color: 'var(--pufi-primary)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <UploadCloud size={20} />
          </div>
          <div style={{ flex: 1 }}>
            <h4 style={{ margin: 0, fontSize: '0.92rem', fontWeight: 700, color: 'var(--text-primary)' }}>
              Ingest Obligations
            </h4>
            <p style={{ margin: '2px 0 0 0', fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
              Bulk JSON import with automated duplicate protection
            </p>
          </div>
          <ArrowRight size={16} color="var(--text-muted)" />
        </div>

        <div
          onClick={() => onNavigate('analysis')}
          style={{
            background: 'var(--bg-surface)',
            border: '1px solid var(--border-base)',
            borderRadius: 'var(--radius-md)',
            padding: '18px 20px',
            display: 'flex',
            alignItems: 'center',
            gap: 14,
            cursor: 'pointer',
            transition: 'all var(--trans-fast)',
            boxShadow: 'var(--shadow-xs)',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.transform = 'translateY(-2px)'
            e.currentTarget.style.borderColor = 'var(--pufi-primary)'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.transform = 'translateY(0)'
            e.currentTarget.style.borderColor = 'var(--border-base)'
          }}
        >
          <div
            style={{
              width: 40,
              height: 40,
              borderRadius: 'var(--radius-md)',
              background: 'var(--pufi-info-bg)',
              color: 'var(--pufi-info-text)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <Cpu size={20} />
          </div>
          <div style={{ flex: 1 }}>
            <h4 style={{ margin: 0, fontSize: '0.92rem', fontWeight: 700, color: 'var(--text-primary)' }}>
              Route Optimizer
            </h4>
            <p style={{ margin: '2px 0 0 0', fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
              AI advisory & multi-provider cost comparison
            </p>
          </div>
          <ArrowRight size={16} color="var(--text-muted)" />
        </div>

        <div
          onClick={() => onNavigate('audit')}
          style={{
            background: 'var(--bg-surface)',
            border: '1px solid var(--border-base)',
            borderRadius: 'var(--radius-md)',
            padding: '18px 20px',
            display: 'flex',
            alignItems: 'center',
            gap: 14,
            cursor: 'pointer',
            transition: 'all var(--trans-fast)',
            boxShadow: 'var(--shadow-xs)',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.transform = 'translateY(-2px)'
            e.currentTarget.style.borderColor = 'var(--pufi-primary)'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.transform = 'translateY(0)'
            e.currentTarget.style.borderColor = 'var(--border-base)'
          }}
        >
          <div
            style={{
              width: 40,
              height: 40,
              borderRadius: 'var(--radius-md)',
              background: 'var(--pufi-success-bg)',
              color: 'var(--pufi-success-text)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <ShieldCheck size={20} />
          </div>
          <div style={{ flex: 1 }}>
            <h4 style={{ margin: 0, fontSize: '0.92rem', fontWeight: 700, color: 'var(--text-primary)' }}>
              Audit & Compliance
            </h4>
            <p style={{ margin: '2px 0 0 0', fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
              Immutable transition logs and maker-checker traces
            </p>
          </div>
          <ArrowRight size={16} color="var(--text-muted)" />
        </div>
      </div>

      {/* Two Columns: Recent Batches & Recent Obligations */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(460px, 1fr))',
          gap: 24,
        }}
      >
        {/* Recent Batches Card */}
        <div
          style={{
            background: 'var(--bg-surface)',
            border: '1px solid var(--border-base)',
            borderRadius: 'var(--radius-lg)',
            padding: '24px',
            boxShadow: 'var(--shadow-card)',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <h3 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 750, color: 'var(--text-primary)' }}>
              Recent Payment Batches
            </h3>
            <button
              onClick={() => onNavigate('batches')}
              style={{
                background: 'transparent',
                border: 'none',
                color: 'var(--pufi-primary)',
                cursor: 'pointer',
                fontSize: '0.8rem',
                fontWeight: 650,
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4,
              }}
            >
              <span>View all batches</span>
              <ArrowRight size={13} />
            </button>
          </div>

          {isBatchesLoading ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <SkeletonBox height={40} />
              <SkeletonBox height={40} />
              <SkeletonBox height={40} />
            </div>
          ) : !batches || batches.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '32px 0', color: 'var(--text-muted)' }}>
              No payment batches created yet.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {batches.slice(0, 5).map((b: Batch) => (
                <div
                  key={b.id}
                  onClick={() => onOpenBatchDetail ? onOpenBatchDetail(b.id) : onNavigate('batches')}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '12px 14px',
                    borderRadius: 'var(--radius-md)',
                    background: 'var(--bg-subtle)',
                    border: '1px solid var(--border-subtle)',
                    cursor: 'pointer',
                    transition: 'all var(--trans-fast)',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.backgroundColor = 'var(--bg-surface-hover)'
                    e.currentTarget.style.borderColor = 'var(--border-strong)'
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.backgroundColor = 'var(--bg-subtle)'
                    e.currentTarget.style.borderColor = 'var(--border-subtle)'
                  }}
                >
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <code style={{ fontWeight: 800, color: 'var(--pufi-primary)', fontSize: '0.86rem' }}>
                        {b.batch_reference}
                      </code>
                      <StatusBadge status={b.status} size="sm" />
                    </div>
                    <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)', marginTop: 3 }}>
                      {b.obligation_count} obligations • Created {new Date(b.created_at).toLocaleDateString()}
                    </div>
                  </div>

                  <ArrowRight size={15} color="var(--text-muted)" />
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Recent Obligations Card */}
        <div
          style={{
            background: 'var(--bg-surface)',
            border: '1px solid var(--border-base)',
            borderRadius: 'var(--radius-lg)',
            padding: '24px',
            boxShadow: 'var(--shadow-card)',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <h3 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 750, color: 'var(--text-primary)' }}>
              Recent Obligations
            </h3>
            <button
              onClick={() => onNavigate('obligations')}
              style={{
                background: 'transparent',
                border: 'none',
                color: 'var(--pufi-primary)',
                cursor: 'pointer',
                fontSize: '0.8rem',
                fontWeight: 650,
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4,
              }}
            >
              <span>View all obligations</span>
              <ArrowRight size={13} />
            </button>
          </div>

          {isObligationsLoading ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <SkeletonBox height={40} />
              <SkeletonBox height={40} />
              <SkeletonBox height={40} />
            </div>
          ) : obligations.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '32px 0', color: 'var(--text-muted)' }}>
              No supplier obligations registered.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {obligations.slice(0, 5).map((ob: Obligation) => (
                <div
                  key={ob.id}
                  onClick={() => onNavigate('obligations')}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '12px 14px',
                    borderRadius: 'var(--radius-md)',
                    background: 'var(--bg-subtle)',
                    border: '1px solid var(--border-subtle)',
                    cursor: 'pointer',
                    transition: 'all var(--trans-fast)',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.backgroundColor = 'var(--bg-surface-hover)'
                    e.currentTarget.style.borderColor = 'var(--border-strong)'
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.backgroundColor = 'var(--bg-subtle)'
                    e.currentTarget.style.borderColor = 'var(--border-subtle)'
                  }}
                >
                  <div style={{ minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span style={{ fontWeight: 700, fontSize: '0.86rem', color: 'var(--text-primary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {ob.supplier.display_name}
                      </span>
                      <CurrencyBadge currency={ob.currency} size="sm" />
                    </div>
                    <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)', marginTop: 3 }}>
                      Inv: <code>{ob.invoice_reference}</code> • Due {ob.due_at}
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
                    <strong className="num-tabular" style={{ fontSize: '0.92rem', color: 'var(--text-primary)' }}>
                      {formatAmount(ob.amount, ob.currency)}
                    </strong>
                    <StatusBadge status={ob.status} size="sm" />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
