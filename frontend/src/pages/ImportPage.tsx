import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
  UploadCloud,
  Zap,
} from 'lucide-react'
import {
  importObligations,
  type ImportRowResult,
  type ImportResponse,
  type ObligationImportRow,
} from '../api/client'

// -------------------------------------------------------------------------
// Helpers
// -------------------------------------------------------------------------

function parseJsonRows(text: string): ObligationImportRow[] | string {
  try {
    const parsed = JSON.parse(text)
    if (!Array.isArray(parsed)) return 'JSON must be an array of obligation rows.'
    return parsed as ObligationImportRow[]
  } catch (e) {
    return `Invalid JSON: ${(e as Error).message}`
  }
}

const EXAMPLE_JSON = JSON.stringify(
  [
    {
      supplier_reference: 'SUP-001',
      invoice_reference: 'INV-2027-001',
      amount: '1250.00',
      currency: 'USD',
      due_at: '2027-01-31',
      notes: 'Q1 services via Zapier Webhook',
    },
    {
      supplier_reference: 'SUP-002',
      invoice_reference: 'INV-2027-002',
      amount: '800.50',
      currency: 'EUR',
      due_at: '2027-02-15',
      notes: 'Cloud infrastructure support',
    },
    {
      supplier_reference: 'SUP-003',
      invoice_reference: 'INV-2027-003',
      amount: '3150.00',
      currency: 'GBP',
      due_at: '2027-03-01',
      notes: 'Hardware procurement (Channel3 Sync)',
    },
  ],
  null,
  2
)

// -------------------------------------------------------------------------
// Row result badge
// -------------------------------------------------------------------------

function RowResultBadge({ status }: { status: ImportRowResult['status'] }) {
  const configs = {
    ACCEPTED: { label: '✓ Accepted', cls: 'status-validated' },
    DUPLICATE: { label: '⚠ Duplicate', cls: 'status-hold' },
    INVALID: { label: '✗ Invalid', cls: 'status-failed' },
  }
  const { label, cls } = configs[status]
  return <span className={`status-badge ${cls}`}>{label}</span>
}

// -------------------------------------------------------------------------
// Summary bar
// -------------------------------------------------------------------------

function ImportSummary({ result }: { result: ImportResponse }) {
  return (
    <div className="import-summary" style={{ background: '#FFFFFF', border: '1px solid #E2E8F0', borderRadius: 10, padding: '18px 24px', boxShadow: '0 2px 10px rgba(0,0,0,0.04)' }}>
      <div className="import-summary-title" style={{ fontWeight: 700, color: '#003087', fontSize: '0.88rem' }}>
        Batch Ingestion Results
      </div>
      <div className="import-summary-counts" style={{ display: 'flex', gap: 32, marginTop: 12 }}>
        <div className="summary-count accepted">
          <span className="count-num" style={{ color: '#007934', fontWeight: 800 }}>{result.accepted}</span>
          <span className="count-label">Accepted</span>
        </div>
        <div className="summary-count duplicate">
          <span className="count-num" style={{ color: '#B7791F', fontWeight: 800 }}>{result.duplicate}</span>
          <span className="count-label">Duplicates Flagged</span>
        </div>
        <div className="summary-count invalid">
          <span className="count-num" style={{ color: '#D9383A', fontWeight: 800 }}>{result.invalid}</span>
          <span className="count-label">Invalid Rejected</span>
        </div>
        <div className="summary-count total">
          <span className="count-num" style={{ color: '#0F172A', fontWeight: 800 }}>{result.total_rows}</span>
          <span className="count-label">Total Processed</span>
        </div>
      </div>
    </div>
  )
}

// -------------------------------------------------------------------------
// Main component
// -------------------------------------------------------------------------

