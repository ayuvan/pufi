import React, { useState } from 'react'
import { AlertTriangle, Copy, Check, RefreshCw } from 'lucide-react'

interface ErrorStateProps {
  title?: string
  message: string
  correlationId?: string
  onRetry?: () => void
}

export const ErrorState: React.FC<ErrorStateProps> = ({
  title = 'System Operation Failed',
  message,
  correlationId,
  onRetry,
}) => {
  const [copied, setCopied] = useState(false)

  const handleCopy = () => {
    if (correlationId) {
      navigator.clipboard.writeText(correlationId)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  return (
    <div
      style={{
        padding: '20px 24px',
        borderRadius: 'var(--radius-lg)',
        background: 'var(--pufi-danger-bg)',
        border: '1px solid var(--pufi-danger-border)',
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
        margin: '16px 0',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <div
          style={{
            width: 32,
            height: 32,
            borderRadius: '50%',
            background: 'var(--pufi-danger-border)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--pufi-danger-text)',
            flexShrink: 0,
          }}
        >
          <AlertTriangle size={18} />
        </div>
        <div>
          <h4
            style={{
              margin: 0,
              fontSize: '0.92rem',
              fontWeight: 700,
              color: 'var(--pufi-danger-text)',
            }}
          >
            {title}
          </h4>
          <p
            style={{
              margin: '2px 0 0 0',
              fontSize: '0.84rem',
              color: 'var(--text-primary)',
            }}
          >
            {message}
          </p>
        </div>
      </div>

      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: 12,
          paddingTop: 8,
          borderTop: '1px solid var(--pufi-danger-border)',
        }}
      >
        {correlationId ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.76rem' }}>
            <span style={{ color: 'var(--text-secondary)' }}>Correlation ID:</span>
            <code
              style={{
                background: 'rgba(0,0,0,0.06)',
                padding: '2px 6px',
                borderRadius: 'var(--radius-xs)',
                fontFamily: 'monospace',
                fontWeight: 600,
              }}
            >
              {correlationId}
            </code>
            <button
              onClick={handleCopy}
              style={{
                border: 'none',
                background: 'transparent',
                cursor: 'pointer',
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4,
                color: 'var(--pufi-primary)',
                fontSize: '0.74rem',
                fontWeight: 650,
              }}
            >
              {copied ? <Check size={12} color="var(--pufi-success)" /> : <Copy size={12} />}
              <span>{copied ? 'Copied' : 'Copy'}</span>
            </button>
          </div>
        ) : (
          <div />
        )}

        {onRetry && (
          <button
            onClick={onRetry}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              padding: '6px 14px',
              borderRadius: 'var(--radius-sm)',
              background: 'var(--bg-surface)',
              border: '1px solid var(--border-base)',
              fontSize: '0.8rem',
              fontWeight: 650,
              color: 'var(--text-primary)',
              cursor: 'pointer',
            }}
          >
            <RefreshCw size={13} />
            <span>Retry Operation</span>
          </button>
        )}
      </div>
    </div>
  )
}
