$ErrorActionPreference = 'Stop'
$apiUrl = if ($env:JOLDINAW_API_URL) { $env:JOLDINAW_API_URL } else { 'http://localhost:8000' }
$mcpUrl = if ($env:JOLDINAW_MCP_URL) { $env:JOLDINAW_MCP_URL } else { 'http://localhost:8001/mcp' }
if (!$env:DEMO_PASSWORD) { throw 'Set DEMO_PASSWORD for your local demo first. This script never prints it or the access token.' }
$loginBody = @{password=$env:DEMO_PASSWORD} | ConvertTo-Json -Compress
$login = Invoke-RestMethod -Method Post -Uri "$apiUrl/api/v1/auth/demo" -ContentType 'application/json' -Body $loginBody
$env:MCP_STORAGE_DIR = Join-Path ([System.IO.Path]::GetTempPath()) ('joldinaw-inspector-' + [Guid]::NewGuid().ToString('N'))
$env:MCP_INSPECTOR_OAUTH_STATE_PATH = Join-Path $env:MCP_STORAGE_DIR 'oauth.json'
New-Item -ItemType Directory -Path $env:MCP_STORAGE_DIR -Force | Out-Null
$commonArgs = @('--loglevel=error','--yes','@modelcontextprotocol/inspector@2.5.0','--cli','--transport','http','--server-url',$mcpUrl,'--connect-timeout','10000','--stored-auth-only','--format','json','--header',"Authorization: Bearer $($login.access_token)")
$listing = & npx @commonArgs --method tools/list
if ($LASTEXITCODE -ne 0) { throw 'Inspector tools/list failed' }
$listingData = $listing | ConvertFrom-Json
if ($listingData.result.tools.Count -ne 6) { throw 'Expected six tools' }
$result = & npx @commonArgs --method tools/call --tool-name list_jobs --tool-arg limit=5
if ($LASTEXITCODE -ne 0) { throw 'Inspector list_jobs call failed' }
$resultData = $result | ConvertFrom-Json
if ($resultData.result.isError) { throw 'MCP tool returned an error' }
$result
Write-Output 'Inspector verified six tools and an authenticated list_jobs invocation.'
