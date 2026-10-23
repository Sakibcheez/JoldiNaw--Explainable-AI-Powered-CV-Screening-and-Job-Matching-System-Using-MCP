export type Requirement = { text: string; kind: string; required: boolean; weight: number }
export type Job = { id: string; title: string; description: string; status: string; requirements: Requirement[] }
export type Resume = { id: string; filename: string; status: string; skills: string[]; error?: string; sections?: { id: string; text: string; page: number }[] }
export type Batch = { id: string; job_id: string; status: string; error?: string }
export type Result = { id: string; resume_id: string; batch_id: string; requirement_evidence_coverage: number; semantic_similarity: number | null; model_version: string; limitations: string; reviews: { decision: string; notes: string }[]; requirements: { requirement_id: string; requirement_text: string; decision: string; explanation: string; supporting_evidence: { section_id: string; page: number; excerpt: string }[] }[] }
let token = sessionStorage.getItem('session') || ''
export const setToken = (value: string) => { token = value; value ? sessionStorage.setItem('session', value) : sessionStorage.removeItem('session') }
export const hasToken = () => Boolean(token)
export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers)
  if (token) headers.set('Authorization', `Bearer ${token}`)
  if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json')
  const response = await fetch(`/api/v1${path}`, { ...options, headers })
  if (!response.ok) { if (response.status === 401 && !path.includes('/auth/')) { setToken(''); window.dispatchEvent(new Event('session-expired')) }; const body = await response.json().catch(() => ({})); throw new Error(typeof body.detail === 'string' ? body.detail : `Request failed (${response.status})`) }
  if (response.status === 204) return undefined as T
  return (response.headers.get('content-type')?.includes('text/csv') ? response.text() : response.json()) as Promise<T>
}
