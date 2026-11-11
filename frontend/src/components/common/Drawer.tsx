import React, { useEffect } from 'react'
import { X } from 'lucide-react'

interface DrawerProps {
  isOpen: boolean
  onClose: () => void
  title: string
  subtitle?: string
  children: React.ReactNode
  width?: string | number
}

export const Drawer: React.FC<DrawerProps> = ({
  isOpen,
  onClose,
  title,
  subtitle,
  children,
  width = 540,
}) => {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) onClose()
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, onClose])

  if (!isOpen) return null

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 1000,
        display: 'flex',
        justifyContent: 'flex-end',
      }}
    >
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{
          position: 'fixed',
          inset: 0,
          background: 'rgba(16, 28, 50, 0.45)',
          backdropFilter: 'blur(4px)',
          animation: 'fadeIn var(--trans-fast) forwards',
        }}
      />

      {/* Drawer Card */}
      <div
        style={{
          position: 'relative',
          width: typeof width === 'number' ? `${width}px` : width,
          maxWidth: '100vw',
          height: '100%',
          background: 'var(--bg-surface)',
          boxShadow: 'var(--shadow-drawer)',
          display: 'flex',
          flexDirection: 'column',
          zIndex: 1001,
          animation: 'slideInLeft var(--trans-normal) forwards',
          borderLeft: '1px solid var(--border-base)',
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: '20px 24px',
            borderBottom: '1px solid var(--border-subtle)',
            display: 'flex',
            alignItems: 'flex-start',
            justifyContent: 'space-between',
            background: 'var(--bg-surface)',
          }}
        >
          <div>
            <h3
              style={{
                margin: 0,
                fontSize: '1.15rem',
                fontWeight: 750,
                color: 'var(--text-primary)',
              }}
            >
              {title}
            </h3>
            {subtitle && (
              <p
                style={{
                  margin: '4px 0 0 0',
                  fontSize: '0.82rem',
                  color: 'var(--text-secondary)',
                }}
              >
                {subtitle}
              </p>
            )}
          </div>
          <button
            onClick={onClose}
            style={{
              background: 'var(--bg-subtle)',
              border: 'none',
              width: 32,
              height: 32,
              borderRadius: '50%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'pointer',
              color: 'var(--text-secondary)',
              transition: 'background var(--trans-fast)',
            }}
            title="Close (Esc)"
          >
            <X size={16} />
          </button>
        </div>

        {/* Content Body */}
        <div
          style={{
            padding: 24,
            overflowY: 'auto',
            flex: 1,
          }}
        >
          {children}
        </div>
      </div>
    </div>
  )
}
