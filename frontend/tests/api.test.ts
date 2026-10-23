// @vitest-environment jsdom
import { afterEach, expect, test, vi } from 'vitest'
import { api, setToken } from '../src/api'
afterEach(() => { vi.unstubAllGlobals(); setToken('') })
test('sends bearer authorization and serializes JSON requests', async () => {
  const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ id: 'job' }), { headers: { 'content-type': 'application/json' } }))
  vi.stubGlobal('fetch', fetch); setToken('signed-token')
  expect(await api('/jobs', { method: 'POST', body: '{}' })).toEqual({ id: 'job' })
  expect(fetch.mock.calls[0][1].headers.get('Authorization')).toBe('Bearer signed-token')
})
test('returns readable API validation errors', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: 'All selected resumes must be ready' }), { status: 409 })))
  await expect(api('/jobs/job/screenings')).rejects.toThrow('All selected resumes must be ready')
})
test('expired sessions clear credentials and signal login UI', async () => {
  const expired = vi.fn(); window.addEventListener('session-expired', expired); setToken('expired')
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}', { status: 401 })))
  await expect(api('/me')).rejects.toThrow(); expect(sessionStorage.getItem('session')).toBeNull(); expect(expired).toHaveBeenCalled()
  window.removeEventListener('session-expired', expired)
})
