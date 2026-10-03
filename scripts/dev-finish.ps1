[CmdletBinding()]
param([int]$PullRequest = 0)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot/dev-common.ps1"
$context = Get-DevContext (Split-Path -Parent $PSScriptRoot)
Assert-DevClean $context
Invoke-DevGit $context.Root @('fetch', 'origin')
if ($PullRequest) {
    $remote = Invoke-DevGit $context.Root @('remote', 'get-url', 'origin')
    $json = & gh pr view $PullRequest --repo $remote --json 'state,headRefOid,baseRefName,mergeCommit'
    if ($LASTEXITCODE -ne 0) { throw 'Cannot verify the merged pull request.' }
    $pr = $json | ConvertFrom-Json
    if ($pr.state -ne 'MERGED' -or $pr.baseRefName -ne 'main' -or $pr.headRefOid -ne $context.Head -or -not $pr.mergeCommit.oid) {
        throw 'The PR is not merged into main with exactly the current HEAD. No checkout was changed.'
    }
    & git -C $context.Root merge-base --is-ancestor $pr.mergeCommit.oid origin/main
    if ($LASTEXITCODE -ne 0) { throw 'The verified PR merge is absent from fetched origin/main.' }
} else {
    & git -C $context.Root merge-base --is-ancestor $context.Head origin/main
    if ($LASTEXITCODE -ne 0) { throw 'The current branch is not fully merged into origin/main. For a squash/rebase PR pass -PullRequest NUMBER. No checkout was changed.' }
}
& git -C $context.Root merge-base --is-ancestor main origin/main
if ($LASTEXITCODE -ne 0) { throw 'Local main diverged from origin/main. Resolve it explicitly; no reset was performed.' }
# Suppress hooks only for this command sequence, so sync sees the final fetched main.
Invoke-DevGit $context.Root @('-c', 'core.hooksPath=', 'switch', 'main')
Invoke-DevGit $context.Root @('-c', 'core.hooksPath=', 'merge', '--ff-only', 'origin/main')
$syncScript = Join-Path $context.Root 'scripts/dev-sync.ps1'
if (-not (Test-Path "$($context.Root)/scripts/dev-common.ps1")) {
    $syncScript = Join-Path $context.GitDir 'humorpedia-dev-hooks/dev-sync.ps1'
}
& $syncScript -ProjectRoot $context.Root -Auto
