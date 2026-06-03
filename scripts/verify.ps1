param(
  [string]$Provider = "mock"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$env:PAPERSHIELD_LLM_PROVIDER = $Provider

Write-Host "PaperShield verify: provider=$env:PAPERSHIELD_LLM_PROVIDER"

python main.py doctor
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

python -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

python main.py eval-fixtures --json
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "PaperShield verification complete."
