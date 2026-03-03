# dev.ps1 — Start SirHENRY in development mode (instant hot reload)
# Usage: .\scripts\dev.ps1
#
# API runs in Docker (port 8000).
# Frontend runs natively via Node so file changes reflect instantly in the browser.
# No Docker rebuild needed for frontend changes.

$env:PATH = [System.Environment]::GetEnvironmentVariable("PATH","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("PATH","User")

Write-Host "Starting API in Docker..." -ForegroundColor Green
docker compose up api -d

Write-Host ""
Write-Host "API:               http://localhost:8000" -ForegroundColor Cyan
Write-Host "Frontend (dev):    http://localhost:3000  (starting...)" -ForegroundColor Cyan
Write-Host ""
Write-Host "Edit any file in frontend/ and the browser updates instantly." -ForegroundColor Yellow
Write-Host "Press Ctrl+C to stop the dev server." -ForegroundColor Yellow
Write-Host ""

Set-Location "$PSScriptRoot\..\frontend"
npm run dev
