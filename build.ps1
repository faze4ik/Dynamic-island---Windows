param(
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (!(Test-Path $python)) {
    Write-Host "Creating virtual environment..." -ForegroundColor Cyan
    py -3 -m venv .venv
}

if (!$SkipInstall) {
    Write-Host "Installing dependencies..." -ForegroundColor Cyan
    & $python -m pip install --upgrade pip
    & $python -m pip install -r requirements.txt
}

Write-Host "Generating application icon..." -ForegroundColor Cyan
& $python tools\make_icon.py

$dist = Join-Path $PSScriptRoot "dist"
$legacyFolder = Join-Path $dist "DynamicIsland"
$legacyZip = Join-Path $dist "DynamicIsland-Windows.zip"
if (Test-Path $legacyFolder) { Remove-Item $legacyFolder -Recurse -Force }
if (Test-Path $legacyZip) { Remove-Item $legacyZip -Force }

Write-Host "Building DynamicIsland.exe (PyInstaller, one file)..." -ForegroundColor Cyan
& $python -m PyInstaller --noconfirm --clean dynamic_island.spec

$exe = Join-Path $dist "DynamicIsland.exe"
if (!(Test-Path $exe)) {
    throw "Build failed: $exe was not created."
}

Write-Host ""
Write-Host "Done!" -ForegroundColor Green
Write-Host "  EXE: $exe"
Write-Host "  Single file: no _internal folder or extra files are required."
