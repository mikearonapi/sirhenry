# deploy.ps1 — Rebuild and restart production containers
# Usage: .\scripts\deploy.ps1

Write-Host "Building and deploying SirHENRY (production)..." -ForegroundColor Green

docker compose up --build -d

Write-Host ""
Write-Host "Frontend: http://localhost:3001" -ForegroundColor Cyan
Write-Host "API:      http://localhost:8000" -ForegroundColor Cyan
