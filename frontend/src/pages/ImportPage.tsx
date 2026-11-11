import { useState, useRef } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
  importObligations,
  type ImportRowResult,
  type ObligationImportRow,
} from '../api/client'
import { PageHeader } from '../components/layout/PageHeader'
import { StatusBadge } from '../components/common/StatusBadge'
import {
  UploadCloud,
  FileCode,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Zap,
} from 'lucide-react'

function parseJsonRows(text: string): ObligationImportRow[] | string {
  try {
    const parsed = JSON.parse(text)
    if (!Array.isArray(parsed)) return 'JSON root must be an array of obligation row objects.'
    return parsed as ObligationImportRow[]
  } catch (e) {
    return `Invalid JSON syntax: ${(e as Error).message}`
  }
}

const EXAMPLE_JSON = JSON.stringify(
  [
    {
      supplier_reference: 'SUP-001',
      invoice_reference: `INV-2027-${Math.floor(100 + Math.random() * 900)}`,
      amount: '1250.00',
      currency: 'USD',
      due_at: '2027-01-31',
      notes: 'Q1 services via Zapier Webhook sync',
    },
    {
      supplier_reference: 'SUP-002',
      invoice_reference: `INV-2027-${Math.floor(100 + Math.random() * 900)}`,
      amount: '800.50',
      currency: 'EUR',
      due_at: '2027-02-15',
      notes: 'Cloud infrastructure support package',
    },
    {
      supplier_reference: 'SUP-003',
      invoice_reference: `INV-2027-${Math.floor(100 + Math.random() * 900)}`,
      amount: '3150.00',
      currency: 'GBP',
      due_at: '2027-03-01',
      notes: 'Hardware procurement (Channel3 Sync)',
    },
  ],
  null,
  2
)

