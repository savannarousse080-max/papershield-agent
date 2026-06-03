param(
  [string]$Provider = "mock",
  [string]$BaseUrl = "",
  [string]$Model = "mock",
  [string]$ApiKey = "",
  [string]$PromptProfile = "default",
  [int]$Timeout = 120,
  [int]$MaxRetries = 1
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$env:PAPERSHIELD_LLM_PROVIDER = $Provider
$env:PAPERSHIELD_LLM_BASE_URL = $BaseUrl
$env:PAPERSHIELD_LLM_MODEL = $Model
$env:PAPERSHIELD_API_KEY = $ApiKey
$env:PAPERSHIELD_PROMPT_PROFILE = $PromptProfile
$env:PAPERSHIELD_LLM_TIMEOUT = "$Timeout"
$env:PAPERSHIELD_LLM_MAX_RETRIES = "$MaxRetries"

Write-Host "PaperShield environment loaded for provider=$env:PAPERSHIELD_LLM_PROVIDER"
