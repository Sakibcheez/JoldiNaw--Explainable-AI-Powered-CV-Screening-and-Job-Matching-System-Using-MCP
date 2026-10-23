# Deployment

The project includes CI, green-CI-gated GHCR publication, protected manual deployment and production Compose/Caddy. These configurations have not been executed on GitHub or a VPS during local implementation. Never report an unexecuted deployment as live.

Configure repository main protection and a protected `production` environment with required approval. Supply environment secrets `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY`, `DEPLOY_KNOWN_HOSTS`. SSH host verification stays enabled. Install a hardened Linux Docker host, put reviewed config/scripts under `/opt/joldinaw`, and provide private read-only GHCR pull credentials on the host if images are private.

Create `/opt/joldinaw/.env.production` (mode 600) with APP_ENV=production, TASK_MODE=rq, PostgreSQL/Redis URLs, storage path `/app/storage`, OIDC_ISSUER/OIDC_AUDIENCE/OIDC_JWKS_URL/OIDC_CLIENT_ID/OIDC_REDIRECT_URI/OIDC_SCOPES, exact CORS origins and APP_DOMAIN. Register the exact HTTPS redirect URI with the identity provider. Set POSTGRES credentials consistently. Configure RS256 access tokens with `read`, `write` and/or `mcp:read` scopes. Provision users and memberships by CLI after migrations. Demo login and seed are disabled in production.

The Publish images workflow triggers only after successful push CI on main, builds both images tagged by the tested SHA and saves immutable digest references. Dispatch Deploy production with the successful publication run ID; the workflow verifies publication status, downloads digest artifacts and passes validated digest references over SSH to the host script. The host script pulls, migrates, starts Compose with health checks and records `.release`/`.release.previous`. Config updates on the VPS must match the tested image version; review and sync them before deployment. Never interpolate untrusted user input into remote commands.

Caddy terminates HTTPS on APP_DOMAIN and serves the UI/API under one origin. Only ports 80/443 are public. PostgreSQL, Redis, workers and file storage are private. MCP is disabled by profile and has no public proxy route; see MCP.md before enabling it. API needs outbound HTTPS access to OIDC JWKS; the production network attachment must allow that before rollout.

Rollback: use the previous two digest lines from `.release.previous` as arguments to `bash infra/scripts/deploy-prod.sh`. Automatic application rollback is attempted on failed Compose readiness, when a previous release exists. Database schema rollback is deliberately manual; take a tested backup before migrations and use additive/backward-compatible changes. Do not destroy persistent volumes during deploy.

GitHub Actions are pinned to immutable SHAs resolved from official release refs. Base-image tags still need reviewed digest hardening before production release. Dependabot proposes action/package updates. Actual CI green status, image build/publish, TLS, OIDC integration, disaster recovery and deployment smoke tests remain acceptance gates.
