// @vitest-environment jsdom
import React from 'react'
import { afterEach, expect, test, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import App from '../src/App'
import { setToken } from '../src/api'

afterEach(() => { cleanup(); vi.unstubAllGlobals(); setToken('') })
function renderApp(path = '/') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[path]}><App/></MemoryRouter></QueryClientProvider>)
  return client
}
function reply(data: unknown, status = 200) { return new Response(JSON.stringify(data), { status, headers: { 'content-type': 'application/json' } }) }
test('login surfaces errors and then opens authenticated workspace', async () => {
  let fail = true
  vi.stubGlobal('fetch', vi.fn(async (path: string) => path.includes('/auth/demo') ? (fail ? reply({ detail: 'Invalid credentials' }, 401) : reply({ access_token: 'signed' })) : path.endsWith('/me') ? reply({ role: 'admin' }) : reply([])))
  renderApp()
  fireEvent.change(screen.getByLabelText('Local demo password'), { target: { value: 'wrong' } })
  fireEvent.click(screen.getByRole('button', { name: /Open workspace/ }))
  expect(await screen.findByRole('alert')).toHaveProperty('textContent', 'Invalid credentials')
  fail = false
  fireEvent.click(screen.getByRole('button', { name: /Open workspace/ }))
  expect(await screen.findByRole('heading', { name: 'A clearer view of your pipeline.' })).toBeTruthy()
})
test('password visibility can be toggled on the demo sign-in form', () => {
  vi.stubGlobal('fetch', vi.fn(async () => reply({})))
  renderApp()
  const password = screen.getByLabelText('Local demo password') as HTMLInputElement
  expect(password.type).toBe('password')
  fireEvent.click(screen.getByRole('button', { name: 'Show password' }))
  expect(password.type).toBe('text')
  fireEvent.click(screen.getByRole('button', { name: 'Hide password' }))
  expect(password.type).toBe('password')
})
test('signup exposes user and recruiter roles and explains provider provisioning', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => reply({})))
  renderApp()
  fireEvent.click(screen.getByRole('tab', { name: 'Create account' }))
  expect(screen.getByRole('radio', { name: /User/ })).toBeTruthy()
  fireEvent.click(screen.getByRole('radio', { name: /Recruiter/ }))
  expect(screen.getByRole('radio', { name: /Recruiter/ })).toHaveProperty('checked', true)
  fireEvent.click(screen.getByRole('button', { name: /Continue to create account/ }))
  expect(await screen.findByRole('alert')).toHaveProperty('textContent', expect.stringContaining('Organization sign-in is not configured'))
})
test('assistant preview is clear that it is not connected to an AI service', () => {
  vi.stubGlobal('fetch', vi.fn(async () => reply({})))
  renderApp()
  fireEvent.click(screen.getByRole('button', { name: 'Open assistant' }))
  expect(screen.getByText('Hi! I can help you explore the workspace. The AI service is not connected yet.')).toBeTruthy()
  fireEvent.change(screen.getByLabelText('Message the assistant'), { target: { value: 'How does this work?' } })
  fireEvent.click(screen.getByRole('button', { name: 'Send message' }))
  expect(screen.getByText('How does this work?')).toBeTruthy()
  expect(screen.getByText('Thanks for the question. This chatbot preview is not connected to an AI service yet.')).toBeTruthy()
})
test('user role gets an isolated account view without loading recruiting records', async () => {
  setToken('user-token')
  const fetchSpy = vi.fn(async (path: string) => path.endsWith('/me') ? reply({ role: 'user', organization_id: 'org' }) : reply([]))
  vi.stubGlobal('fetch', fetchSpy)
  renderApp()
  expect(await screen.findByRole('heading', { name: 'Welcome to JoldiNaw.' })).toBeTruthy()
  expect(screen.queryByRole('link', { name: 'Jobs' })).toBeNull()
  expect(fetchSpy.mock.calls.some(([path]) => path.endsWith('/jobs'))).toBe(false)
})
test('job editor validates explicit requirements and sends approved representation', async () => {
  setToken('signed')
  const requests: { path: string; body: string }[] = []
  vi.stubGlobal('fetch', vi.fn(async (path: string, options?: RequestInit) => { if (options?.method === 'POST') requests.push({ path, body: String(options.body) }); return reply(options?.method === 'POST' ? { id: 'new' } : []) }))
  renderApp('/jobs')
  fireEvent.click(await screen.findByRole('button', { name: 'Create job' }))
  fireEvent.change(screen.getByLabelText('Job title'), { target: { value: 'API Engineer' } })
  fireEvent.change(screen.getByLabelText('Job description'), { target: { value: 'Build reliable services' } })
  fireEvent.change(screen.getByLabelText('Requirement 1'), { target: { value: 'Python' } })
  fireEvent.click(screen.getByRole('button', { name: 'Approve and save job' }))
  await waitFor(() => expect(requests).toHaveLength(1))
  expect(JSON.parse(requests[0].body).requirements[0]).toMatchObject({ text: 'Python', required: true, weight: 1 })
})
test('screening view expands exact evidence and records human review', async () => {
  setToken('signed')
  const result = { id: 'result', resume_id: 'resume', model_version: 'test-v1', requirement_evidence_coverage: 100, semantic_similarity: null, reviews: [], requirements: [{ requirement_id: 'req', requirement_text: 'Python', decision: 'supported', explanation: 'Explicit source', supporting_evidence: [{ section_id: 'passage', page: 1, excerpt: 'Built a Python API.' }] }] }
  const save = vi.fn()
  vi.stubGlobal('fetch', vi.fn(async (path: string, options?: RequestInit) => {
    if (path.endsWith('/reviews')) { save(JSON.parse(String(options?.body))); return reply({ id: 'review' }, 201) }
    if (path.endsWith('/results')) return reply([result])
    if (path.endsWith('/resumes')) return reply([{ id: 'resume', filename: 'synthetic.docx', status: 'ready', skills: ['Python'] }])
    if (path.endsWith('/jobs')) return reply([])
    if (path.endsWith('/batch')) return reply({ id: 'batch', status: 'completed' })
    return reply([])
  }))
  renderApp('/screenings/batch')
  expect(await screen.findByText('synthetic.docx', { selector: 'h2' })).toBeTruthy()
  const requirement = await screen.findByText('Python', { selector: 'summary span' })
  fireEvent.click(requirement)
  expect(screen.getByText('Built a Python API.')).toBeTruthy()
  fireEvent.change(screen.getByLabelText('Review notes'), { target: { value: 'Verify project details' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save review' }))
  await waitFor(() => expect(save).toHaveBeenCalledWith({ notes: 'Verify project details', decision: 'reviewed' }))
})
