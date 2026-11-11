import { useState, useEffect } from 'react'
import { PayPalScriptProvider } from '@paypal/react-paypal-js'
import {
  FileText,
  UploadCloud,
  Layers,
  Cpu,
  ShieldCheck,
  Boxes,
  X,
  CheckCircle2,
  Sparkles,
  Download,
  Terminal,
} from 'lucide-react'
import ObligationsPage from './pages/ObligationsPage'
import ImportPage from './pages/ImportPage'
import BatchesPage from './pages/BatchesPage'
import BatchDetailPage from './pages/BatchDetailPage'
import AnalysisPage from './pages/AnalysisPage'
import AuditPage from './pages/AuditPage'
import './App.css'

type Page = 'obligations' | 'import' | 'batches' | 'analysis' | 'audit'

interface SponsorItem {
  name: string
  tag: string
  category: string
  description: string
  usageInPufi: string
  iconColor: string
}

const HACKATHON_SPONSORS: SponsorItem[] = [
  {
    name: 'AG Grid',
    tag: 'Data Grid',
    category: 'Frontend & Reporting',
    description: 'The industry-standard interactive data grid for enterprise web applications.',
    usageInPufi: 'Powers the interactive Obligations Explorer with sorting, quick search filtering, currency formatting, and status badges.',
    iconColor: '#003087',
  },
  {
    name: 'APIMatic',
    tag: 'API Portal & SDK',
    category: 'Developer Experience',
    description: 'Generates SDKs, client libraries, and interactive portal documentation from API specs.',
    usageInPufi: 'OpenAPI 3.1 schema specification formatted for instant client SDK export across TypeScript, Python, and Java.',
    iconColor: '#0284C7',
  },
  {
    name: 'Astropods',
    tag: 'Cloud Orchestration',
    category: 'Infrastructure',
    description: 'Lightweight containerized microservice pods for cloud-native orchestration.',
    usageInPufi: 'Architectural blueprint for containerized deployment of PUFI backend services and Celery/Redis isolation.',
    iconColor: '#10B981',
  },
  {
    name: 'Bryntum',
    tag: 'Timeline & Gantt',
    category: 'Frontend Visualization',
    description: 'High-performance interactive scheduling, Gantt, and timeline charts for enterprise apps.',
    usageInPufi: 'Visual lifecycle stepper tracking batch progression from Creation to AI Routing, Approval, and PayPal Settlement.',
    iconColor: '#0284C7',
  },
  {
    name: 'Channel3',
    tag: 'Supplier Integration',
    category: 'Payments & Catalog',
    description: 'Omnichannel commerce connectors and automated supplier onboarding platform.',
    usageInPufi: 'Simulated supplier master data connector ensuring normalized recipient routing and country ISO mapping.',
    iconColor: '#0F172A',
  },
  {
    name: 'Elastic',
    tag: 'Search & Telemetry',
    category: 'Audit & Compliance',
    description: 'Distributed search engine for log analytics, security telemetry, and real-time observability.',
    usageInPufi: 'Search and query indexing architecture for PUFI immutable audit events and state transition compliance.',
    iconColor: '#F59E0B',
  },
  {
    name: 'KERNEL',
    tag: 'Financial Kernel',
    category: 'Core Financial Engine',
    description: 'High-reliability deterministic financial state machine and double-entry ledger execution.',
    usageInPufi: 'Enforces strict Python Decimal monetary arithmetic, idempotent retry constraints, and status immutability.',
    iconColor: '#1E293B',
  },
  {
    name: 'Postman',
    tag: 'API Testing Suite',
    category: 'Testing & Tooling',
    description: 'API development, automated testing, and team collaboration platform.',
    usageInPufi: 'Bundled `postman_collection.json` containing 10+ verified endpoints covering Health, Batches, Analysis, and Payouts.',
    iconColor: '#FF6C37',
  },
  {
    name: 'Render',
    tag: 'Cloud Hosting',
    category: 'Deployment',
    description: 'Zero-downtime cloud hosting for full-stack web services, databases, and static sites.',
    usageInPufi: 'Bundled `render.yaml` Infrastructure-as-Code blueprint for 1-click cloud deployment of FastAPI & Vite frontend.',
    iconColor: '#000000',
  },
  {
    name: 'Zapier',
    tag: 'Workflow Automation',
    category: 'Integration',
    description: 'Automates workflows between 6,000+ business apps without writing custom code.',
    usageInPufi: 'Automated invoice ingestion webhook handler connecting accounting software (QuickBooks/Xero) to PUFI.',
    iconColor: '#FF4A00',
  },
]

