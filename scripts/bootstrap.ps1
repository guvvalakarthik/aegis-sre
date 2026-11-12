$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python 3.12+ is required. Install it from python.org or your approved package source."
}

python "$repoRoot/scripts/check-toolchain.py"
if ($LASTEXITCODE -ne 0) {
    throw "Prerequisite check failed. Resolve the diagnostics before bootstrapping."
}

$venvPython = Join-Path $repoRoot ".venv/Scripts/python.exe"
if (-not (Test-Path $venvPython)) {
    python -m venv (Join-Path $repoRoot ".venv")
}

& $venvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) {
    throw "pip upgrade failed."
}
& $venvPython -m pip install -e "$repoRoot[dev]"
if ($LASTEXITCODE -ne 0) {
    throw "Project installation failed."
}

Write-Host "Bootstrap complete. Activate with: .\.venv\Scripts\Activate.ps1"
