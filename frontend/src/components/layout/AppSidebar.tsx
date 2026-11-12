import React from 'react'
import {
  LayoutDashboard,
  FileText,
  UploadCloud,
  Layers,
  Cpu,
  ShieldCheck,
  Boxes,
  Settings,
  ChevronLeft,
  ChevronRight,
  Building2,
} from 'lucide-react'

export type NavPage =
  | 'overview'
  | 'obligations'
  | 'import'
  | 'batches'
  | 'analysis'
  | 'audit'
  | 'ecosystem'
  | 'settings'

interface AppSidebarProps {
  currentPage: NavPage
  onNavigate: (page: NavPage) => void
  collapsed: boolean
  onToggleCollapse: () => void
  batchBadgeCount?: number
  draftObligationCount?: number
}

interface NavItem {
  id: NavPage
  label: string
  icon: React.ReactNode
  badge?: string | number
  badgeColor?: string
}

export const AppSidebar: React.FC<AppSidebarProps> = ({
  currentPage,
  onNavigate,
  collapsed,
  onToggleCollapse,
  batchBadgeCount,
  draftObligationCount,
}) => {
  const workspaceItems: NavItem[] = [
    {
      id: 'overview',
      label: 'Overview',
      icon: <LayoutDashboard size={18} />,
    },
    {
      id: 'obligations',
      label: 'Payment Obligations',
      icon: <FileText size={18} />,
      badge: draftObligationCount && draftObligationCount > 0 ? draftObligationCount : undefined,
      badgeColor: 'var(--pufi-warning)',
    },
    {
      id: 'import',
      label: 'Import & Ingestion',
      icon: <UploadCloud size={18} />,
    },
    {
      id: 'batches',
      label: 'Payment Batches',
      icon: <Layers size={18} />,
      badge: batchBadgeCount && batchBadgeCount > 0 ? batchBadgeCount : undefined,
      badgeColor: 'var(--pufi-primary)',
    },
    {
      id: 'analysis',
      label: 'Route Analysis',
      icon: <Cpu size={18} />,
    },
  ]

  const governanceItems: NavItem[] = [
    {
      id: 'audit',
      label: 'Compliance & Audit',
      icon: <ShieldCheck size={18} />,
    },
    {
      id: 'ecosystem',
      label: 'Ecosystem & Sponsors',
      icon: <Boxes size={18} />,
      badge: '10',
      badgeColor: 'var(--pufi-info)',
    },
  ]

  const preferenceItems: NavItem[] = [
    {
      id: 'settings',
      label: 'Settings & Appearance',
      icon: <Settings size={18} />,
    },
  ]

  const renderNavGroup = (title: string, items: NavItem[]) => (
    <div style={{ marginBottom: 20 }}>
      {!collapsed && (
        <div
          style={{
            fontSize: '0.68rem',
            fontWeight: 750,
            color: 'var(--text-sidebar-muted)',
            textTransform: 'uppercase',
            letterSpacing: '0.08em',
            padding: '0 16px',
            marginBottom: 8,
          }}
        >
          {title}
        </div>
      )}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
        {items.map((item) => {
          const isActive = currentPage === item.id

          return (
            <button
              key={item.id}
              onClick={() => onNavigate(item.id)}
              title={collapsed ? item.label : undefined}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: collapsed ? 'center' : 'space-between',
                padding: collapsed ? '10px 0' : '10px 14px',
                borderRadius: 'var(--radius-md)',
                border: 'none',
                background: isActive ? 'var(--bg-sidebar-active)' : 'transparent',
                color: isActive ? 'var(--text-sidebar-active)' : 'var(--text-sidebar)',
                cursor: 'pointer',
                transition: 'background var(--trans-fast), color var(--trans-fast)',
                width: '100%',
                position: 'relative',
              }}
              onMouseEnter={(e) => {
                if (!isActive) {
                  e.currentTarget.style.backgroundColor = 'var(--bg-sidebar-hover)'
                  e.currentTarget.style.color = 'var(--text-sidebar-active)'
                }
              }}
              onMouseLeave={(e) => {
                if (!isActive) {
                  e.currentTarget.style.backgroundColor = 'transparent'
                  e.currentTarget.style.color = 'var(--text-sidebar)'
                }
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <span style={{ color: isActive ? '#42A5FF' : 'inherit', display: 'flex' }}>
                  {item.icon}
                </span>
                {!collapsed && (
                  <span
                    style={{
                      fontSize: '0.86rem',
                      fontWeight: isActive ? 650 : 500,
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {item.label}
                  </span>
                )}
              </div>

              {!collapsed && item.badge && (
                <span
                  style={{
                    fontSize: '0.68rem',
                    fontWeight: 750,
                    padding: '1px 6px',
                    borderRadius: 'var(--radius-pill)',
                    background: item.badgeColor || 'var(--pufi-primary)',
                    color: '#FFFFFF',
                  }}
                >
                  {item.badge}
                </span>
              )}

              {/* Active left indicator stripe */}
              {isActive && (
                <div
                  style={{
                    position: 'absolute',
                    left: 0,
                    top: '20%',
                    bottom: '20%',
                    width: 3,
                    borderRadius: '0 4px 4px 0',
                    background: '#1677FF',
                  }}
                />
              )}
            </button>
          )
        })}
      </div>
    </div>
  )

  return (
    <aside
      style={{
        width: collapsed ? 72 : 260,
        height: '100vh',
        position: 'sticky',
        top: 0,
        background: 'var(--bg-sidebar)',
        borderRight: '1px solid var(--border-sidebar)',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        transition: 'width var(--trans-normal)',
        zIndex: 50,
        flexShrink: 0,
      }}
    >
      {/* Top Branding Section */}
      <div>
        <div
          style={{
            height: 64,
            padding: collapsed ? '0 12px' : '0 20px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: collapsed ? 'center' : 'space-between',
            borderBottom: '1px solid var(--border-sidebar)',
          }}
        >
          <div
            onClick={() => onNavigate('overview')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 12,
              cursor: 'pointer',
            }}
          >
            {/* PayPal Double-P Emblem — Official geometry & 3-tone layering */}
            <svg
              style={{ width: 28, height: 32, flexShrink: 0 }}
              viewBox="0 0 100 115"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              {/* Rear P (Cyan/Light Blue) */}
              <path
                d="M31.2 97.4l11.1-70.4c0.8-5.1 5.2-8.9 10.4-8.9h23.7c14.2 0 24.1 9.2 22.1 24.1-1.9 14.5-14.1 23.1-28.3 23.1H59.5l-4.9 31.1c-0.4 2.2-2.3 3.8-4.5 3.8H34.4c-2.5 0-3.7-2.3-3.2-2.8z"
                fill="#0079C1"
              />
              {/* Front P (Deep PayPal Blue) */}
              <path
                d="M16.8 91.3L27.9 20.9c0.8-5.1 5.2-8.9 10.4-8.9h23.7c14.2 0 24.1 9.2 22.1 24.1-1.9 14.5-14.1 23.1-28.3 23.1H45.1l-4.9 31.1c-0.4 2.2-2.3 3.8-4.5 3.8H20.0c-2.5 0-3.7-2.3-3.2-2.7z"
                fill="#003087"
              />
              {/* Authentic dark intersection blend */}
              <path
                d="M45.1 59.2h10.7c14.2 0 26.4-8.6 28.3-23.1 0.4-3.1 0.1-5.9-0.9-8.4-2.6 13.5-14.1 22.6-28.3 22.6H45.1l-4.9 31.1c-0.4 2.2-2.3 3.8-4.5 3.8h-7.6l4.9-31.1c0.4-2.2 2.3-3.9 4.5-3.9z"
                fill="#002C6C"
                opacity="0.65"
              />
            </svg>

            {!collapsed && (
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span
                    style={{
                      fontWeight: 850,
                      fontSize: '1.05rem',
                      letterSpacing: '-0.02em',
                      color: '#FFFFFF',
                    }}
                  >
                    PUFI
                  </span>
                  <span
                    style={{
                      fontSize: '0.62rem',
                      fontWeight: 800,
                      background: 'linear-gradient(135deg, #1677FF, #00CFDE)',
                      color: '#FFFFFF',
                      padding: '1px 6px',
                      borderRadius: 'var(--radius-pill)',
                      letterSpacing: '0.05em',
                    }}
                  >
                    ENTERPRISE
                  </span>
                </div>
                <div style={{ fontSize: '0.66rem', color: 'var(--text-sidebar-muted)' }}>
                  Treasury Coordination
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Navigation list */}
        <div style={{ padding: collapsed ? '16px 8px' : '16px 12px', overflowY: 'auto' }}>
          {renderNavGroup('Workspace', workspaceItems)}
          {renderNavGroup('Governance', governanceItems)}
          {renderNavGroup('Preferences', preferenceItems)}
        </div>
      </div>

      {/* Bottom Profile & Collapse Toggle */}
      <div style={{ borderTop: '1px solid var(--border-sidebar)', padding: '12px' }}>
        {!collapsed && (
          <div
            style={{
              padding: '10px 12px',
              borderRadius: 'var(--radius-md)',
              background: 'var(--bg-sidebar-hover)',
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              marginBottom: 10,
            }}
          >
            <div
              style={{
                width: 32,
                height: 32,
                borderRadius: 'var(--radius-md)',
                background: 'linear-gradient(135deg, #1677FF, #101C32)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#FFF',
                flexShrink: 0,
              }}
            >
              <Building2 size={16} />
            </div>
            <div style={{ overflow: 'hidden' }}>
              <div
                style={{
                  fontSize: '0.82rem',
                  fontWeight: 700,
                  color: '#FFFFFF',
                  whiteSpace: 'nowrap',
                  textOverflow: 'ellipsis',
                  overflow: 'hidden',
                }}
              >
                ACME Corp
              </div>
              <div
                style={{
                  fontSize: '0.7rem',
                  color: 'var(--text-sidebar-muted)',
                  whiteSpace: 'nowrap',
                  textOverflow: 'ellipsis',
                  overflow: 'hidden',
                }}
              >
                Global Treasury · Controller
              </div>
            </div>
          </div>
        )}

        <button
          onClick={onToggleCollapse}
          style={{
            width: '100%',
            height: 32,
            borderRadius: 'var(--radius-sm)',
            border: 'none',
            background: 'transparent',
            color: 'var(--text-sidebar-muted)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
            transition: 'background var(--trans-fast), color var(--trans-fast)',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.backgroundColor = 'var(--bg-sidebar-hover)'
            e.currentTarget.style.color = '#FFFFFF'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.backgroundColor = 'transparent'
            e.currentTarget.style.color = 'var(--text-sidebar-muted)'
          }}
          title={collapsed ? 'Expand Sidebar' : 'Collapse Sidebar'}
        >
          {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
        </button>
      </div>
    </aside>
  )
}
