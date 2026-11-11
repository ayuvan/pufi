import React, { useState, useEffect } from 'react'
import { AppSidebar, type NavPage } from './AppSidebar'
import { Topbar } from './Topbar'
import { useQuery } from '@tanstack/react-query'
import { fetchHealth, fetchBatches, fetchObligations } from '../../api/client'
import { ShieldAlert, ExternalLink, Sparkles } from 'lucide-react'

interface MainLayoutProps {
  currentPage: NavPage
  onNavigate: (page: NavPage) => void
  children: React.ReactNode
  onOpenSponsors?: () => void
}

export const MainLayout: React.FC<MainLayoutProps> = ({
  currentPage,
  onNavigate,
  children,
  onOpenSponsors,
}) => {
  // Theme state persisted in localStorage
  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    return (localStorage.getItem('pufi_theme') as 'light' | 'dark') || 'light'
  })

  // Collapsible sidebar state persisted in localStorage
  const [sidebarCollapsed, setSidebarCollapsed] = useState<boolean>(() => {
    return localStorage.getItem('pufi_sidebar_collapsed') === 'true'
  })

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('pufi_theme', theme)
  }, [theme])

  const toggleTheme = () => {
    setTheme((prev) => (prev === 'light' ? 'dark' : 'light'))
  }

  const toggleSidebarCollapse = () => {
    setSidebarCollapsed((prev) => {
      const next = !prev
      localStorage.setItem('pufi_sidebar_collapsed', String(next))
      return next
    })
  }

  // Health check query
  const { data: healthData, isLoading: isHealthLoading, isError: isHealthError } = useQuery({
    queryKey: ['health'],
    queryFn: fetchHealth,
    refetchInterval: 30_000,
  })

  // Quick summary counts for navigation badges
  const { data: batchesData } = useQuery({
    queryKey: ['batches'],
    queryFn: () => fetchBatches({ limit: 100 }),
  })

  const { data: obligationsData } = useQuery({
    queryKey: ['obligations', 0, 'DRAFT'],
    queryFn: () => fetchObligations({ limit: 1, status: 'DRAFT' }),
  })

  const batchCount = batchesData?.length || 0
  const draftObligationCount = obligationsData?.total || 0

  return (
    <div
      style={{
        display: 'flex',
        minHeight: '100vh',
        backgroundColor: 'var(--bg-app)',
        color: 'var(--text-primary)',
      }}
    >
      {/* Collapsible Left Navigation Sidebar */}
      <AppSidebar
        currentPage={currentPage}
        onNavigate={onNavigate}
        collapsed={sidebarCollapsed}
        onToggleCollapse={toggleSidebarCollapse}
        batchBadgeCount={batchCount}
        draftObligationCount={draftObligationCount}
      />

      {/* Main Content Area */}
      <div
        style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          minWidth: 0,
          overflowX: 'hidden',
        }}
      >
        {/* Polished Top Navigation Bar */}
        <Topbar
          currentPage={currentPage}
          theme={theme}
          onToggleTheme={toggleTheme}
          healthStatus={healthData}
          isHealthLoading={isHealthLoading}
          isHealthError={isHealthError}
        />

        {/* Dynamic Page Content */}
        <main
          className="animate-fade-in"
          style={{
            flex: 1,
            padding: '28px 32px 48px 32px',
            maxWidth: 1600,
            width: '100%',
            boxSizing: 'border-box',
            margin: '0 auto',
          }}
        >
          {children}
        </main>

        {/* Enterprise Fintech Footer */}
        <footer
          style={{
            borderTop: '1px solid var(--border-subtle)',
            background: 'var(--bg-surface)',
            padding: '16px 32px',
            fontSize: '0.76rem',
            color: 'var(--text-muted)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: 16,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <ShieldAlert size={14} color="#0070BA" />
            <span>
              <strong>PUFI FinTech Infrastructure</strong> • Operating under{' '}
              <span
                style={{
                  fontWeight: 700,
                  color: 'var(--pufi-primary)',
                  background: 'var(--pufi-primary-light)',
                  padding: '1px 6px',
                  borderRadius: 4,
                }}
              >
                PAYPAL SANDBOX
              </span>{' '}
              • Prototype environment with deterministic decimal ledger. No live funds move.
            </span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            {onOpenSponsors && (
              <button
                onClick={onOpenSponsors}
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: 'var(--pufi-primary)',
                  cursor: 'pointer',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 4,
                  fontSize: '0.76rem',
                  fontWeight: 650,
                }}
              >
                <Sparkles size={13} />
                <span>Sponsor Tech Stack</span>
              </button>
            )}
            <a
              href="https://github.com/ayuvan/pufi"
              target="_blank"
              rel="noreferrer"
              style={{
                color: 'var(--text-secondary)',
                textDecoration: 'none',
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4,
              }}
            >
              <span>GitHub</span>
              <ExternalLink size={12} />
            </a>
            <a
              href="https://developer.paypal.com/docs/api/payments.payouts-batch/v1/"
              target="_blank"
              rel="noreferrer"
              style={{
                color: 'var(--text-secondary)',
                textDecoration: 'none',
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4,
              }}
            >
              <span>PayPal Docs</span>
              <ExternalLink size={12} />
            </a>
          </div>
        </footer>
      </div>
    </div>
  )
}
