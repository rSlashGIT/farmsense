param(
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"
$Venv = Join-Path $Backend ".venv"
$VenvPython = Join-Path $Venv "Scripts\python.exe"

Write-Host ""
Write-Host "FarmSense AI - Windows launcher"
Write-Host "Repository: $Root"
Write-Host ""

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python is not available on PATH. Install Python 3.11 and retry."
}
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw "npm is not available on PATH. Install Node.js 18+ and retry."
}

if (-not (Test-Path $VenvPython)) {
    Write-Host "Creating backend virtual environment..."
    python -m venv $Venv
}
if (-not $SkipInstall) {
    Write-Host "Installing/updating backend dependencies..."
    & $VenvPython -m pip install -r (Join-Path $Backend "requirements.txt")

    if (-not (Test-Path (Join-Path $Frontend "node_modules"))) {
        Write-Host "Installing frontend dependencies..."
        Push-Location $Frontend
        npm ci
        Pop-Location
    }
}

$FrontendEnv = Join-Path $Frontend ".env.local"
if (-not (Test-Path $FrontendEnv)) {
    Copy-Item (Join-Path $Frontend ".env.example") $FrontendEnv
    Write-Host "Created frontend/.env.local from .env.example"
}

$backendCommand = "Set-Location '$Backend'; & '$VenvPython' -m uvicorn main:app --reload --port 8001"
$frontendCommand = "Set-Location '$Frontend'; npm run dev"

Start-Process powershell.exe -ArgumentList "-NoExit", "-Command", $backendCommand
Start-Sleep -Seconds 2
Start-Process powershell.exe -ArgumentList "-NoExit", "-Command", $frontendCommand

Write-Host ""
Write-Host "FarmSense services launched in separate terminals."
Write-Host "Frontend : http://localhost:5173"
Write-Host "Backend  : http://localhost:8001"
Write-Host "API docs : http://localhost:8001/docs"
Write-Host "Health   : http://localhost:8001/health"
Write-Host ""
Write-Host "Use -SkipInstall on later runs to skip dependency installation."
