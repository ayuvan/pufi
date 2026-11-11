import React from 'react'

interface CurrencyBadgeProps {
  currency: string
  size?: 'sm' | 'md'
}

const CURRENCY_SYMBOLS: Record<string, string> = {
  USD: '$',
  EUR: '€',
  GBP: '£',
  CAD: 'CA$',
  AUD: 'AU$',
  JPY: '¥',
  CHF: 'CHF',
  INR: '₹',
  SGD: 'SG$',
}

export const CurrencyBadge: React.FC<CurrencyBadgeProps> = ({ currency, size = 'md' }) => {
  const curr = (currency || 'USD').toUpperCase()
  const isInvalid = curr === 'ZZZ'
  const symbol = CURRENCY_SYMBOLS[curr] || curr

  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 4,
        padding: size === 'sm' ? '1px 6px' : '2px 8px',
        fontSize: size === 'sm' ? '0.72rem' : '0.78rem',
        fontWeight: 700,
        borderRadius: 'var(--radius-sm)',
        background: isInvalid ? 'var(--pufi-danger-bg)' : 'var(--bg-subtle)',
        color: isInvalid ? 'var(--pufi-danger-text)' : 'var(--text-primary)',
        border: `1px solid ${isInvalid ? 'var(--pufi-danger-border)' : 'var(--border-subtle)'}`,
        fontFamily: 'monospace',
      }}
      title={`Currency: ${curr}`}
    >
      <span style={{ opacity: 0.7 }}>{symbol}</span>
      <span>{curr}</span>
      {isInvalid && <span style={{ color: 'var(--pufi-danger)' }}>⚠</span>}
    </span>
  )
}
