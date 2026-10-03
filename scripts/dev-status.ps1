[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot/dev-common.ps1"
$context = Get-DevContext (Split-Path -Parent $PSScriptRoot)
$state = Read-DevState $context.StateFile
$inputs = Get-DevInputs $context.Root
Write-Host "Checkout: $($context.Root)"
Write-Host "Branch: $($context.Branch); HEAD: $($context.Head.Substring(0, 7))"
$dirty = @(Invoke-DevGit $context.Root @('status', '--porcelain'))
Write-Host "Uncommitted paths: $($dirty.Count) (source changes use reload/HMR)"
if (-not $state) { throw 'No successful sync recorded. Run scripts/dev-sync.ps1.' }
Write-Host "Last sync: $($state.Status); $($state.Branch) $($state.Head.Substring(0, 7)); $($state.UpdatedAt)"
if ($state.Status -ne 'synced') { throw 'The last Docker sync did not succeed. Run scripts/dev-sync.ps1.' }
if ($state.Root -ne $context.Root -or $state.Branch -ne $context.Branch) { throw 'The current checkout has not been synchronized.' }
if ($state.Inputs.Build -ne $inputs.Build -or $state.Inputs.Frontend -ne $inputs.Frontend) { throw 'Docker configuration or dependencies changed. Run scripts/dev-sync.ps1.' }
if ($state.Configuration -ne (Get-DevComposeConfiguration $context.Root).Hash) { throw 'Effective Compose configuration changed (including environment overrides). Run scripts/dev-sync.ps1.' }
$containers = Get-DevContainers
Assert-DevContainers $context.Root $containers
foreach ($container in $containers) {
    if ($state.Images.($container.Name) -ne $container.Image) { throw "Image changed outside dev-sync: $($container.Name)" }
}
foreach ($uri in @('http://localhost:8001/api/health', 'http://localhost:3000')) {
    $response = Invoke-WebRequest -UseBasicParsing -Uri $uri -TimeoutSec 5
    if ($response.StatusCode -ne 200) { throw "Endpoint unavailable: $uri" }
    Write-Host "OK: $uri"
}
& docker compose -f "$($context.Root)/docker-compose.yml" ps
if ($LASTEXITCODE -ne 0) { throw 'docker compose ps failed.' }
$hooks = & git -C $context.Root config --get core.hooksPath
Write-Host "Hooks: $hooks"
Write-Host 'Docker mounts this checkout; dependencies match the last successful sync. MongoDB data is shared between branches.'
