[CmdletBinding()]
param([switch]$Uninstall)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot/dev-common.ps1"
$context = Get-DevContext (Split-Path -Parent $PSScriptRoot)
$destination = (Join-Path $context.GitDir 'humorpedia-dev-hooks').Replace('\', '/')
$configured = & git -C $context.Root config --get core.hooksPath
if ($Uninstall) {
    if ($configured -eq $destination) {
        Invoke-DevGit $context.Root @('config', '--local', '--unset', 'core.hooksPath')
        Invoke-DevGit $context.Root @('config', '--local', '--unset', 'humorpedia.devRoot')
        Invoke-DevGit $context.Root @('config', '--local', '--unset', 'humorpedia.devPowerShell')
    }
    Write-Host 'Local Docker hooks disabled. Installed files and sync history are preserved.'
    return
}
if ($configured -and $configured -ne $destination) { throw 'An existing core.hooksPath is configured; refusing to overwrite it.' }
foreach ($name in @('post-checkout', 'post-merge')) {
    if (-not $configured -and (Test-Path (Join-Path $context.GitDir "hooks/$name"))) {
        throw "An existing $name hook needs explicit integration; it was preserved."
    }
}
# Prefer PowerShell 7, but store an absolute executable path for Git outside Codex too.
$shell = Get-Command pwsh -ErrorAction SilentlyContinue
if (-not $shell) { $shell = Get-Command powershell -ErrorAction Stop }
New-Item -ItemType Directory -Path $destination -Force | Out-Null
Copy-Item -LiteralPath "$PSScriptRoot/dev-common.ps1", "$PSScriptRoot/dev-sync.ps1" -Destination $destination -Force
Copy-Item -Path "$($context.Root)/.githooks/*" -Destination $destination -Force
Invoke-DevGit $context.Root @('config', '--local', 'humorpedia.devRoot', $context.Root.Replace('\', '/'))
Invoke-DevGit $context.Root @('config', '--local', 'humorpedia.devPowerShell', $shell.Source.Replace('\', '/'))
Invoke-DevGit $context.Root @('config', '--local', 'core.hooksPath', $destination)
Write-Host "Docker hooks installed for $($context.Root). Linked worktrees are ignored."