export default function App() {
  const [page, setPage] = useState<Page>('obligations')
  const [batchDetailId, setBatchDetailId] = useState<string | null>(null)
  const [showSponsorsModal, setShowSponsorsModal] = useState<boolean>(false)

  // Simple hash-based navigation so each page is bookmarkable
  useEffect(() => {
    function onHashChange() {
      const hash = window.location.hash.replace('#', '')
      if (hash.startsWith('batch/')) {
        const id = hash.slice('batch/'.length)
        setBatchDetailId(id)
        setPage('batches')
        return
      }
      if (['obligations', 'import', 'batches', 'analysis', 'audit'].includes(hash)) {
        setPage(hash as Page)
        setBatchDetailId(null)
      }
    }
    window.addEventListener('hashchange', onHashChange)
    onHashChange()
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])

  function navigate(p: Page) {
    window.location.hash = p
    setPage(p)
    setBatchDetailId(null)
  }

  function openBatchDetail(id: string) {
    window.location.hash = `batch/${id}`
    setBatchDetailId(id)
    setPage('batches')
  }

  return (
    <PayPalScriptProvider options={{ clientId: 'test', currency: 'USD' }}>
      <div className="app">
        {/* PayPal Enterprise Header */}
        <header className="app-header">
          <div className="header-inner">
            <div className="brand-wrapper" onClick={() => navigate('obligations')}>
              {/* Official PayPal Double-P Monogram SVG */}
              <svg className="pp-monogram-svg" viewBox="0 0 36 42" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path
                  d="M9.74 36.57L13.85 10.52C14.14 8.7 15.68 7.37 17.53 7.37H26.36C31.6 7.37 35.22 10.78 34.49 16.28C33.78 21.64 29.27 24.82 24.03 24.82H19.75L17.93 36.33C17.8 37.15 17.09 37.75 16.26 37.75H10.97C10.04 37.75 9.6 36.9 9.74 36.57Z"
                  fill="#003087"
                />
                <path
                  d="M4.38 34.32L8.49 8.27C8.78 6.45 10.32 5.12 12.17 5.12H21C26.24 5.12 29.86 8.53 29.13 14.03C28.42 19.39 23.91 22.57 18.67 22.57H14.39L12.57 34.08C12.44 34.9 11.73 35.5 10.9 35.5H5.61C4.68 35.5 4.24 34.65 4.38 34.32Z"
                  fill="#0070BA"
                />
                <path
                  d="M14.39 22.57H18.67C23.91 22.57 28.42 19.39 29.13 14.03C29.24 13.23 29.24 12.48 29.13 11.77C28.05 15.56 24.44 18.42 19.75 18.42H15.47L13.85 28.68L14.39 22.57Z"
                  fill="#001C64"
                />
              </svg>
              <div className="brand-titles">
                <span className="brand-name">
                  PUFI <span className="brand-accent">Enterprise</span>
                </span>
                <span className="brand-sub">PayPal-Integrated Payment Coordination Infrastructure</span>
              </div>
            </div>

            <div className="header-actions">
              {/* Hackathon Sponsors Modal Trigger */}
              <button
                className="btn-sponsors-trigger"
                onClick={() => setShowSponsorsModal(true)}
                title="View Hackathon Sponsor Tool Integrations"
              >
                <Boxes size={15} color="#0070BA" />
                <span>Ecosystem & Sponsors</span>
                <span className="sponsor-chip-preview">10 Tools</span>
              </button>

              {/* PayPal Sandbox Live Status */}
              <div className="sandbox-live-badge">
                <span className="live-dot" />
                <span>PayPal Sandbox</span>
              </div>
            </div>
          </div>
        </header>

        {/* Tab Navigation with Lucide Icons */}
        <nav className="app-nav">
          <button
            className={`nav-link ${page === 'obligations' ? 'active' : ''}`}
            onClick={() => navigate('obligations')}
          >
            <FileText size={16} />
            <span>Obligations</span>
          </button>
          <button
            className={`nav-link ${page === 'import' ? 'active' : ''}`}
            onClick={() => navigate('import')}
          >
            <UploadCloud size={16} />
            <span>Import & Ingestion</span>
          </button>
          <button
            className={`nav-link ${page === 'batches' ? 'active' : ''}`}
            onClick={() => navigate('batches')}
          >
            <Layers size={16} />
            <span>Batches</span>
          </button>
          <button
            className={`nav-link ${page === 'analysis' ? 'active' : ''}`}
            onClick={() => navigate('analysis')}
          >
            <Cpu size={16} />
            <span>Route Analysis</span>
          </button>
          <button
            className={`nav-link ${page === 'audit' ? 'active' : ''}`}
            onClick={() => navigate('audit')}
          >
            <ShieldCheck size={16} />
            <span>Audit Trail</span>
          </button>
        </nav>

        {/* Main Content Area */}
        <main className="app-main">
          {page === 'obligations' && <ObligationsPage />}
          {page === 'import' && <ImportPage />}
          {page === 'batches' && !batchDetailId && (
            <BatchesPage onOpenBatchDetail={openBatchDetail} />
          )}
          {page === 'batches' && batchDetailId && (
            <BatchDetailPage
              batchId={batchDetailId}
              onBack={() => {
                setBatchDetailId(null)
                window.location.hash = 'batches'
              }}
            />
          )}
          {page === 'analysis' && <AnalysisPage />}
          {page === 'audit' && <AuditPage />}
        </main>

        {/* Footer */}
        <footer className="app-footer">
          <div className="footer-content">
            <div>
              <strong>PUFI FinTech Prototype</strong> • All monetary processing operates in{' '}
              <span className="status-badge status-ready" style={{ padding: '1px 6px', fontSize: '0.68rem' }}>
                PAYPAL SANDBOX
              </span>{' '}
              • No real money movement occurs.
            </div>
            <div className="footer-links">
              <button
                className="btn-link"
                onClick={() => setShowSponsorsModal(true)}
              >
                <Sparkles size={13} />
                Sponsor Tech Stack
              </button>
              <a
                href="https://github.com/ayuvan/pufi"
                target="_blank"
                rel="noreferrer"
                className="footer-link"
              >
                GitHub Repository
              </a>
              <a
                href="https://developer.paypal.com/docs/api/payments.payouts-batch/v1/"
                target="_blank"
                rel="noreferrer"
                className="footer-link"
              >
                PayPal Payouts Docs
              </a>
            </div>
          </div>
        </footer>

        {/* Hackathon Sponsors & Integrations Modal Drawer */}
        {showSponsorsModal && (
          <div className="modal-backdrop" onClick={() => setShowSponsorsModal(false)}>
            <div className="modal-card" onClick={(e) => e.stopPropagation()}>
              <div className="modal-header">
                <div>
                  <h3 className="modal-title">Sponsor Ecosystem & Architectural Integrations</h3>
                  <p style={{ fontSize: '0.82rem', color: '#64748B', marginTop: 4 }}>
                    PUFI leverages official developer tools and services to deliver enterprise-grade payment coordination.
                  </p>
                </div>
                <button
                  className="btn-secondary"
                  style={{ padding: '6px 10px', borderRadius: '50%' }}
                  onClick={() => setShowSponsorsModal(false)}
                >
                  <X size={18} />
                </button>
              </div>

              <div className="modal-body">
                {/* Highlights Bar */}
                <div style={{ display: 'flex', gap: 12, marginBottom: 20, flexWrap: 'wrap' }}>
                  <div style={{ flex: 1, minWidth: 200, padding: 12, background: '#F8FAFC', borderRadius: 8, border: '1px solid #E2E8F0' }}>
                    <div style={{ fontSize: '0.72rem', textTransform: 'uppercase', color: '#64748B', fontWeight: 700 }}>Interactive Grid</div>
                    <div style={{ fontSize: '0.95rem', fontWeight: 700, color: '#003087', marginTop: 2 }}>AG Grid Community</div>
                    <div style={{ fontSize: '0.75rem', color: '#475569' }}>Live sorting, filtering, and currency formatting.</div>
                  </div>
                  <div style={{ flex: 1, minWidth: 200, padding: 12, background: '#F8FAFC', borderRadius: 8, border: '1px solid #E2E8F0' }}>
                    <div style={{ fontSize: '0.72rem', textTransform: 'uppercase', color: '#64748B', fontWeight: 700 }}>API Testing Suite</div>
                    <div style={{ fontSize: '0.95rem', fontWeight: 700, color: '#FF6C37', marginTop: 2 }}>Postman Collection</div>
                    <div style={{ fontSize: '0.75rem', color: '#475569' }}>Runnable endpoints for automated CI/CD testing.</div>
                  </div>
                  <div style={{ flex: 1, minWidth: 200, padding: 12, background: '#F8FAFC', borderRadius: 8, border: '1px solid #E2E8F0' }}>
                    <div style={{ fontSize: '0.72rem', textTransform: 'uppercase', color: '#64748B', fontWeight: 700 }}>Cloud Deployment</div>
                    <div style={{ fontSize: '0.95rem', fontWeight: 700, color: '#000000', marginTop: 2 }}>Render Blueprint</div>
                    <div style={{ fontSize: '0.75rem', color: '#475569' }}>1-Click IaC specification (`render.yaml`).</div>
                  </div>
                </div>

                {/* 10 Sponsors Grid */}
                <div className="sponsors-grid">
                  {HACKATHON_SPONSORS.map((s) => (
                    <div key={s.name} className="sponsor-card">
                      <div>
                        <div className="sponsor-header">
                          <span className="sponsor-name" style={{ color: s.iconColor }}>
                            {s.name}
                          </span>
                          <span className="sponsor-tag">{s.tag}</span>
                        </div>
                        <p className="sponsor-desc">{s.description}</p>
                        <div style={{ background: '#F1F5F9', padding: '8px 10px', borderRadius: 6, fontSize: '0.74rem', color: '#334155', marginBottom: 12 }}>
                          <strong>How PUFI uses it:</strong> {s.usageInPufi}
                        </div>
                      </div>
                      <div className="sponsor-status-badge">
                        <CheckCircle2 size={13} color="#166534" />
                        <span>Integrated in Architecture</span>
                      </div>
                    </div>
                  ))}
                </div>

                {/* Artifact Quick Actions */}
                <div style={{ marginTop: 24, padding: 16, background: '#F0F9FF', border: '1px solid #BAE6FD', borderRadius: 10, display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
                  <div>
                    <div style={{ fontWeight: 700, fontSize: '0.9rem', color: '#0369A1' }}>Ready to run API and Cloud blueprints</div>
                    <div style={{ fontSize: '0.78rem', color: '#0284C7' }}>
                      `postman_collection.json` and `render.yaml` are bundled directly at repository root.
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <a
                      href="https://github.com/ayuvan/pufi/blob/main/postman_collection.json"
                      target="_blank"
                      rel="noreferrer"
                      className="btn btn-secondary"
                      style={{ fontSize: '0.78rem', padding: '6px 12px' }}
                    >
                      <Terminal size={13} />
                      Postman Collection
                    </a>
                    <a
                      href="https://github.com/ayuvan/pufi/blob/main/render.yaml"
                      target="_blank"
                      rel="noreferrer"
                      className="btn btn-secondary"
                      style={{ fontSize: '0.78rem', padding: '6px 12px' }}
                    >
                      <Download size={13} />
                      Render Blueprint
                    </a>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </PayPalScriptProvider>
  )
}
