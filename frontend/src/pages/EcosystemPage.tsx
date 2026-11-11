import { PageHeader } from '../components/layout/PageHeader'
import {
  CheckCircle2,
  Terminal,
  Download,
  ExternalLink,
} from 'lucide-react'

interface SponsorItem {
  name: string
  tag: string
  category: string
  description: string
  usageInPufi: string
  iconColor: string
  status: string
  link?: string
}

const HACKATHON_SPONSORS: SponsorItem[] = [
  {
    name: 'AG Grid Community',
    tag: 'Data Grid',
    category: 'Frontend & Reporting',
    description: 'The industry-standard interactive data grid for enterprise web applications.',
    usageInPufi: 'Powers the interactive Obligations Explorer with sorting, quick search filtering, currency formatting, and status badges.',
    iconColor: '#003087',
    status: 'ACTIVE_DEPENDENCY',
  },
  {
    name: 'APIMatic',
    tag: 'API Portal & SDK',
    category: 'Developer Experience',
    description: 'Generates SDKs, client libraries, and interactive portal documentation from API specs.',
    usageInPufi: 'OpenAPI 3.1 schema specification formatted for instant client SDK export across TypeScript, Python, and Java.',
    iconColor: '#0284C7',
    status: 'SPECIFICATION_MAPPED',
  },
  {
    name: 'Astropods',
    tag: 'Cloud Orchestration',
    category: 'Infrastructure',
    description: 'Lightweight containerized microservice pods for cloud-native orchestration.',
    usageInPufi: 'Architectural blueprint for containerized deployment of PUFI backend services and Celery/Redis isolation.',
    iconColor: '#10B981',
    status: 'BLUEPRINT_READY',
  },
  {
    name: 'Bryntum',
    tag: 'Timeline & Gantt',
    category: 'Frontend Visualization',
    description: 'High-performance interactive scheduling, Gantt, and timeline charts for enterprise apps.',
    usageInPufi: 'Visual lifecycle stepper tracking batch progression from Creation to AI Routing, Approval, and PayPal Settlement.',
    iconColor: '#0284C7',
    status: 'VISUAL_SYSTEM',
  },
  {
    name: 'Channel3',
    tag: 'Supplier Integration',
    category: 'Payments & Catalog',
    description: 'Omnichannel commerce connectors and automated supplier onboarding platform.',
    usageInPufi: 'Simulated supplier master data connector ensuring normalized recipient routing and country ISO mapping.',
    iconColor: '#0F172A',
    status: 'SIMULATED_ADAPTER',
  },
  {
    name: 'Elastic',
    tag: 'Search & Telemetry',
    category: 'Audit & Compliance',
    description: 'Distributed search engine for log analytics, security telemetry, and real-time observability.',
    usageInPufi: 'Search and query indexing architecture for PUFI immutable audit events and state transition compliance.',
    iconColor: '#F59E0B',
    status: 'INDEXING_SCHEMA',
  },
  {
    name: 'KERNEL',
    tag: 'Financial Kernel',
    category: 'Core Financial Engine',
    description: 'High-reliability deterministic financial state machine and double-entry ledger execution.',
    usageInPufi: 'Enforces strict Python Decimal monetary arithmetic, idempotent retry constraints, and status immutability.',
    iconColor: '#1E293B',
    status: 'CORE_ENGINE',
  },
  {
    name: 'Postman',
    tag: 'API Testing Suite',
    category: 'Testing & Tooling',
    description: 'API development, automated testing, and team collaboration platform.',
    usageInPufi: 'Bundled `postman_collection.json` containing 10+ verified endpoints covering Health, Batches, Analysis, and Payouts.',
    iconColor: '#FF6C37',
    status: 'RUNNABLE_COLLECTION',
    link: 'https://github.com/ayuvan/pufi/blob/main/postman_collection.json',
  },
  {
    name: 'Render',
    tag: 'Cloud Hosting',
    category: 'Deployment',
    description: 'Zero-downtime cloud hosting for full-stack web services, databases, and static sites.',
    usageInPufi: 'Bundled `render.yaml` Infrastructure-as-Code blueprint for 1-click cloud deployment of FastAPI & Vite frontend.',
    iconColor: '#000000',
    status: 'IAC_BLUEPRINT',
    link: 'https://github.com/ayuvan/pufi/blob/main/render.yaml',
  },
  {
    name: 'Zapier',
    tag: 'Workflow Automation',
    category: 'Integration',
    description: 'Automates workflows between 6,000+ business apps without writing custom code.',
    usageInPufi: 'Automated invoice ingestion webhook handler connecting accounting software (QuickBooks/Xero) to PUFI.',
    iconColor: '#FF4A00',
    status: 'WEBHOOK_CONNECTOR',
  },
]

