/**
 * PUFI — Centralized Error Formatter
 *
 * Guarantees clean, beginner-friendly error strings across all API calls,
 * mutations, and HTTP error responses. Never returns '[object Object]'.
 */

export function formatErrorMessage(err: unknown): string {
  if (!err) return 'Unknown error'
  if (typeof err === 'string') return err
  
  if (err instanceof Error) {
    return err.message || 'An unexpected error occurred'
  }

  const obj = err as Record<string, any>

  // Handle FastAPI / Starlette detail payloads
  if (obj.detail) {
    if (typeof obj.detail === 'string') return obj.detail
    if (typeof obj.detail === 'object') {
      if (obj.detail.message) return String(obj.detail.message)
      if (obj.detail.error) return String(obj.detail.error)
      if (Array.isArray(obj.detail)) {
        return obj.detail
          .map((d: any) => d.msg || d.message || (typeof d === 'string' ? d : JSON.stringify(d)))
          .join(', ')
      }
      try {
        return JSON.stringify(obj.detail)
      } catch {
        return 'Invalid request parameter'
      }
    }
  }

  // Handle nested error objects
  if (obj.error) {
    if (typeof obj.error === 'string') return obj.error
    if (typeof obj.error === 'object' && obj.error.message) {
      return String(obj.error.message)
    }
  }

  if (obj.message) return String(obj.message)

  try {
    const serialized = JSON.stringify(err)
    if (serialized && serialized !== '{}') {
      return serialized
    }
  } catch {
    // fallback
  }

  return 'Operation failed. Please review input parameters and re-try.'
}
