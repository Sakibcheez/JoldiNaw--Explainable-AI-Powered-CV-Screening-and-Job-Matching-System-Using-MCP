# API

OpenAPI is available at `http://localhost:8000/docs`. All `/api/v1` record endpoints require `Authorization: Bearer <token>`. Members of several organizations must supply `X-Organization-ID`; the server validates stored membership. Foreign IDs return 404. Token scopes: `read` for REST reads; `write` plus recruiter/admin membership for mutations. Production uses verified OIDC RS256 tokens.

`POST /api/v1/auth/demo` with `{"password":"your configured password"}` issues a two-hour development token. Demo login is disabled outside development.

The web frontend supports OIDC Authorization Code with PKCE. Configure `OIDC_ISSUER`, `OIDC_CLIENT_ID`, `OIDC_REDIRECT_URI`, and optional `OIDC_SCOPES` in the backend environment; the API reads provider discovery metadata and proxies the code exchange. Register the exact frontend callback URL with the provider. OIDC signup is hosted by the configured provider; users do not self-assign membership roles. Admin/recruiter/viewer roles may use the recruiting workspace, while the `user` role is restricted to `/me` and cannot read recruiting records or use MCP tools.

Create a job:

```json
{"title":"Backend Engineer","description":"Build APIs","requirements":[{"text":"Python","kind":"skill","required":true,"weight":3},{"text":"Docker","kind":"skill","required":false,"weight":1}]}
```

| Method | Path under `/api/v1` | Behavior |
|---|---|---|
| GET | `/me` | Identity and memberships |
| GET | `/auth/oidc/config` | Public OIDC authorization settings from server-side provider discovery |
| POST | `/auth/oidc/token` | Exchange `{"code":"...","code_verifier":"..."}` using configured callback URI |
| GET/POST | `/jobs` | List/create jobs |
| GET/PATCH/DELETE | `/jobs/{id}` | Get, full editable-field update, delete |
| PUT | `/jobs/{id}/requirements` | Approve replacement requirement list |
| GET/POST | `/resumes` | List/upload one PDF/DOCX using multipart `file` |
| GET/DELETE | `/resumes/{id}` | Inspect/delete document and derived data |
| PATCH | `/resumes/{id}/corrections` | `{"text":"corrected CV text"}`; invalidate old results |
| GET | `/processing/{id}` | Persisted task status |
| POST | `/jobs/{id}/screenings` | `{"resume_ids":["uuid"]}`; returns 202 and batch/task IDs |
| GET | `/screening-batches` | Recent batches |
| GET | `/screening-batches/{id}` | Batch status |
| GET | `/screening-batches/{id}/results` | Evidence-rich results |
| GET | `/screening-results/{id}` | Result and human review history |
| POST | `/screening-results/{id}/reviews` | `{"decision":"follow_up","notes":"Verify project scope"}` |
| GET | `/screening-batches/{id}/export` | Minimal CSV |

Lists accept bounded `limit` and `offset` where documented in OpenAPI. Job PATCH currently accepts the complete editable job representation. Upload returns `resume_id`, `processing_job_id`, `status: queued`; poll until ready/failed. Queue failures return 503 with a persisted failed record. No automatic retries after parser failure; correct the text or upload a repaired file. Deleting a job cascades its screening history.

Liveness `/health` and dependency readiness `/ready` are public and disclose no credentials. Validation errors use FastAPI's structured `detail`; safe parser failures omit raw source data and stack traces.
