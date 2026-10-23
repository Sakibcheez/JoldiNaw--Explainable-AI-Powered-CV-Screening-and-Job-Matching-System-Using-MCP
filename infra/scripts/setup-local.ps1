$ErrorActionPreference = 'Stop'
$repoPath = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $repoPath
if (!(Test-Path 'backend/.venv/Scripts/python.exe')) { python -m venv backend/.venv }
& backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.lock
if (!(Test-Path 'backend/.env')) {
    $randomSource = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $keyBytes = New-Object byte[] 32
    $passwordBytes = New-Object byte[] 12
    $randomSource.GetBytes($keyBytes)
    $randomSource.GetBytes($passwordBytes)
    $randomSource.Dispose()
    $randomKey = [BitConverter]::ToString($keyBytes).Replace('-', '')
    $randomPassword = [BitConverter]::ToString($passwordBytes).Replace('-', '')
    @("APP_ENV=development", "DATABASE_URL=sqlite:///./joldinaw.db", "TASK_MODE=inline", "STORAGE_DIR=storage", "JWT_SECRET=$randomKey", "DEMO_PASSWORD=$randomPassword") | Set-Content backend/.env
    Write-Host "Local demo password: $randomPassword"
}
Push-Location backend
try {
    & .venv/Scripts/python.exe -m alembic upgrade head
    & .venv/Scripts/python.exe -m scripts.seed_demo
} finally { Pop-Location }
Push-Location frontend
try { npm ci } finally { Pop-Location }
Write-Host 'Start API: cd backend; .venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000'
Write-Host 'Start UI in another terminal: cd frontend; npm run dev'
