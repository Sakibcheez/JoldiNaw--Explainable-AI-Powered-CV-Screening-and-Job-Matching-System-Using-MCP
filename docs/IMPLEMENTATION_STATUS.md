# Implementation status — 2026-10-24

## Working locally

- React/TypeScript recruiting workspace: authenticated login, dashboard, job/requirement editing, PDF/DOCX library, processing states, text correction, candidate selection, screening results, expandable source citations, human reviews, filters, CSV exports and settings.
- Animated public home page with OIDC sign-in/signup and Authorization Code + PKCE, a password visibility control for development demo login, and explicit user/recruiter role onboarding. OIDC roles remain provider-provisioned; `user` accounts are isolated from recruiting REST and MCP data.
- Chatbot interface preview on the home page and signed-in views. No model/API is connected; the UI states this clearly.
- FastAPI CRUD and screening API; signed development sessions; production OIDC verifier; stored users/memberships, scoped lookups and role/scope checks. Production disables demo login/seeding and refuses incomplete auth/database/queue configuration.
- SQLAlchemy schema, Alembic initial migration and synthetic seed. SQLite migration/seed actually executed. PostgreSQL vector schema and Compose services are implemented; PostgreSQL execution is pending Docker availability.
- Safe bounded extraction, canonical skill distinctions, private random-key storage and cascade deletion. Corrections invalidate stale results. RQ task implementation is shared with development inline execution; real Redis/RQ integration has a CI verification script but was not run locally.
- Deterministic evidence matching and TF-IDF retrieval with actual persisted source passages. Coverage never means hiring probability. Bounded local-only semantic loading and pgvector embedding persistence implemented; model weights were not downloaded or tested.
- Six official MCP SDK 2.3.0 read-only tools with verified identity, tenant checks, scope enforcement, bounded output, transport host/origin allowlists and development-only stdio.
- Offline dataset acquisition with provenance gate, schema/audit reports, duplicate/conflict detection, benchmark/unseen-job/strict identity splits, frozen TF-IDF and optional pooled-embedding pair classifiers, validation model selection and checksummed evaluation/artifacts. Synthetic training-pipeline tests executed; public-data training did not.
- Dockerfiles, development/production Compose, Caddy/Nginx, CI with PostgreSQL/Redis and container boot gates, green-CI-gated immutable image publication, protected digest-based SSH deployment, rollback/backup scripts and operating documentation.

## Actual verification results

| Check | Actual result |
|---|---|
| `backend/.venv/Scripts/python.exe -m pytest -q --tb=short` from backend | **27 passed**, 19.61 seconds |
| Ruff on app, MCP, scripts, tests and ML | **All checks passed** |
| `python -m pip check` in backend environment | **No broken requirements found** |
| `python -m compileall -q app mcp_server scripts ../ml` | Passed |
| `npm test -- --run` after Vitest update | **10 passed**, 2 files, Vitest 5.0.5 |
| `npm run lint` | Passed TypeScript check |
| `npm run build` | Passed; Vite 7.3.7, production JS ~323 kB (~102 kB gzip) |
| Live `npm audit --json` after update | **0 vulnerabilities** |
| `alembic upgrade head` / `alembic current` on local SQLite | Passed, `0001 (head)` |
| Local `/health` and `/ready` | Passed in explicit SQLite/inline development mode |
| Browser smoke | Signed in, loaded seeded data, selected both synthetic CVs, ran screening, expanded exact Python passage, saved human review; verified persisted results |
| New home page browser smoke | Desktop accessibility/UI smoke passed; mobile viewport 375px wide with no horizontal overflow |
| OIDC provider login/signup | Server discovery/code-exchange and PKCE-verifier validation tested with mocked provider responses; signup role/UI state tested. Live IdP browser round-trip not run |
| API process restart persistence | Passed; both synthetic results and the saved human review remained available after restart; readiness returned ready |
| Official Inspector 2.5.0 via stdio | **Passed** real `list_jobs` invocation; `isError: false`, Backend Engineer returned |
| MCP ASGI protocol tests | Passed initialize/discovery/tool call/input bound checks and unauthorized/cross-tenant checks |
| Inspector Streamable HTTP over loopback | **Failed**: invalid HTTP chunk size; reproduced on ports 8001 and 8011. ASGI response has valid Content-Length; observed socket response has chunked header and unchunked body. Unresolved host/network/server-path issue |
| YAML parse | Both Compose files and all three workflow files parsed successfully; this is not Compose schema/runtime validation |
| Docker Compose config/build/boot | **Not run**: `docker` command is absent on this host |
| GitHub CI, GHCR publish, production deployment | **Not run**: no remote execution/deploy credentials supplied |
| Public-dataset audit/training and semantic weights | **Not run**: dataset license/upstream-use review and pinned artifact acquisition required |

Earlier sandbox runs failed on temporary-file/process permissions; required checks were rerun with approved access. Node needed the Windows system CA store for package installation. Initial test-tool advisories were resolved by upgrading Vitest to 5.0.5. No TLS verification was disabled.

## Milestone assessment

M0–M5: local baseline application implemented and exercised. Docker/PostgreSQL/RQ acceptance remains pending. M6: tools, authorization, ASGI protocol tests and official stdio Inspector verified; HTTP Inspector transport gate unresolved. M7: pipeline implemented/tested on synthetic software fixtures; real dataset experiment pending terms review and acquisition. M8: CI/CD code and pinned Action SHAs implemented; remote workflow/image/deployment gates pending. M9: controls and operating runbooks implemented, with production hardening gaps disclosed in SECURITY.md.

This is **not a claim that every blueprint acceptance gate is complete**. Requirements/skills/evidence snapshots use aggregate JSON instead of separate normalized tables; this documented schema refinement keeps passage/review/task/auth records relational. The runtime experimental fit classifier remains disabled, with null predictions, until independently evaluated artifacts are reviewed.

## Remaining acceptance work

1. Install/enable Docker Desktop, then run documented Compose config/build/boot commands, real PostgreSQL migrations, Redis/RQ integration script and restart-persistence/deletion checks.
2. Resolve the loopback HTTP framing issue and repeat `scripts/inspector-smoke.ps1` through the actual container/proxy path. Inspect against a clean network host before exposing HTTP MCP.
3. Review dataset/upstream permissions, pin dataset/model commits, run acquisition/audit/splits/training and independently annotated grounding/fairness/retrieval experiments. Optional trainer dependencies are exact-version specified but not installed/tested here.
4. Configure a real OIDC provider and provision memberships; verify the full browser PKCE and production signature/scope flows with that provider. Antivirus isolation, distributed throttling, durable queue outbox/crash recovery, automatic retention and backup/restore rehearsal remain production-hardening tasks.
5. Push reviewed code to GitHub, require green CI, verify both image builds/publication and immutable deployment digests. Configure protected production environment, DNS/VPS/SSH secrets, TLS and image-pull credentials. Pin/review base-image digests and rehearse rollback.

Screenshots in `docs/screenshots/` show only synthetic demo data. Private generated local credentials live in ignored `backend/.env`. The app runs at http://localhost:5173 with API at http://localhost:8000; normal Docker operation uses the root `.env` instead.