export default function ImportPage() {
  const [jsonText, setJsonText] = useState('')
  const [parseError, setParseError] = useState<string | null>(null)
  const [showZapierGuide, setShowZapierGuide] = useState(false)
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
      setParseError('Array is empty — provide at least one obligation row.')
      return
    }
    mutation.mutate(result)
  }

  const importResult = mutation.data

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1 className="page-title" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span>Import & Ingestion</span>
            <span
              style={{
                fontSize: '0.72rem',
                padding: '3px 10px',
                borderRadius: 999,
                background: '#FFF3E0',
                color: '#FF6C37',
                border: '1px solid #FFE0B2',
                fontWeight: 700,
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4,
              }}
            >
              <Zap size={12} color="#FF6C37" />
              Zapier & Channel3 Ready
            </span>
          </h1>
          <p className="page-subtitle">
            Ingest supplier obligations via JSON batch, Zapier Webhooks, or Channel3 ERP connectors.
          </p>
        </div>
        <div className="page-actions">
          <button
            className="btn btn-secondary"
            onClick={() => setShowZapierGuide(!showZapierGuide)}
            style={{ fontSize: '0.8rem' }}
          >
            <Zap size={14} color="#FF6C37" />
            {showZapierGuide ? 'Hide Zapier Guide' : 'Zapier Webhook Config'}
          </button>
          <button className="btn btn-secondary" onClick={handleLoadExample}>
            Load Sample Payload
          </button>
        </div>
      </div>

      {/* Zapier / ERP Webhook Integration Card */}
      {showZapierGuide && (
        <div className="panel" style={{ borderLeft: '4px solid #FF6C37', background: '#FFFDFB' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
            <Zap size={18} color="#FF6C37" />
            <strong style={{ color: '#003087', fontSize: '0.95rem' }}>Automated Zapier Webhook Trigger</strong>
          </div>
          <p style={{ fontSize: '0.82rem', color: '#475569', marginBottom: 12 }}>
            You can connect QuickBooks, Xero, or Google Sheets to PUFI using Zapier Webhooks. Whenever a new invoice is approved in your accounting system, Zapier triggers PUFI's ingestion endpoint:
          </p>
          <pre style={{ background: '#F1F5F9', padding: '10px 14px', borderRadius: 6, fontSize: '0.76rem', color: '#0F172A', overflow: 'auto' }}>
{`POST http://localhost:8000/api/v1/obligations/import
Content-Type: application/json

[
  {
    "supplier_reference": "{{Zapier.SupplierID}}",
    "invoice_reference": "{{Zapier.InvoiceNumber}}",
    "amount": "{{Zapier.TotalAmount}}",
    "currency": "USD",
    "due_at": "{{Zapier.DueDate}}",
    "notes": "Ingested via Zapier trigger"
  }
]`}
          </pre>
        </div>
      )}

      {/* JSON input area */}
      <div className="panel">
        <label htmlFor="json-input" className="form-label" style={{ fontWeight: 700, color: '#003087' }}>
          Paste Obligation JSON Payload (Array)
        </label>
        <p style={{ fontSize: '0.78rem', color: '#64748B', marginBottom: 12 }}>
          Schema conforms to APIMatic OpenAPI 3.1 specification. Duplicate references are automatically quarantined.
        </p>
        <textarea
          id="json-input"
          className="import-textarea"
          value={jsonText}
          onChange={(e) => {
            setJsonText(e.target.value)
            setParseError(null)
          }}
          placeholder='[{"supplier_reference":"SUP-001","invoice_reference":"INV-001","amount":"500.00","currency":"USD","due_at":"2027-01-15"}]'
          rows={10}
          spellCheck={false}
          style={{ fontFamily: 'monospace', fontSize: '0.82rem' }}
        />

        {parseError && (
          <div className="alert alert-error" role="alert" style={{ marginTop: 12 }}>
            <strong>Parse error:</strong> {parseError}
          </div>
        )}

        <div className="import-actions" style={{ display: 'flex', gap: 10, marginTop: 14 }}>
          <button
            className="btn btn-paypal-blue"
            onClick={handleImport}
            disabled={mutation.isPending || !jsonText.trim()}
          >
            <UploadCloud size={16} />
            {mutation.isPending ? 'Validating & Importing…' : 'Process Ingestion'}
          </button>
          {(importResult || mutation.isError) && (
            <button
              className="btn btn-secondary"
              onClick={() => { mutation.reset(); setJsonText('') }}
            >
              Clear
            </button>
          )}
        </div>
      </div>

      {/* API error */}
      {mutation.isError && (
        <div className="alert alert-error" role="alert">
          <strong>Import failed:</strong>{' '}
          {(mutation.error as { error?: { message?: string } })?.error?.message ?? 'Unknown error'}
        </div>
      )}

      {/* Results */}
      {importResult && (
        <div className="import-results">
          <ImportSummary result={importResult} />

          <div className="table-wrapper" role="region" aria-label="Import results" style={{ marginTop: 16 }}>
            <table className="obligations-table">
              <thead>
                <tr>
                  <th scope="col">#</th>
                  <th scope="col">Invoice Ref</th>
                  <th scope="col">Supplier Ref</th>
                  <th scope="col">Ingestion Result</th>
                  <th scope="col">Validation Audit Detail</th>
                </tr>
              </thead>
              <tbody>
                {importResult.results.map((row) => (
                  <tr
                    key={row.row_index}
                    className={
                      row.status === 'INVALID'
                        ? 'row-error'
                        : row.status === 'DUPLICATE'
                        ? 'row-warning'
                        : 'row-success'
                    }
                  >
                    <td>{row.row_index + 1}</td>
                    <td>
                      <code style={{ fontWeight: 700, color: '#003087' }}>{row.invoice_reference}</code>
                    </td>
                    <td>{row.supplier_reference}</td>
                    <td>
                      <RowResultBadge status={row.status} />
                    </td>
                    <td className="col-notes">
                      {row.status === 'ACCEPTED' && row.obligation_id ? (
                        <span className="notes-text" title={row.obligation_id}>
                          Assigned UUID: {row.obligation_id.slice(0, 8)}…
                        </span>
                      ) : (
                        <span className="notes-text">{row.reason ?? '—'}</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {importResult.accepted > 0 && (
            <div className="alert alert-success" style={{ marginTop: 16 }}>
              ✓ {importResult.accepted} obligation{importResult.accepted !== 1 ? 's' : ''} ingested as DRAFT.
              Navigate to <strong>Obligations</strong> or <strong>Batches</strong> to bundle and route them for PayPal Sandbox payment.
            </div>
          )}
        </div>
      )}

      <p className="disclaimer" style={{ marginTop: 20 }}>
        ⓘ All imported data is treated as SYNTHETIC. No actual bank transfers or real money movement occurs.
      </p>
    </div>
  )
}
