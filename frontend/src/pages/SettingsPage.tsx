import { useState } from 'react'
import { PageHeader } from '../components/layout/PageHeader'
import {
  Sun,
  Moon,
  Shield,
  Layers,
  CheckCircle2,
  Palette,
} from 'lucide-react'

export default function SettingsPage() {
  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    return (localStorage.getItem('pufi_theme') as 'light' | 'dark') || 'light'
  })

  const [sidebarCollapsed, setSidebarCollapsed] = useState<boolean>(() => {
    return localStorage.getItem('pufi_sidebar_collapsed') === 'true'
  })

  const [tabularDigits, setTabularDigits] = useState<boolean>(() => {
    return localStorage.getItem('pufi_tabular_digits') !== 'false'
  })

  const handleThemeChange = (newTheme: 'light' | 'dark') => {
    setTheme(newTheme)
    document.documentElement.setAttribute('data-theme', newTheme)
    localStorage.setItem('pufi_theme', newTheme)
  }

  const handleSidebarChange = (collapsed: boolean) => {
    setSidebarCollapsed(collapsed)
    localStorage.setItem('pufi_sidebar_collapsed', String(collapsed))
  }

  const handleTabularChange = (tabular: boolean) => {
    setTabularDigits(tabular)
    localStorage.setItem('pufi_tabular_digits', String(tabular))
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24, maxWidth: 960 }}>
      {/* Header */}
      <PageHeader
        title="Settings & Appearance"
        subtitle="Manage client-side workstation preferences, theme styling, and financial display parameters."
        badge={
          <span
            style={{
              fontSize: '0.72rem',
              padding: '3px 10px',
              borderRadius: 'var(--radius-pill)',
              background: 'var(--bg-subtle)',
              color: 'var(--text-secondary)',
              border: '1px solid var(--border-base)',
              fontWeight: 700,
            }}
          >
            Local Workstation
          </span>
        }
      />

      {/* Appearance Section */}
      <div
        style={{
          background: 'var(--bg-surface)',
          border: '1px solid var(--border-base)',
          borderRadius: 'var(--radius-lg)',
          padding: 24,
          boxShadow: 'var(--shadow-card)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
          <Palette size={18} color="var(--pufi-primary)" />
          <h3 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 750, color: 'var(--text-primary)' }}>
            Appearance & Visual Theme
          </h3>
        </div>

        <p style={{ margin: '0 0 16px 0', fontSize: '0.84rem', color: 'var(--text-secondary)' }}>
          Select your preferred visual mode. The default is Premium Hybrid Fintech with high-contrast text and navy navigation.
        </p>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 16 }}>
          {/* Light Theme Card */}
          <div
            onClick={() => handleThemeChange('light')}
            style={{
              border: `2px solid ${theme === 'light' ? 'var(--pufi-primary)' : 'var(--border-base)'}`,
              borderRadius: 'var(--radius-md)',
              padding: 16,
              background: '#FFFFFF',
              color: '#17243A',
              cursor: 'pointer',
              display: 'flex',
              flexDirection: 'column',
              gap: 8,
              boxShadow: theme === 'light' ? 'var(--shadow-card-hover)' : 'var(--shadow-xs)',
              transition: 'all var(--trans-fast)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 700, fontSize: '0.9rem' }}>
                <Sun size={16} color="#E9A23B" />
                <span>Light / Hybrid</span>
              </div>
              {theme === 'light' && <CheckCircle2 size={16} color="var(--pufi-primary)" />}
            </div>
            <div style={{ fontSize: '0.76rem', color: '#75839A' }}>
              Deep navy sidebar with clean off-white workspace canvas and crisp typography.
            </div>
          </div>

          {/* Dark Theme Card */}
          <div
            onClick={() => handleThemeChange('dark')}
            style={{
              border: `2px solid ${theme === 'dark' ? 'var(--pufi-primary)' : 'var(--border-base)'}`,
              borderRadius: 'var(--radius-md)',
              padding: 16,
              background: '#121D33',
              color: '#F1F5F9',
              cursor: 'pointer',
              display: 'flex',
              flexDirection: 'column',
              gap: 8,
              boxShadow: theme === 'dark' ? 'var(--shadow-card-hover)' : 'var(--shadow-xs)',
              transition: 'all var(--trans-fast)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 700, fontSize: '0.9rem' }}>
                <Moon size={16} color="#42A5FF" />
                <span>Enterprise Dark</span>
              </div>
              {theme === 'dark' && <CheckCircle2 size={16} color="var(--pufi-primary)" />}
            </div>
            <div style={{ fontSize: '0.76rem', color: '#94A3B8' }}>
              Midnight blue dark canvas with subdued glow borders designed for low-light trading desks.
            </div>
          </div>
        </div>
      </div>

      {/* Navigation Preferences */}
      <div
        style={{
          background: 'var(--bg-surface)',
          border: '1px solid var(--border-base)',
          borderRadius: 'var(--radius-lg)',
          padding: 24,
          boxShadow: 'var(--shadow-card)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
          <Layers size={18} color="var(--pufi-primary)" />
          <h3 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 750, color: 'var(--text-primary)' }}>
            Workspace Layout & Navigation
          </h3>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 0', borderBottom: '1px solid var(--border-subtle)' }}>
          <div>
            <div style={{ fontSize: '0.86rem', fontWeight: 700, color: 'var(--text-primary)' }}>
              Collapsed Sidebar by Default
            </div>
            <div style={{ fontSize: '0.76rem', color: 'var(--text-secondary)' }}>
              Maximize workspace canvas by keeping the left sidebar collapsed to icon-only mode.
            </div>
          </div>
          <input
            type="checkbox"
            checked={sidebarCollapsed}
            onChange={(e) => handleSidebarChange(e.target.checked)}
            style={{ width: 18, height: 18, cursor: 'pointer' }}
          />
        </div>

        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 0' }}>
          <div>
            <div style={{ fontSize: '0.86rem', fontWeight: 700, color: 'var(--text-primary)' }}>
              Tabular Financial Numerals
            </div>
            <div style={{ fontSize: '0.76rem', color: 'var(--text-secondary)' }}>
              Enforce monospaced numeral glyph alignment across all monetary balance columns.
            </div>
          </div>
          <input
            type="checkbox"
            checked={tabularDigits}
            onChange={(e) => handleTabularChange(e.target.checked)}
            style={{ width: 18, height: 18, cursor: 'pointer' }}
          />
        </div>
      </div>

      {/* Environment & Financial Safeguards Disclosure */}
      <div
        style={{
          background: 'var(--bg-surface)',
          border: '1px solid var(--border-base)',
          borderRadius: 'var(--radius-lg)',
          padding: 24,
          boxShadow: 'var(--shadow-card)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
          <Shield size={18} color="var(--pufi-info-text)" />
          <h3 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 750, color: 'var(--text-primary)' }}>
            Financial & Sandbox Safeguards
          </h3>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 12, fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
          <div style={{ display: 'flex', gap: 10 }}>
            <span style={{ color: 'var(--pufi-primary)', fontWeight: 800 }}>•</span>
            <div>
              <strong>PayPal Sandbox Environment:</strong> All payout executions are routed strictly to PayPal Sandbox test accounts. No real fiat funds are transferred.
            </div>
          </div>

          <div style={{ display: 'flex', gap: 10 }}>
            <span style={{ color: 'var(--pufi-primary)', fontWeight: 800 }}>•</span>
            <div>
              <strong>Deterministic Decimal Calculations:</strong> All monetary amounts remain string Decimals to avoid binary floating-point roundoff errors.
            </div>
          </div>

          <div style={{ display: 'flex', gap: 10 }}>
            <span style={{ color: 'var(--pufi-primary)', fontWeight: 800 }}>•</span>
            <div>
              <strong>Gemini AI Advisory Boundary:</strong> Generative AI routing recommendations are strictly non-authoritative decision support. AI never executes payment disbursements.
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
