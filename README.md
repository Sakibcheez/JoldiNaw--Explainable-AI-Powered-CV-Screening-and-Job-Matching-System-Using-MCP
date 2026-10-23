# JoldiNaw

Explainable CV screening and job matching using FastAPI, React/TypeScript, PostgreSQL/pgvector, Redis/RQ and the official MCP Python SDK v2.

Create weighted job requirements, upload authorized PDF/DOCX CVs, run comparisons, inspect exact evidence passages and record human reviews. Evidence coverage, TF-IDF retrieval and optional semantic similarity remain separate. The app never automatically rejects candidates or presents a hiring probability.

## Docker quick start

Requires Docker Desktop with Compose v2. From this repository:

```powershell
Copy-Item .env.example .env
# Edit .env: choose DEMO_PASSWORD, a random JWT_SECRET (32+ characters),
# and matching POSTGRES_PASSWORD / DATABASE_URL credentials.
docker compose config
docker compose up --build -d
docker compose exec api python -m scripts.seed_demo
docker compose ps
```

Linux/macOS: use `cp .env.example .env`, then the same Docker commands.
Open **http://localhost:5173** and sign in using your configured demo password. Seed data contains two explicitly synthetic CVs and one job. The seed command is development-only and repeatable.

```sh
curl http://localhost:8000/health
curl http://localhost:8000/ready
docker compose logs --tail=100 api worker
docker compose exec api alembic current
docker compose exec db psql -U joldinaw -d joldinaw -c "SELECT extname FROM pg_extension WHERE extname='vector';"
```

Normal startup does not download datasets or models. The deterministic skill/TF-IDF mode needs no model cache. `docker compose down` preserves volumes; `down -v` destroys them.

## Local Windows setup without Docker

Requires Python 3.13 and Node.js 22.12+. This explicit development mode uses SQLite and inline processing; Redis/RQ is used in Docker and required in production.

```powershell
powershell -ExecutionPolicy Bypass -File infra/scripts/setup-local.ps1
# The script prints a generated local demo password on first setup.
Set-Location backend
.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In a second terminal from the repository root:

```powershell
Set-Location frontend
npm run dev
```

If Node reports an untrusted registry certificate on a managed Windows machine, set `$env:NODE_USE_SYSTEM_CA='1'` before `npm ci`. Do not disable TLS verification.

## Main workflow

1. Create a job and explicitly approve requirement types, weights and required/preferred flags.
2. Upload synthetic or authorized PDF/DOCX files in Candidate library. Wait for ready status.
3. Select a job and up to 50 ready candidates in Screenings.
4. Open each requirement to inspect the quoted passage and page. DOCX has extracted-text offsets rather than reliable printed page locations.
5. Record review notes and a human disposition. Export a CSV without raw CV text or names.
6. Correct extracted CV text when necessary. Corrections invalidate previous results for that CV so stale citations are not reused.

## Validation

```powershell
Set-Location backend
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe -m ruff check app mcp_server scripts tests ../ml
Set-Location ../frontend
npm run lint
npm test -- --run
npm run build
```

Tests use their own temporary database/storage. Set `TEST_DATABASE_URL` only to a disposable PostgreSQL database; fixtures recreate tables. CI additionally migrates PostgreSQL/pgvector, checks Redis and builds/boots Compose. Local container verification requires Docker and is tracked separately in [implementation status](docs/IMPLEMENTATION_STATUS.md).

## Architecture and research

REST and MCP share organization-scoped services. RQ workers parse documents and perform versioned comparisons. Private file storage uses random object keys. Alembic manages schema changes. UI uses React Router, TanStack Query and Tailwind/CSS. Optional embeddings load from a prepared local model only.

See [API](docs/API.md), [MCP](docs/MCP.md), [offline research commands](ml/README.md), [dataset card](docs/DATASET_CARD.md), [model card](docs/MODEL_CARD.md), [evaluation](docs/EVALUATION.md), [security](docs/SECURITY.md), [deployment](docs/DEPLOYMENT.md) and [operations](docs/OPERATIONS.md).

This is a research/demo implementation. Production rollout requires configured OIDC, explicit organization memberships, reviewed retention/consent procedures, parser/antivirus isolation and completed infrastructure verification. No production deployment or public-dataset training is claimed.

## OIDC signup and sign-in

The public home page supports hosted OIDC sign-in and signup using Authorization Code with PKCE. Configure `OIDC_ISSUER`, `OIDC_AUDIENCE`, `OIDC_JWKS_URL`, `OIDC_CLIENT_ID`, `OIDC_REDIRECT_URI`, and `OIDC_SCOPES` in the backend environment. Register the exact redirect URI (locally `http://localhost:5173/auth/callback`) with the provider and enable PKCE (`S256`) on its public client. The backend exchanges authorization codes with the provider; no provider token-endpoint CORS exception is needed. The provider must issue the API scopes required by this deployment and provide its own hosted signup experience if self-service registration is enabled. For another frontend origin, set its exact `/auth/callback` URL and add the origin to `CORS_ORIGINS`.

The signup role selector records the requested account type, but does not assign permissions. Provision the user's organization membership and role in the identity provider/application provisioning workflow; the app verifies the requested role against `/api/v1/me`. Recruiter/admin accounts enter the recruiting workspace. A `user` membership can access `/me` only and receives no job, CV, screening, review, or MCP data. Local demo-password login remains available only in development; the organization access-token field is intended for configured identity integrations.

The assistant bubble is currently an interface preview only. It does not call a model or service and clearly tells users that generated answers are not available yet.
