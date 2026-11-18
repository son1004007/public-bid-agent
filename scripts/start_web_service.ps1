# Loopback-only staging; not a production deployment.
$ErrorActionPreference = "Stop"
$repo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$py = Join-Path $env:LOCALAPPDATA "PublicBidAgent\sm02-venv\Scripts\python.exe"
$env:DJANGO_SETTINGS_MODULE = "bid_server.settings.local"
$env:PYTHONPATH = Join-Path $repo "server"
$secretDir = Join-Path $env:LOCALAPPDATA "PublicBidAgent\local"
$secretFile = Join-Path $secretDir "django_secret_key.txt"
$dbConfig = Join-Path $env:LOCALAPPDATA "PublicBidAgent\sm03-postgres\connection.private.json"
if (-not (Test-Path -LiteralPath $py)) { throw "Isolated Python venv missing" }
if (-not (Test-Path -LiteralPath $dbConfig)) { throw "PostgreSQL private settings missing" }
if (-not (Test-Path -LiteralPath $secretFile -PathType Leaf)) {
    throw "Private signing key missing; provision the key in the protected local directory first"
}
if (Test-Path Env:BID_LOCAL_SECRET_KEY) { throw "Plaintext signing key environment is not permitted" }
# Validate settings before launching. No migration, account generation, or directory creation.
& $py (Join-Path $repo "server\manage.py") check --settings=bid_server.settings.local
if ($LASTEXITCODE -ne 0) { throw "Local settings validation failed" }
Write-Host "Loopback-only workspace at http://127.0.0.1:8000/workspace"
& $py (Join-Path $repo "server\manage.py") runserver --settings=bid_server.settings.local --noreload "127.0.0.1:8000"
exit $LASTEXITCODE
