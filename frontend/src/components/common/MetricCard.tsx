import React from 'react'

interface MetricCardProps {
  title: string
  value: string | number
  subtext?: string
  icon: React.ReactNode
  trend?: {
    label: string
    isPositive?: boolean
    isNeutral?: boolean
  }
  badge?: React.ReactNode
  onClick?: () => void
  highlightColor?: string
}

export const MetricCard: React.FC<MetricCardProps> = ({
  title,
  value,
  subtext,
  icon,
  trend,
  badge,
  onClick,
  highlightColor = 'var(--pufi-primary)',
}) => {
  return (
    <div
      onClick={onClick}
      style={{
        background: 'var(--bg-surface)',
        border: '1px solid var(--border-base)',
        borderRadius: 'var(--radius-lg)',
        padding: '20px 22px',
        boxShadow: 'var(--shadow-card)',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        cursor: onClick ? 'pointer' : 'default',
        transition: 'transform var(--trans-fast), box-shadow var(--trans-fast), border-color var(--trans-fast)',
        position: 'relative',
        overflow: 'hidden',
      }}
      onMouseEnter={(e) => {
        if (onClick) {
          e.currentTarget.style.transform = 'translateY(-2px)'
          e.currentTarget.style.boxShadow = 'var(--shadow-card-hover)'
          e.currentTarget.style.borderColor = 'var(--border-strong)'
        }
      }}
      onMouseLeave={(e) => {
        if (onClick) {
          e.currentTarget.style.transform = 'translateY(0)'
          e.currentTarget.style.boxShadow = 'var(--shadow-card)'
          e.currentTarget.style.borderColor = 'var(--border-base)'
        }
      }}
    >
      {/* Top row: Title + Icon */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <span
          style={{
            fontSize: '0.84rem',
            fontWeight: 600,
            color: 'var(--text-secondary)',
            letterSpacing: '0.01em',
          }}
        >
          {title}
        </span>
        <div
          style={{
            width: 36,
            height: 36,
            borderRadius: 'var(--radius-md)',
            background: 'var(--bg-subtle)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: highlightColor,
          }}
        >
          {icon}
        </div>
      </div>

      {/* Main value */}
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 8 }}>
        <span
          className="num-tabular"
          style={{
            fontSize: '1.85rem',
            fontWeight: 800,
            color: 'var(--text-primary)',
            lineHeight: 1.1,
          }}
        >
          {value}
        </span>
        {badge}
      </div>

      {/* Bottom row: trend or subtext */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.78rem' }}>
        {trend && (
          <span
            style={{
              padding: '2px 8px',
              borderRadius: 'var(--radius-pill)',
              fontWeight: 700,
              fontSize: '0.72rem',
              background: trend.isNeutral
                ? 'var(--bg-subtle)'
                : trend.isPositive
                ? 'var(--pufi-success-bg)'
                : 'var(--pufi-danger-bg)',
              color: trend.isNeutral
                ? 'var(--text-secondary)'
                : trend.isPositive
                ? 'var(--pufi-success-text)'
                : 'var(--pufi-danger-text)',
            }}
          >
            {trend.label}
          </span>
        )}
        {subtext && (
          <span style={{ color: 'var(--text-muted)' }}>
            {subtext}
          </span>
        )}
      </div>
    </div>
  )
}
