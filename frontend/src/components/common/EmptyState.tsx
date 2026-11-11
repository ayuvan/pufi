import React from 'react'
import { Inbox } from 'lucide-react'

interface EmptyStateProps {
  title: string
  description: string
  icon?: React.ReactNode
  action?: {
    label: string
    onClick: () => void
    icon?: React.ReactNode
  }
  style?: React.CSSProperties
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  title,
  description,
  icon,
  action,
  style,
}) => {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        textAlign: 'center',
        padding: '56px 24px',
        borderRadius: 'var(--radius-lg)',
        border: '1px dashed var(--border-strong)',
        background: 'var(--bg-surface)',
        ...style,
      }}
    >
      <div
        style={{
          width: 52,
          height: 52,
          borderRadius: '50%',
          background: 'var(--bg-subtle)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'var(--text-muted)',
          marginBottom: 16,
        }}
      >
        {icon || <Inbox size={26} />}
      </div>
      <h3
        style={{
          fontSize: '1.05rem',
          fontWeight: 700,
          color: 'var(--text-primary)',
          margin: '0 0 6px 0',
        }}
      >
        {title}
      </h3>
      <p
        style={{
          fontSize: '0.85rem',
          color: 'var(--text-secondary)',
          maxWidth: 420,
          margin: '0 0 20px 0',
          lineHeight: 1.5,
        }}
      >
        {description}
      </p>
      {action && (
        <button
          onClick={action.onClick}
          className="btn-pufi-primary"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 8,
            padding: '10px 20px',
            borderRadius: 'var(--radius-pill)',
            fontWeight: 650,
            fontSize: '0.86rem',
            background: 'var(--pufi-primary)',
            color: '#FFFFFF',
            border: 'none',
            cursor: 'pointer',
            transition: 'background-color var(--trans-fast), transform var(--trans-fast)',
            boxShadow: 'var(--shadow-sm)',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.backgroundColor = 'var(--pufi-primary-hover)'
            e.currentTarget.style.transform = 'translateY(-1px)'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.backgroundColor = 'var(--pufi-primary)'
            e.currentTarget.style.transform = 'translateY(0)'
          }}
        >
          {action.icon}
          <span>{action.label}</span>
        </button>
      )}
    </div>
  )
}