export default function ImportPage() {
  const [jsonText, setJsonText] = useState('')
  const [parseError, setParseError] = useState<string | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [showZapierGuide, setShowZapierGuide] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const queryClient = useQueryClient()

  const mutation = useMutation({
    mutationFn: (rows: ObligationImportRow[]) => importObligations(rows),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['obligations'] })
    },
  })

  function handleLoadExample() {
    setJsonText(EXAMPLE_JSON)
    setParseError(null)
    mutation.reset()
  }

  function handleImport() {
    setParseError(null)
    mutation.reset()
    const result = parseJsonRows(jsonText)
    if (typeof result === 'string') {
      setParseError(result)
      return
    }
    if (result.length === 0) {
      setParseError('The array is empty. Please provide at least one obligation row.')
      return
    }
    mutation.mutate(result)
  }

  function handleFileRead(file: File) {
    if (!file.name.endsWith('.json')) {
      setParseError('Only .json files are supported by the backend.')
      return
    }
    const reader = new FileReader()
    reader.onload = (e) => {
      const content = e.target?.result as string
      setJsonText(content)
      setParseError(null)
      mutation.reset()
    }
    reader.onerror = () => setParseError('Failed to read selected file.')
    reader.readAsText(file)
  }

  const importResult = mutation.data

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      {/* Header */}
      <PageHeader
        title="Import & Ingestion"
        subtitle="Automated batch ingestion of supplier payment obligations with real-time JSON validation and cryptographic duplicate prevention."
        badge={
          <span
            style={{
              fontSize: '0.72rem',
              padding: '3px 10px',
              borderRadius: 'var(--radius-pill)',
              background: 'var(--pufi-primary-light)',
              color: 'var(--pufi-primary)',
              border: '1px solid rgba(22,119,255,0.25)',
              fontWeight: 700,
            }}
          >
            Sha256 Duplicate Guard
          </span>
        }
        actions={
          <div style={{ display: 'flex', gap: 10 }}>
            <button
              onClick={() => setShowZapierGuide(!showZapierGuide)}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                padding: '8px 14px',
                borderRadius: 'var(--radius-md)',
                background: 'var(--bg-surface)',
                border: '1px solid var(--border-base)',
                fontSize: '0.82rem',
                fontWeight: 650,
                color: 'var(--text-primary)',
                cursor: 'pointer',
              }}
            >
              <Zap size={15} color="#FF4A00" />
              <span>{showZapierGuide ? 'Hide Webhook Guide' : 'Zapier Webhook Guide'}</span>
            </button>
            <button
              onClick={handleLoadExample}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                padding: '8px 14px',
                borderRadius: 'var(--radius-md)',
                background: 'var(--bg-subtle)',
                border: '1px solid var(--border-subtle)',
                fontSize: '0.82rem',
                fontWeight: 650,
                color: 'var(--text-primary)',
                cursor: 'pointer',
              }}
            >
              <FileCode size={15} color="var(--pufi-primary)" />
              <span>Load Sample Invoices</span>
            </button>
          </div>
        }
      />

      {/* Zapier / ERP Webhook Integration Callout */}
      {showZapierGuide && (
        <div
          style={{
            background: 'var(--bg-surface)',
            border: '1px solid #FFD4C2',
            borderRadius: 'var(--radius-lg)',
            padding: '20px 24px',
            boxShadow: 'var(--shadow-card)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
            <Zap size={20} color="#FF4A00" />
            <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 750, color: '#9A2A00' }}>
              Zapier & Accounting ERP Webhook Connector
            </h3>
          </div>
          <p style={{ margin: '0 0 12px 0', fontSize: '0.84rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
            PUFI supports automated ingestion from QuickBooks, Xero, NetSuite, and Stripe via Zapier webhooks.
            Configure your Zap to transmit raw invoice JSON directly to <code>POST /api/v1/obligations/import</code>.
          </p>
          <div
            style={{
              background: 'var(--bg-subtle)',
              padding: 12,
              borderRadius: 'var(--radius-sm)',
              fontFamily: 'monospace',
              fontSize: '0.78rem',
              color: 'var(--text-primary)',
              overflowX: 'auto',
            }}
          >
            curl -X POST https://your-pufi-instance.com/api/v1/obligations/import -H &quot;Content-Type: application/json&quot; -d &apos;[...row items]&apos;
          </div>
        </div>
      )}

      {/* Main Grid: Upload & Editor */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(460px, 1fr))',
          gap: 24,
        }}
      >
        {/* Left: Drag-and-Drop Area & Formats */}
        <div
          style={{
            background: 'var(--bg-surface)',
            border: '1px solid var(--border-base)',
            borderRadius: 'var(--radius-lg)',
            padding: 24,
            boxShadow: 'var(--shadow-card)',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
          }}
        >
          <div>
            <h3 style={{ margin: '0 0 6px 0', fontSize: '1.05rem', fontWeight: 750, color: 'var(--text-primary)' }}>
              Upload JSON Invoice File
            </h3>
            <p style={{ margin: '0 0 18px 0', fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
              Drag and drop an export from your ERP, or click to browse local filesystem.
            </p>

            {/* Drop Zone */}
            <div
              onDragOver={(e) => {
                e.preventDefault()
                setIsDragging(true)
              }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={(e) => {
                e.preventDefault()
                setIsDragging(false)
                if (e.dataTransfer.files && e.dataTransfer.files[0]) {
                  handleFileRead(e.dataTransfer.files[0])
                }
              }}
              onClick={() => fileInputRef.current?.click()}
              style={{
                border: `2px dashed ${isDragging ? 'var(--pufi-primary)' : 'var(--border-strong)'}`,
                background: isDragging ? 'var(--pufi-primary-light)' : 'var(--bg-subtle)',
                borderRadius: 'var(--radius-md)',
                padding: '44px 20px',
                textAlign: 'center',
                cursor: 'pointer',
                transition: 'all var(--trans-fast)',
              }}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".json"
                style={{ display: 'none' }}
                onChange={(e) => {
                  if (e.target.files && e.target.files[0]) {
                    handleFileRead(e.target.files[0])
                  }
                }}
              />
              <div
                style={{
                  width: 48,
                  height: 48,
                  borderRadius: '50%',
                  background: 'var(--bg-surface)',
                  color: 'var(--pufi-primary)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  margin: '0 auto 12px auto',
                  boxShadow: 'var(--shadow-sm)',
                }}
              >
                <UploadCloud size={24} />
              </div>
              <h4 style={{ margin: '0 0 4px 0', fontSize: '0.94rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                Click to upload or drag & drop JSON
              </h4>
              <p style={{ margin: 0, fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                Standard PUFI JSON array format (Max 2MB per upload)
              </p>
            </div>
          </div>

          {/* Supported Format Guide */}
          <div
            style={{
              marginTop: 20,
              padding: 14,
              borderRadius: 'var(--radius-sm)',
              background: 'var(--bg-subtle)',
              border: '1px solid var(--border-subtle)',
              fontSize: '0.76rem',
              color: 'var(--text-secondary)',
            }}
          >
            <div style={{ fontWeight: 700, color: 'var(--text-primary)', marginBottom: 4 }}>
              Required Object Fields:
            </div>
            <div>• <code>supplier_reference</code> (e.g. SUP-001)</div>
            <div>• <code>invoice_reference</code> (Unique within supplier)</div>
            <div>• <code>amount</code> (Decimal string &gt; 0)</div>
            <div>• <code>currency</code> (ISO 4217, e.g. USD, EUR, GBP)</div>
            <div>• <code>due_at</code> (YYYY-MM-DD date format)</div>
          </div>
        </div>

        {/* Right: Textarea Editor & Import CTA */}
        <div
          style={{
            background: 'var(--bg-surface)',
            border: '1px solid var(--border-base)',
            borderRadius: 'var(--radius-lg)',
            padding: 24,
            boxShadow: 'var(--shadow-card)',
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <h3 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 750, color: 'var(--text-primary)' }}>
              JSON Payload Editor
            </h3>
            <span style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>
              {jsonText ? `${jsonText.length} characters` : 'Empty buffer'}
            </span>
          </div>

          <textarea
            value={jsonText}
            onChange={(e) => {
              setJsonText(e.target.value)
              setParseError(null)
            }}
            placeholder="Paste your JSON array of obligation rows here, or click 'Load Sample Invoices' above..."
            style={{
              width: '100%',
              flex: 1,
              minHeight: 220,
              padding: 14,
              fontFamily: 'monospace',
              fontSize: '0.8rem',
              lineHeight: 1.45,
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-base)',
              background: 'var(--bg-subtle)',
              color: 'var(--text-primary)',
              resize: 'vertical',
              outline: 'none',
              boxSizing: 'border-box',
            }}
          />

          {parseError && (
            <div
              style={{
                marginTop: 12,
                padding: '10px 14px',
                borderRadius: 'var(--radius-sm)',
                background: 'var(--pufi-danger-bg)',
                border: '1px solid var(--pufi-danger-border)',
                color: 'var(--pufi-danger-text)',
                fontSize: '0.8rem',
                fontWeight: 650,
              }}
            >
              ⚠ {parseError}
            </div>
          )}

          <div style={{ marginTop: 16, display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
            <button
              onClick={handleImport}
              disabled={mutation.isPending || !jsonText.trim()}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 8,
                padding: '10px 24px',
                borderRadius: 'var(--radius-md)',
                background: 'var(--pufi-primary)',
                border: 'none',
                color: '#FFFFFF',
                fontSize: '0.86rem',
                fontWeight: 650,
                cursor: mutation.isPending || !jsonText.trim() ? 'not-allowed' : 'pointer',
                opacity: mutation.isPending || !jsonText.trim() ? 0.6 : 1,
                boxShadow: 'var(--shadow-sm)',
                transition: 'all var(--trans-fast)',
              }}
            >
              <UploadCloud size={16} />
              <span>{mutation.isPending ? 'Validating & Ingesting…' : 'Run Ingestion Pipeline'}</span>
            </button>
          </div>
        </div>
      </div>

      {/* Results Section */}
      {importResult && (
        <div
          style={{
            background: 'var(--bg-surface)',
            border: '1px solid var(--border-base)',
            borderRadius: 'var(--radius-lg)',
            padding: 24,
            boxShadow: 'var(--shadow-card)',
            display: 'flex',
            flexDirection: 'column',
            gap: 20,
          }}
        >
          {/* Summary Strip */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 16 }}>
            <div>
              <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 800, color: 'var(--text-primary)' }}>
                Ingestion Results Summary
              </h3>
              <p style={{ margin: '4px 0 0 0', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                Correlation ID: <code>{importResult.correlation_id}</code>
              </p>
            </div>

            <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
              <div
                style={{
                  padding: '8px 16px',
                  borderRadius: 'var(--radius-md)',
                  background: 'var(--pufi-success-bg)',
                  border: '1px solid var(--pufi-success-border)',
                  color: 'var(--pufi-success-text)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                }}
              >
                <CheckCircle2 size={16} />
                <span>
                  <strong>{importResult.accepted}</strong> Accepted
                </span>
              </div>

              <div
                style={{
                  padding: '8px 16px',
                  borderRadius: 'var(--radius-md)',
                  background: 'var(--pufi-warning-bg)',
                  border: '1px solid var(--pufi-warning-border)',
                  color: 'var(--pufi-warning-text)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                }}
              >
                <AlertTriangle size={16} />
                <span>
                  <strong>{importResult.duplicate}</strong> Flagged Duplicate
                </span>
              </div>

              <div
                style={{
                  padding: '8px 16px',
                  borderRadius: 'var(--radius-md)',
                  background: 'var(--pufi-danger-bg)',
                  border: '1px solid var(--pufi-danger-border)',
                  color: 'var(--pufi-danger-text)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                }}
              >
                <XCircle size={16} />
                <span>
                  <strong>{importResult.invalid}</strong> Invalid Rejected
                </span>
              </div>
            </div>
          </div>

          {/* Diagnostic Per-Row Results Table */}
          <div style={{ overflowX: 'auto', border: '1px solid var(--border-base)', borderRadius: 'var(--radius-md)' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.82rem' }}>
              <thead>
                <tr style={{ background: 'var(--bg-subtle)', borderBottom: '1px solid var(--border-base)', color: 'var(--text-secondary)' }}>
                  <th style={{ padding: '10px 16px', fontWeight: 700 }}>Row #</th>
                  <th style={{ padding: '10px 16px', fontWeight: 700 }}>Invoice Ref</th>
                  <th style={{ padding: '10px 16px', fontWeight: 700 }}>Supplier Ref</th>
                  <th style={{ padding: '10px 16px', fontWeight: 700 }}>Ingestion Status</th>
                  <th style={{ padding: '10px 16px', fontWeight: 700 }}>Diagnostic Details</th>
                  <th style={{ padding: '10px 16px', fontWeight: 700 }}>Obligation ID</th>
                </tr>
              </thead>
              <tbody>
                {importResult.results.map((r: ImportRowResult) => (
                  <tr key={r.row_index} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                    <td style={{ padding: '12px 16px', fontWeight: 600 }}>{r.row_index + 1}</td>
                    <td style={{ padding: '12px 16px' }}>
                      <code style={{ fontWeight: 700, color: 'var(--pufi-primary)' }}>{r.invoice_reference}</code>
                    </td>
                    <td style={{ padding: '12px 16px', color: 'var(--text-secondary)' }}>{r.supplier_reference}</td>
                    <td style={{ padding: '12px 16px' }}>
                      <StatusBadge status={r.status} size="sm" />
                    </td>
                    <td style={{ padding: '12px 16px', color: r.reason ? 'var(--pufi-danger-text)' : 'var(--text-muted)' }}>
                      {r.reason || 'Validation passed. Ingested as DRAFT.'}
                    </td>
                    <td style={{ padding: '12px 16px' }}>
                      {r.obligation_id ? (
                        <code style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>
                          {r.obligation_id.slice(-10)}
                        </code>
                      ) : (
                        '—'
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
