# ==============================================================================
# run_all_checks.ps1 — PowerShell runner for C-to-RTL Formal Equivalence Checking
# ==============================================================================
# Course: Formal Verification
# ==============================================================================

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir

Set-Location $RepoRoot

Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host " Running Full C-to-RTL Formal Equivalence Checking Suite" -ForegroundColor Cyan
Write-Host " Course: Formal Verification" -ForegroundColor Cyan
Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host ""

# Find python executable (prefer venv if present)
$PythonPath = "python"
if (Test-Path "$RepoRoot\..\venv\Scripts\python.exe") {
    $PythonPath = "$RepoRoot\..\venv\Scripts\python.exe"
} elseif (Test-Path "$RepoRoot\venv\Scripts\python.exe") {
    $PythonPath = "$RepoRoot\venv\Scripts\python.exe"
}

# 1. Run Python CLI on both valid and buggy designs
& $PythonPath -m src.cli --benchmark all --both

# 2. Run pytest suite
Write-Host ""
Write-Host "==================================================================" -ForegroundColor Cyan
Write-Host " Running Automated Pytest Verification Suite" -ForegroundColor Cyan
Write-Host "==================================================================" -ForegroundColor Cyan
& $PythonPath -m pytest tests/test_equivalence.py -v

Write-Host ""
Write-Host "==================================================================" -ForegroundColor Green
Write-Host " All Formal Equivalence Checks Completed Successfully!" -ForegroundColor Green
Write-Host "==================================================================" -ForegroundColor Green

