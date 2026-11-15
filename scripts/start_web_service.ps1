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
if (-not (Test-Path -LiteralPath $secretFile)) {
    New-Item -ItemType Directory -Force -Path $secretDir | Out-Null
    $key = & $py -c "import secrets; print(secrets.token_urlsafe(64))"
    if ($LASTEXITCODE -ne 0 -or $key.Length -lt 40) { throw "Secret generation failed" }
    [System.IO.File]::WriteAllText($secretFile, $key)
}
Write-Host "Loopback-only workspace at http://127.0.0.1:8000/workspace"
& $py (Join-Path $repo "server\manage.py") runserver --noreload "127.0.0.1:8000"
exit $LASTEXITCODE
