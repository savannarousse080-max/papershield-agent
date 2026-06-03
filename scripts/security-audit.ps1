$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

@'
import importlib.util
import sys

missing = [name for name in ("pip_audit", "bandit", "ruff") if importlib.util.find_spec(name) is None]
if missing:
    print("Missing security tooling: " + ", ".join(missing))
    print("Install with: python -m pip install -r requirements-dev.txt")
    sys.exit(2)
'@ | python -
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

python -m pip_audit -r requirements.txt
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

python -m pip_audit -r requirements-optional.txt
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

python -m bandit -q -r main.py agent scorer utils web
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

python -m ruff check main.py agent scorer utils web tests
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "PaperShield security audit complete."