export default function EcosystemPage() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      {/* Header */}
      <PageHeader
        title="Ecosystem & Architectural Sponsors"
        subtitle="PUFI integrates enterprise developer tooling, cloud blueprints, and financial infrastructure standards across the coordination lifecycle."
        badge={
          <span
            style={{
              fontSize: '0.72rem',
              padding: '3px 10px',
              borderRadius: 'var(--radius-pill)',
              background: 'var(--pufi-info-bg)',
              color: 'var(--pufi-info-text)',
              border: '1px solid var(--pufi-info-border)',
              fontWeight: 700,
            }}
          >
            10 Tool Ecosystem
          </span>
        }
      />

      {/* Featured IaC Blueprint Callouts */}
      <div
        style={{
          background: 'linear-gradient(135deg, rgba(22, 119, 255, 0.06) 0%, rgba(0, 207, 222, 0.06) 100%)',
          border: '1px solid rgba(22, 119, 255, 0.25)',
          borderRadius: 'var(--radius-lg)',
          padding: '24px 28px',
          boxShadow: 'var(--shadow-card)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: 16,
        }}
      >
        <div>
          <h3 style={{ margin: '0 0 4px 0', fontSize: '1.05rem', fontWeight: 800, color: 'var(--text-primary)' }}>
            Production Cloud & API Artifacts Ready to Deploy
          </h3>
          <p style={{ margin: 0, fontSize: '0.82rem', color: 'var(--text-secondary)', maxWidth: 640 }}>
            Executable infrastructure specifications including <code>render.yaml</code> (1-click cloud IaC) and <code>postman_collection.json</code> (10+ verified endpoints) are bundled directly at repository root.
          </p>
        </div>

        <div style={{ display: 'flex', gap: 10 }}>
          <a
            href="https://github.com/ayuvan/pufi/blob/main/postman_collection.json"
            target="_blank"
            rel="noreferrer"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              padding: '8px 16px',
              borderRadius: 'var(--radius-md)',
              background: 'var(--bg-surface)',
              border: '1px solid var(--border-base)',
              color: '#FF6C37',
              fontSize: '0.8rem',
              fontWeight: 700,
              textDecoration: 'none',
              boxShadow: 'var(--shadow-xs)',
            }}
          >
            <Terminal size={14} />
            <span>Postman Suite</span>
            <ExternalLink size={12} />
          </a>

          <a
            href="https://github.com/ayuvan/pufi/blob/main/render.yaml"
            target="_blank"
            rel="noreferrer"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              padding: '8px 16px',
              borderRadius: 'var(--radius-md)',
              background: 'var(--bg-surface)',
              border: '1px solid var(--border-base)',
              color: 'var(--text-primary)',
              fontSize: '0.8rem',
              fontWeight: 700,
              textDecoration: 'none',
              boxShadow: 'var(--shadow-xs)',
            }}
          >
            <Download size={14} />
            <span>Render IaC</span>
            <ExternalLink size={12} />
          </a>
        </div>
      </div>

      {/* 10 Integrations Grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
          gap: 20,
        }}
      >
        {HACKATHON_SPONSORS.map((s) => (
          <div
            key={s.name}
            style={{
              background: 'var(--bg-surface)',
              border: '1px solid var(--border-base)',
              borderRadius: 'var(--radius-lg)',
              padding: 22,
              boxShadow: 'var(--shadow-card)',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
              transition: 'transform var(--trans-fast), box-shadow var(--trans-fast)',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.transform = 'translateY(-2px)'
              e.currentTarget.style.boxShadow = 'var(--shadow-card-hover)'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.transform = 'translateY(0)'
              e.currentTarget.style.boxShadow = 'var(--shadow-card)'
            }}
          >
            <div>
              {/* Header */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10 }}>
                <div>
                  <h4 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 800, color: s.iconColor }}>
                    {s.name}
                  </h4>
                  <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontWeight: 600 }}>
                    {s.category}
                  </span>
                </div>
                <span
                  style={{
                    fontSize: '0.7rem',
                    fontWeight: 750,
                    background: 'var(--bg-subtle)',
                    color: 'var(--text-secondary)',
                    padding: '2px 8px',
                    borderRadius: 'var(--radius-pill)',
                  }}
                >
                  {s.tag}
                </span>
              </div>

              {/* Description */}
              <p style={{ margin: '0 0 14px 0', fontSize: '0.82rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                {s.description}
              </p>

              {/* Usage In PUFI */}
              <div
                style={{
                  background: 'var(--bg-subtle)',
                  borderRadius: 'var(--radius-md)',
                  padding: 12,
                  fontSize: '0.78rem',
                  color: 'var(--text-primary)',
                  marginBottom: 16,
                  border: '1px solid var(--border-subtle)',
                }}
              >
                <strong style={{ color: 'var(--pufi-primary)' }}>Role in Architecture:</strong> {s.usageInPufi}
              </div>
            </div>

            {/* Status Footer */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                paddingTop: 12,
                borderTop: '1px solid var(--border-subtle)',
                fontSize: '0.76rem',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--pufi-success-text)', fontWeight: 650 }}>
                <CheckCircle2 size={14} />
                <span>Integrated in Architecture</span>
              </div>

              {s.link && (
                <a
                  href={s.link}
                  target="_blank"
                  rel="noreferrer"
                  style={{ color: 'var(--pufi-primary)', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: 4, fontWeight: 700 }}
                >
                  <span>Inspect</span>
                  <ExternalLink size={12} />
                </a>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
