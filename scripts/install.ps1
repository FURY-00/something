# Jarvis installer for Windows.
# Run from the project folder in PowerShell:
#   powershell -ExecutionPolicy Bypass -File scripts\install.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

Write-Host "==> Checking Python"
if (Get-Command py -ErrorAction SilentlyContinue) {
    $python = "py"; $pyArgs = @("-3")
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $python = "python"; $pyArgs = @()
} else {
    Write-Host "Python not found. Install Python 3.12 from https://www.python.org/downloads/"
    Write-Host "(tick 'Add python.exe to PATH'), then run this script again."
    exit 1
}
& $python @pyArgs -c "import sys; assert sys.version_info >= (3, 10), 'Python 3.10 or newer is required'"
if ($LASTEXITCODE -ne 0) { exit 1 }

Write-Host "==> Creating virtual environment (.venv)"
if (-not (Test-Path .venv)) { & $python @pyArgs -m venv .venv }
$venvPy = ".\.venv\Scripts\python.exe"
& $venvPy -m pip install --upgrade pip
& $venvPy -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing packages failed. If you have a very new Python, try Python 3.12."
    exit 1
}
& $venvPy -m pip install --no-deps openwakeword
if (Get-ChildItem env: | Where-Object { $_.Name -like "AWP_ROOT*" }) {
    Write-Host "==> Ansys found: installing PyMAPDL"
    & $venvPy -m pip install ansys-mapdl-core
}

Write-Host "==> Checking Ollama (runs the AI model locally)"
if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        winget install -e --id Ollama.Ollama --accept-source-agreements --accept-package-agreements
        $env:Path += ";$env:LOCALAPPDATA\Programs\Ollama"
    } else {
        Write-Host "Please install Ollama from https://ollama.com/download and run this script again."
        exit 1
    }
}
try {
    Invoke-RestMethod http://localhost:11434/api/tags -TimeoutSec 3 | Out-Null
} catch {
    Write-Host "Starting the Ollama server..."
    Start-Process ollama -ArgumentList "serve" -WindowStyle Hidden
    Start-Sleep -Seconds 5
}

Write-Host "==> Downloading models (one time, several GB)"
& $venvPy -m jarvis --setup
if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "Done! Double-click start_jarvis.bat (or run: .venv\Scripts\python -m jarvis)"
}
