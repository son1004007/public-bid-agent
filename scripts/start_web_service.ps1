# Loopback-only staging; not a production deployment.
param([switch]$ValidateOnly)
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
# Explicit selection, never create or repair existing ACLs in the launcher.
$media = $env:BID_LOCAL_PRIVATE_MEDIA_ROOT
$expectedMedia = Join-Path $env:USERPROFILE "PublicBidAgent-private-media"
if (-not $media -or $media -ne $expectedMedia -or -not (Test-Path -LiteralPath $media -PathType Container)) {
    throw "Explicit protected private-media root is required"
}
foreach ($p in @($env:USERPROFILE, $media)) {
    if ((Get-Item -LiteralPath $p -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw "Private-media path cannot be a reparse point"
    }
}
$identity = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$trusted = @($identity, 'S-1-5-18', 'S-1-5-32-544')
$parentAcl = Get-Acl -LiteralPath $env:USERPROFILE
foreach ($rule in $parentAcl.GetAccessRules($true, $true, [Security.Principal.SecurityIdentifier])) {
    if ($rule.AccessControlType -eq 'Allow' -and $rule.IdentityReference.Value -notin $trusted -and
        -not ($rule.PropagationFlags -band [Security.AccessControl.PropagationFlags]::InheritOnly) -and
        (([int64]$rule.FileSystemRights -band 0xD0156) -ne 0)) {
        throw "Private-media parent permits unapproved mutation"
    }
}
$acl = Get-Acl -LiteralPath $media
$rules = @($acl.GetAccessRules($true, $true, [Security.Principal.SecurityIdentifier]))
$inherit = [Security.AccessControl.InheritanceFlags]::ContainerInherit -bor [Security.AccessControl.InheritanceFlags]::ObjectInherit
if (-not $acl.AreAccessRulesProtected -or $acl.GetOwner([Security.Principal.SecurityIdentifier]).Value -notin $trusted -or
    $rules.Count -ne 3 -or @($rules | Where-Object {
        $_.IdentityReference.Value -notin $trusted -or $_.AccessControlType -ne 'Allow' -or
        $_.IsInherited -or $_.FileSystemRights -ne [Security.AccessControl.FileSystemRights]::FullControl -or
        $_.InheritanceFlags -ne $inherit -or $_.PropagationFlags -ne [Security.AccessControl.PropagationFlags]::None
    }).Count -ne 0 -or @($rules | ForEach-Object { $_.IdentityReference.Value } | Sort-Object -Unique).Count -ne 3) {
    throw "Private-media ACL validation failed"
}
# Validate settings before launching. No migration, account generation, or directory creation.
& $py (Join-Path $repo "server\manage.py") check --settings=bid_server.settings.local
if ($LASTEXITCODE -ne 0) { throw "Local settings validation failed" }
if ($ValidateOnly) {
    Write-Host "PRIVATE_MEDIA_PREFLIGHT_PASS"
    exit 0
}
Write-Host "Loopback-only workspace at http://127.0.0.1:8000/workspace"
& $py (Join-Path $repo "server\manage.py") runserver --settings=bid_server.settings.local --noreload "127.0.0.1:8000"
exit $LASTEXITCODE
