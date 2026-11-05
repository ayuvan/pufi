import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
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
      notes: 'Q1 services',
    },
    {
      supplier_reference: 'SUP-002',
      invoice_reference: 'INV-2027-002',
      amount: '800.50',
      currency: 'EUR',
      due_at: '2027-02-15',
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
    ACCEPTED: { label: '✓ Accepted', cls: 'import-badge-accepted' },
    DUPLICATE: { label: '⚠ Duplicate', cls: 'import-badge-duplicate' },
    INVALID: { label: '✗ Invalid', cls: 'import-badge-invalid' },
  }
  const { label, cls } = configs[status]
  return <span className={`import-badge ${cls}`}>{label}</span>
}

// -------------------------------------------------------------------------
// Summary bar
// -------------------------------------------------------------------------

function ImportSummary({ result }: { result: ImportResponse }) {
  return (
    <div className="import-summary">
      <div className="import-summary-title">Import Summary</div>
      <div className="import-summary-counts">
        <div className="summary-count accepted">
          <span className="count-num">{result.accepted}</span>
          <span className="count-label">Accepted</span>
        </div>
        <div className="summary-count duplicate">
          <span className="count-num">{result.duplicate}</span>
          <span className="count-label">Duplicate</span>
        </div>
        <div className="summary-count invalid">
          <span className="count-num">{result.invalid}</span>
          <span className="count-label">Invalid</span>
        </div>
        <div className="summary-count total">
          <span className="count-num">{result.total_rows}</span>
          <span className="count-label">Total</span>
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
  const queryClient = useQueryClient()

  const mutation = useMutation({
    mutationFn: (rows: ObligationImportRow[]) => importObligations(rows),
    onSuccess: () => {
      // Invalidate the obligations list so the main table refreshes
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
          <h1 className="page-title">Import Obligations</h1>
          <p className="page-subtitle">
            Paste a JSON array of obligation rows. Each row is validated independently.
            Invalid and duplicate rows are reported but never inserted.
          </p>
        </div>
        <div className="page-actions">
          <button className="btn btn-secondary" onClick={handleLoadExample}>
            Load Example
          </button>
        </div>
      </div>

      {/* JSON input area */}
      <div className="import-input-section">
        <label htmlFor="json-input" className="import-label">
          Obligation JSON (array)
        </label>
        <textarea
          id="json-input"
          className="import-textarea"
          value={jsonText}
          onChange={(e) => {
            setJsonText(e.target.value)
            setParseError(null)
          }}
          placeholder='[{"supplier_reference":"SUP-001","invoice_reference":"INV-001","amount":"500.00","currency":"USD","due_at":"2027-01-15"}]'
          rows={12}
          spellCheck={false}
        />

        {parseError && (
          <div className="alert alert-error" role="alert">
            <strong>Parse error:</strong> {parseError}
          </div>
        )}

        <div className="import-actions">
          <button
            className="btn btn-primary"
            onClick={handleImport}
            disabled={mutation.isPending || !jsonText.trim()}
          >
            {mutation.isPending ? 'Importing…' : 'Import Obligations'}
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
          <strong>Import failed.</strong>{' '}
          {(mutation.error as { error?: { message?: string } })?.error?.message ?? 'Unknown error'}
        </div>
      )}

      {/* Results */}
      {importResult && (
        <div className="import-results">
          <ImportSummary result={importResult} />

          <div className="table-wrapper" role="region" aria-label="Import results">
            <table className="obligations-table">
              <thead>
                <tr>
                  <th scope="col">#</th>
                  <th scope="col">Invoice Ref</th>
                  <th scope="col">Supplier Ref</th>
                  <th scope="col">Result</th>
                  <th scope="col">Detail</th>
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
                      <code>{row.invoice_reference}</code>
                    </td>
                    <td>{row.supplier_reference}</td>
                    <td>
                      <RowResultBadge status={row.status} />
                    </td>
                    <td className="col-notes">
                      {row.status === 'ACCEPTED' && row.obligation_id ? (
                        <span className="notes-text" title={row.obligation_id}>
                          ID: {row.obligation_id.slice(0, 8)}…
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
            <div className="alert alert-info" role="status">
              ✓ {importResult.accepted} obligation{importResult.accepted !== 1 ? 's' : ''} imported as DRAFT.
              Go to <strong>Obligations</strong> to validate them before batching.
            </div>
          )}
        </div>
      )}

      <p className="disclaimer">
        ⓘ Import is for SYNTHETIC demo data only. No real financial records.
        Invalid and duplicate rows are shown here and never stored.
      </p>
    </div>
  )
}
