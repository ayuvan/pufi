import React from 'react'
import type { ObligationStatus } from '../../api/client'

export type AnyStatus = ObligationStatus | 'APPROVED' | 'SUBMITTED' | 'PROCESSING' | 'COMPLETED' | 'PARTIALLY_COMPLETED' | 'FAILED' | 'ACCEPTED' | 'DUPLICATE' | 'INVALID' | 'ELIGIBLE' | 'EXCLUDED' | 'SIMULATED' | 'SANDBOX' | 'LIVE' | string

interface StatusBadgeProps {
  status: AnyStatus
  label?: string
  size?: 'sm' | 'md' | 'lg'
  icon?: React.ReactNode
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({
  status,
  label,
  size = 'md',
  icon,
}) => {
  const norm = (status || '').toUpperCase()

  let bg = 'var(--bg-subtle)'
  let text = 'var(--text-secondary)'
  let border = 'var(--border-base)'

  if (['VALIDATED', 'APPROVED', 'COMPLETED', 'ACCEPTED', 'ELIGIBLE', 'LIVE'].includes(norm)) {
    bg = 'var(--pufi-success-bg)'
    text = 'var(--pufi-success-text)'
    border = 'var(--pufi-success-border)'
  } else if (['DRAFT', 'ON_HOLD', 'PROCESSING', 'SUBMITTED', 'DUPLICATE', 'SIMULATED'].includes(norm)) {
    bg = 'var(--pufi-warning-bg)'
    text = 'var(--pufi-warning-text)'
    border = 'var(--pufi-warning-border)'
  } else if (['CANCELLED', 'CLOSED', 'FAILED', 'INVALID', 'EXCLUDED'].includes(norm)) {
    bg = 'var(--pufi-danger-bg)'
    text = 'var(--pufi-danger-text)'
    border = 'var(--pufi-danger-border)'
  } else if (['READY', 'SANDBOX'].includes(norm)) {
    bg = 'var(--pufi-info-bg)'
    text = 'var(--pufi-info-text)'
    border = 'var(--pufi-info-border)'
  }

  const padding = size === 'sm' ? '2px 8px' : size === 'lg' ? '6px 14px' : '4px 10px'
  const fontSize = size === 'sm' ? '0.72rem' : size === 'lg' ? '0.85rem' : '0.78rem'

  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 5,
        padding,
        fontSize,
        fontWeight: 650,
        borderRadius: 'var(--radius-pill)',
        backgroundColor: bg,
        color: text,
        border: `1px solid ${border}`,
        lineHeight: 1.2,
        letterSpacing: '0.02em',
        textTransform: 'uppercase',
      }}
    >
      {icon && <span style={{ display: 'inline-flex', alignItems: 'center' }}>{icon}</span>}
      {label || norm.replace('_', ' ')}
    </span>
  )
}
