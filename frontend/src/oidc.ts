import { api, setToken } from './api'

type OidcConfig = {
  authorization_endpoint: string
  client_id: string
  redirect_uri: string
  scopes: string
  audience: string
}

type OidcFlow = {
  state: string
  verifier: string
  redirectUri: string
  requestedRole?: 'user' | 'recruiter'
}

export type Account = { role: string; organization_id: string }

const flowKey = 'oidc-flow'

function base64Url(bytes: Uint8Array) {
  let binary = ''
  bytes.forEach(byte => { binary += String.fromCharCode(byte) })
  return btoa(binary).replaceAll('+', '-').replaceAll('/', '_').replaceAll('=', '')
}

function randomValue() {
  return base64Url(crypto.getRandomValues(new Uint8Array(32)))
}

export async function beginOidc(requestedRole?: 'user' | 'recruiter') {
  const config = await api<OidcConfig>('/auth/oidc/config')
  if (!config.authorization_endpoint || !config.client_id || !config.redirect_uri) {
    throw new Error('Organization sign-in is not configured.')
  }
  const verifier = randomValue() + randomValue()
  const state = randomValue()
  const redirectUri = config.redirect_uri
  const flow: OidcFlow = { state, verifier, redirectUri, requestedRole }
  sessionStorage.setItem(flowKey, JSON.stringify(flow))
  const challenge = base64Url(new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier))))
  const authorization = new URL(config.authorization_endpoint)
  const parameters = new URLSearchParams({
    response_type: 'code',
    client_id: config.client_id,
    redirect_uri: redirectUri,
    scope: config.scopes,
    state,
    code_challenge: challenge,
    code_challenge_method: 'S256',
    ...(config.audience ? { audience: config.audience } : {}),
  })
  parameters.forEach((value, key) => authorization.searchParams.set(key, value))
  window.location.assign(authorization.toString())
}

export async function finishOidc(): Promise<Account> {
  const parameters = new URLSearchParams(window.location.search)
  const providerError = parameters.get('error_description') || parameters.get('error')
  if (providerError) throw new Error(`Identity provider sign-in failed: ${providerError}`)

  const flow = sessionStorage.getItem(flowKey)
  sessionStorage.removeItem(flowKey)
  if (!flow) throw new Error('Sign-in session expired. Start again from the home page.')
  const saved = JSON.parse(flow) as OidcFlow
  if (!parameters.get('code') || parameters.get('state') !== saved.state) {
    throw new Error('The identity-provider response could not be verified. Start sign-in again.')
  }

  const response = await api<{ access_token: string }>('/auth/oidc/token', {
    method: 'POST',
    body: JSON.stringify({
      code: parameters.get('code')!,
      code_verifier: saved.verifier,
    }),
  })
  setToken(response.access_token)
  try {
    const account = await api<Account>('/me')
    if (saved.requestedRole && !hasRequestedRole(account.role, saved.requestedRole)) {
      throw new Error(`Your identity-provider account is not provisioned with the ${saved.requestedRole} role.`)
    }
    return account
  } catch (error) {
    setToken('')
    throw error
  }
}

function hasRequestedRole(actual: string, requested: 'user' | 'recruiter') {
  return requested === 'recruiter' ? ['recruiter', 'admin'].includes(actual) : actual === 'user'
}
