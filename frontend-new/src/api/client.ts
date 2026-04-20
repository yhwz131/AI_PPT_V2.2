const API_BASE = import.meta.env.VITE_API_BASE || ''

export interface ApiResponse<T = any> {
  code: number
  message: string
  data: T
}

function extractError(err: any, fallback: string): string {
  const raw = err.detail || err.error || err.message || fallback
  if (typeof raw === 'string') return raw
  if (Array.isArray(raw)) return raw.map((e: any) => e.msg || JSON.stringify(e)).join('; ')
  return JSON.stringify(raw)
}

export async function apiGet<T = any>(path: string): Promise<ApiResponse<T>> {
  const res = await fetch(`${API_BASE}${path}`)
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(extractError(err, res.statusText))
  }
  return res.json()
}

export async function apiPost<T = any>(path: string, body?: any): Promise<ApiResponse<T>> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(extractError(err, res.statusText))
  }
  return res.json()
}

export async function apiUpload<T = any>(path: string, formData: FormData): Promise<ApiResponse<T>> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    body: formData,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(extractError(err, res.statusText))
  }
  return res.json()
}

export async function apiDelete<T = any>(path: string): Promise<ApiResponse<T>> {
  const res = await fetch(`${API_BASE}${path}`, { method: 'DELETE' })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(extractError(err, res.statusText))
  }
  return res.json()
}

export function staticUrl(path: string): string {
  if (path.startsWith('http')) return path
  return `${API_BASE}${path}`
}

export function sseUrl(path: string): string {
  return `${API_BASE}${path}`
}
