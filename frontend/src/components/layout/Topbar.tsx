import React from 'react'
import {
  Sun,
  Moon,
  Search,
  ExternalLink,
  Shield,
  Activity,
} from 'lucide-react'
import type { NavPage } from './AppSidebar'

interface TopbarProps {
  currentPage: NavPage
  theme: 'light' | 'dark'
  onToggleTheme: () => void
  onOpenSearch?: () => void
  healthStatus?: { status: string; version: string }
  isHealthLoading?: boolean
  isHealthError?: boolean
}

const PAGE_TITLES: Record<NavPage, { title: string; category: string }> = {
  overview: { title: 'Treasury Overview', category: 'Workspace' },
  obligations: { title: 'Payment Obligations', category: 'Workspace' },
  import: { title: 'Import & Ingestion', category: 'Workspace' },
  batches: { title: 'Payment Batches', category: 'Workspace' },
  analysis: { title: 'Multi-Provider Route Analysis', category: 'Workspace' },
  audit: { title: 'Compliance & Audit Trail', category: 'Governance' },
  ecosystem: { title: 'Ecosystem & Sponsors', category: 'Governance' },
  settings: { title: 'Settings & Appearance', category: 'Preferences' },
}

export const Topbar: React.FC<TopbarProps> = ({
  currentPage,
  theme,
  onToggleTheme,
  onOpenSearch,
  healthStatus,
  isHealthLoading,
  isHealthError,
}) => {
  const meta = PAGE_TITLES[currentPage] || { title: 'PUFI Enterprise', category: 'Platform' }

  return (
    <header
      style={{
        height: 64,
        background: 'var(--bg-surface)',
        borderBottom: '1px solid var(--border-base)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 28px',
        position: 'sticky',
        top: 0,
        zIndex: 40,
        transition: 'background var(--trans-normal), border-color var(--trans-normal)',
      }}
    >
      {/* Breadcrumb & Section Name */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <span style={{ fontSize: '0.82rem', color: 'var(--text-muted)', fontWeight: 500 }}>
          {meta.category}
        </span>
        <span style={{ color: 'var(--border-strong)', fontSize: '0.85rem' }}>/</span>
        <h2
          style={{
            margin: 0,
            fontSize: '1rem',
            fontWeight: 750,
            color: 'var(--text-primary)',
            letterSpacing: '-0.01em',
          }}
        >
          {meta.title}
        </h2>
      </div>

      {/* Right Controls Group */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
        {/* Quick Search trigger */}
        {onOpenSearch && (
          <button
            onClick={onOpenSearch}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              padding: '6px 12px',
              borderRadius: 'var(--radius-pill)',
              border: '1px solid var(--border-base)',
              background: 'var(--bg-subtle)',
              color: 'var(--text-secondary)',
              fontSize: '0.78rem',
              cursor: 'pointer',
              transition: 'all var(--trans-fast)',
            }}
          >
            <Search size={14} />
            <span>Search records...</span>
            <kbd
              style={{
                background: 'var(--bg-surface)',
                border: '1px solid var(--border-strong)',
                borderRadius: 4,
                padding: '1px 5px',
                fontSize: '0.68rem',
                fontFamily: 'monospace',
              }}
            >
              ⌘K
            </kbd>
          </button>
        )}

        {/* Backend Heartbeat */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            padding: '4px 10px',
            borderRadius: 'var(--radius-pill)',
            background: isHealthError
              ? 'var(--pufi-danger-bg)'
              : 'var(--pufi-success-bg)',
            border: `1px solid ${
              isHealthError ? 'var(--pufi-danger-border)' : 'var(--pufi-success-border)'
            }`,
            fontSize: '0.74rem',
            fontWeight: 650,
            color: isHealthError ? 'var(--pufi-danger-text)' : 'var(--pufi-success-text)',
          }}
          title={isHealthError ? 'Backend API unreachable' : `FastAPI v${healthStatus?.version || '0.1.0'} connected`}
        >
          <Activity size={12} />
          <span>
            {isHealthLoading ? 'Connecting…' : isHealthError ? 'Backend Disconnected' : 'API v0.1.0'}
          </span>
        </div>

        {/* PayPal Sandbox Live Indicator */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 7,
            padding: '4px 12px',
            borderRadius: 'var(--radius-pill)',
            background: 'var(--pufi-primary-light)',
            border: '1px solid rgba(22, 119, 255, 0.25)',
            fontSize: '0.75rem',
            fontWeight: 700,
            color: 'var(--pufi-primary)',
          }}
        >
          <span
            style={{
              width: 7,
              height: 7,
              borderRadius: '50%',
              background: '#1677FF',
              boxShadow: '0 0 6px #1677FF',
              display: 'inline-block',
              animation: 'pulseGlow 2s infinite',
            }}
          />
          <Shield size={13} />
          <span>PayPal Sandbox</span>
        </div>

        {/* Light / Dark Mode Switch */}
        <button
          onClick={onToggleTheme}
          style={{
            width: 34,
            height: 34,
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--border-base)',
            background: 'var(--bg-surface)',
            color: 'var(--text-secondary)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
            transition: 'all var(--trans-fast)',
          }}
          title={theme === 'dark' ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
        >
          {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
        </button>

        {/* GitHub Docs Link */}
        <a
          href="https://github.com/ayuvan/pufi"
          target="_blank"
          rel="noreferrer"
          style={{
            width: 34,
            height: 34,
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--border-base)',
            background: 'var(--bg-surface)',
            color: 'var(--text-secondary)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            textDecoration: 'none',
            transition: 'all var(--trans-fast)',
          }}
          title="GitHub Repository"
        >
          <ExternalLink size={15} />
        </a>
      </div>
    </header>
  )
}
