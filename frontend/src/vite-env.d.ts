interface ImportMetaEnv {
  readonly DEV: boolean
  readonly VITE_OIDC_ISSUER?: string
  readonly VITE_OIDC_CLIENT_ID?: string
  readonly VITE_OIDC_SCOPES?: string
  readonly VITE_OIDC_AUDIENCE?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
