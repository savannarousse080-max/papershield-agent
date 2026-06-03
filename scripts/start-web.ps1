param(
  [int]$Port = 8000,
  [string]$Provider = "mock"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$env:PAPERSHIELD_LLM_PROVIDER = $Provider
$env:PAPERSHIELD_WEB_PORT = "$Port"

Write-Host "Starting PaperShield Web Demo on http://127.0.0.1:$Port"
Write-Host "Provider: $env:PAPERSHIELD_LLM_PROVIDER"
Write-Host "Health check: http://127.0.0.1:$Port/healthz"

python -m uvicorn web.app:app --host 127.0.0.1 --port $Port
