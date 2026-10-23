# Implementation plan

1. Foundation: FastAPI, React/TypeScript, PostgreSQL/pgvector, Redis/RQ, Alembic, Compose.
2. Identity: signed dev sessions, production OIDC verification and stored memberships; organization-scoped shared services.
3. Documents: bounded PDF/DOCX validation, private storage, queued parsing, passages, skills and corrections.
4. Jobs and screening: structured weighted requirements, asynchronous batches, grounded evidence and immutable result snapshots, human reviews and CSV export.
5. MCP: official SDK v2, authenticated read-only tools through shared services.
6. Offline research: explicit dataset acquisition, provenance gate, audits, leakage-resistant splits, frozen TF-IDF and optional embedding classifier, honest evaluation.
7. Delivery: tests, CI, immutable container publishing, protected deployment, operating documentation.

SQLite and inline tasks are explicit test/development alternatives only. Production requires PostgreSQL, Redis and verified OIDC. Baseline mode works offline; semantic mode loads only an explicitly prepared local model. Docker is unavailable on the initial implementation host; container checks must be recorded as pending until run on a Docker host.

Schema refinement: jobs store ordered requirements as JSON, resumes store canonical skill lists as JSON, and screening results store immutable requirement/evidence snapshots as JSON. Passages, reviews, tasks, memberships and audit records have their own relational tables. This reduces duplicate write paths while preserving UUID passage citations and replayable requirement snapshots. The blueprint's separate job_requirements/resume_skills/requirement_evidence tables are represented in these aggregate documents rather than empty parallel tables. Future high-volume reporting can normalize them in an additive migration.
