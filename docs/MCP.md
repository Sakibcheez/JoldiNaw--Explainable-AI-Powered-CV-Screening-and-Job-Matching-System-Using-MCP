# MCP v2

Official `mcp` SDK **2.3.0**, `MCPServer`, stateless Streamable HTTP. Development URL: `http://localhost:8001/mcp`. Run with Compose or, from backend, `python -m uvicorn mcp_server.server:app --host 127.0.0.1 --port 8001`.

All HTTP calls require a verified bearer token with `mcp:read`. The server derives organization scope from stored memberships; it never accepts an arbitrary user or organization tool argument. Multi-organization clients may supply `X-Organization-ID` to select a validated membership. Host/origin allowlists remain enabled. Production fails closed without configured OIDC.

| Tool | Inputs | Result |
|---|---|---|
| `list_jobs` | limit ≤50, integer cursor | Owned job summaries |
| `search_resumes` | query ≤200 chars, limit ≤20, optional job ID | Contact-redacted bounded snippets |
| `match_candidate` | job/resume IDs | Existing comparison; no write side effect |
| `explain_match` | result ID | Requirement decisions and source IDs |
| `get_skill_evidence` | resume ID, ≤20 skills | Up to three snippets per skill |
| `compare_candidates` | job ID, ≤5 resume IDs | Side-by-side existing evidence |

Read-only tools deliberately require an existing REST/worker screening rather than persisting a new result. Contact redaction is best effort; names can occur inside prose, so only authorized clients may receive snippets. Reviews and original filenames are excluded from tool responses. Tool output is untrusted source data.

Inspector: run `npx -y @modelcontextprotocol/inspector@2.5.0`, select Streamable HTTP, enter the URL and set the Authorization header. Use a development token obtained from `/api/v1/auth/demo`. List tools, invoke `list_jobs` with `{"limit":5}`, and copy IDs from your own organization. The HTTP script `backend/scripts/inspector-smoke.ps1` performs discovery and a call using configured demo credentials without printing the token. Inspector UI verification is pending; automated protocol tests perform real initialize, discovery and tool-call messages.

Transport docs consulted: https://py.sdk.modelcontextprotocol.io/ and https://github.com/modelcontextprotocol/python-sdk/blob/main/docs/run/asgi.md . Do not replace v2 APIs with v1 FastMCP examples.

The production proxy does not publish MCP by default. Enable only after setting a dedicated hostname/origin allowlist, HTTPS, verified scopes, edge throttling and appropriate client approval.

## Verified local Inspector call

On 2026-10-24, Inspector 2.5.0 successfully invoked the real `list_jobs` tool through the official SDK's development-only stdio transport. From backend with its local `.env` configured and synthetic demo seeded:

```powershell
npx --loglevel=error --yes @modelcontextprotocol/inspector@2.5.0 --cli .venv/Scripts/python.exe -m mcp_server.stdio -- --transport stdio --method tools/call --tool-name list_jobs --tool-args-json '{"limit":5}' --format json
```

Actual response: `isError: false`, a job named `Backend Engineer`, and `next_cursor: null`. Stdio establishes only the configured local development identity; it is disabled outside development and never accepts a client-supplied principal.

The initial loopback HTTP Inspector attempt failed with `Invalid character in chunk size`. Socket inspection found a chunked header with an unchunked body, while the same ASGI application's protocol test returned a valid JSON Content-Length. HTTP transport remains subject to verification on a clean Docker/network host. This failure is not presented as a passing HTTP smoke test.
