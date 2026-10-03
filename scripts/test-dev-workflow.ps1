[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$source = $PSScriptRoot
$fixture = Join-Path ([IO.Path]::GetTempPath()) ('humorpedia-dev-test-' + [guid]::NewGuid())
$primary = Join-Path $fixture 'primary'
$linked = Join-Path $fixture 'linked'
function Assert($Condition, $Message) {
    if (-not $Condition) { throw "FAIL: $Message" }
    Write-Host "PASS: $Message"
}
function Run-Git([string[]]$Arguments) {
    & git @Arguments | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "fixture git failed: $Arguments" }
}
function Expect-Failure([scriptblock]$Action, $Pattern) {
    $caught = $null
    try { & $Action | Out-Null } catch { $caught = $_.Exception.Message }
    Assert ($caught -match $Pattern) "guard rejects $Pattern"
}
New-Item -ItemType Directory -Path $primary -Force | Out-Null
Push-Location $primary
try {
    Run-Git @('init', '-b', 'main')
    Run-Git @('config', 'user.name', 'Dev workflow test')
    Run-Git @('config', 'user.email', 'dev-test@example.invalid')
    Run-Git @('config', 'core.autocrlf', 'false')
    New-Item -ItemType Directory scripts | Out-Null
    Copy-Item "$source\dev-*.ps1" scripts
    Copy-Item "$source/../.githooks" .githooks -Recurse
    New-Item -ItemType Directory backend,frontend | Out-Null
    Set-Content backend/requirements.txt 'fixture dependency'
    Set-Content backend/requirements-dev.txt 'fixture dev dependency'
    Set-Content frontend/package.json '{}'
    Set-Content frontend/yarn.lock 'fixture lock'
    Set-Content README.txt 'fixture'
    Run-Git @('add', '.')
    Run-Git @('commit', '-m', 'fixture')
    Run-Git @('worktree', 'add', '-b', 'helper', $linked)
    $global:hptestDockerCalls = 0
    function docker { $global:hptestDockerCalls++; throw 'Unexpected Docker call' }
    Expect-Failure { & "$linked\scripts\dev-sync.ps1" } 'worktree'
    Assert ($global:hptestDockerCalls -eq 0) 'linked worktree never touches Docker'
    $hashScript = @'
param([string]$Root)
. "$Root/scripts/dev-common.ps1"
Get-DevInputs $Root | ConvertTo-Json -Compress
'@
    $hashFile = Join-Path $primary '.git/compare-inputs.ps1'
    Set-Content -LiteralPath $hashFile $hashScript
    $hash5 = (& powershell -NoProfile -File $hashFile -Root $primary) | ConvertFrom-Json
    $hash7 = (& pwsh -NoProfile -File $hashFile -Root $primary) | ConvertFrom-Json
    Assert ($hash5.Build -eq $hash7.Build -and $hash5.Frontend -eq $hash7.Frontend) 'PS5 and PS7 share the same input fingerprints'

    $global:hptestComposeCalls = New-Object Collections.Generic.List[string]
    $global:hptestContainers = @(
        @{Name='/humorpedia-backend';Image='backend-v1';Config=@{Image='test-backend'};State=@{Running=$true};Mounts=@(@{Destination='/app';Source="$primary/backend"})},
        @{Name='/humorpedia-frontend';Image='frontend-v1';Config=@{Image='test-frontend'};State=@{Running=$true};Mounts=@(@{Destination='/app';Source="$primary/frontend"})},
        @{Name='/humorpedia-mongodb';Image='mongo-v1';Config=@{Image='test-mongo'};State=@{Running=$true;Health=@{Status='healthy'}};Mounts=@()}
    )
    $global:hptestImageIds = @{'test-backend'='backend-v1'; 'test-frontend'='frontend-v1'; 'test-mongo'='mongo-v1'}
    $global:hptestConfig = '{"services":{"mongodb":{"image":"test-mongo"}}}'
    function docker {
        $global:LASTEXITCODE = 0
        if ($args[0] -eq 'inspect') { $global:hptestContainers | ConvertTo-Json -Depth 6; return }
        if ($args[0] -eq 'ps') { 'humorpedia-backend'; 'humorpedia-frontend'; 'humorpedia-mongodb'; return }
        if ($args[0] -eq 'image') { $global:hptestImageIds[$args[2]]; return }
        if ($args -contains 'config') { $global:hptestConfig; return }
        if ($args -contains 'build') { $global:hptestImageIds['test-backend'] = 'backend-v1' }
        $global:hptestComposeCalls.Add(($args -join ' '))
    }
    function Invoke-WebRequest { [pscustomobject]@{StatusCode=200} }
    & scripts/dev-sync.ps1
    $state = Get-Content .git/humorpedia-dev-state.json -Raw | ConvertFrom-Json
    Assert ($state.Status -eq 'synced') 'sync records success only after runtime checks'
    $global:hptestConfig = '{"services":{"mongodb":{"image":"test-mongo","environment":{"DB_NAME":"changed"}}}}'
    Expect-Failure { & scripts/dev-status.ps1 } 'Compose configuration'
    $global:hptestConfig = '{"services":{"mongodb":{"image":"test-mongo"}}}'
    $global:hptestComposeCalls.Clear()
    & scripts/dev-sync.ps1 -Auto
    Assert (-not ($global:hptestComposeCalls | Where-Object { $_ -match 'build|install' })) 'unchanged inputs avoid rebuild and dependency reinstall'
    $lockPath = Join-Path $primary 'frontend/yarn.lock'
    [IO.File]::WriteAllText($lockPath, [IO.File]::ReadAllText($lockPath).Replace("`r`n", "`n"))
    $global:hptestComposeCalls.Clear()
    & scripts/dev-sync.ps1 -Auto
    Assert (-not ($global:hptestComposeCalls | Where-Object { $_ -match 'build|install' })) 'LF and CRLF inputs do not cause false rebuilds'
    Set-Content backend/live.py 'source edit'
    $global:hptestComposeCalls.Clear()
    & scripts/dev-sync.ps1 -Auto
    Assert (-not ($global:hptestComposeCalls | Where-Object { $_ -match 'build|install' })) 'source edits keep using reload without rebuild'
    $global:hptestConfig = '{"services":{"mongodb":{"image":"mongo:6.0"}}}'
    $global:hptestComposeCalls.Clear()
    Expect-Failure { & scripts/dev-sync.ps1 -Auto } 'MongoDB image'
    Assert (-not ($global:hptestComposeCalls | Where-Object { $_ -match 'compose (build|stop|run|up)' })) 'branch sync cannot change the shared MongoDB image automatically'
    $global:hptestConfig = '{"services":{"mongodb":{"image":"test-mongo"}}}'
    $global:hptestImageIds['test-backend'] = 'foreign-build'
    $global:hptestComposeCalls.Clear()
    & scripts/dev-sync.ps1 -Auto
    Assert ($global:hptestComposeCalls -contains 'compose build backend frontend') 'replaced image tag forces rebuild before compose up'
    Set-Content frontend/yarn.lock 'changed dependencies'
    Expect-Failure { & scripts/dev-sync.ps1 -SkipBuild } 'inputs changed'
    $global:hptestComposeCalls.Clear()
    & scripts/dev-sync.ps1 -Auto
    Assert (($global:hptestComposeCalls -contains 'compose build backend frontend') -and ($global:hptestComposeCalls -match 'install --frozen-lockfile')) 'changed dependencies force build and install'
    $global:hptestContainers[0].Mounts[0].Source = 'C:/different/backend'
    $global:hptestComposeCalls.Clear()
    Expect-Failure { & scripts/dev-sync.ps1 -Auto } 'another checkout'
    Assert (-not ($global:hptestComposeCalls | Where-Object { $_ -match 'compose (build|stop|run|up)' })) 'foreign checkout is rejected before Docker mutations'
    $state = Get-Content .git/humorpedia-dev-state.json -Raw | ConvertFrom-Json
    Assert ($state.Status -eq 'failed') 'bad runtime mount cannot record success'
    $global:hptestContainers[0].Mounts[0].Source = "$primary/backend"
    $lock = [IO.File]::Open("$primary/.git/humorpedia-dev.lock", 'OpenOrCreate', 'Write', 'None')
    try { Expect-Failure { & scripts/dev-sync.ps1 } 'Another dev-sync' } finally { $lock.Dispose() }
    Run-Git @('add', '.')
    Run-Git @('commit', '-m', 'sync fixtures')

    & "$primary\scripts\dev-hooks.ps1"
    Assert ($LASTEXITCODE -eq 0) 'hook installation succeeds'
    $hooks = git config --local --get core.hooksPath
    Assert (Test-Path "$hooks\post-checkout") 'hooks installed outside versioned checkout'
    # A minimal fake replaces the external Docker service, not Git/hook dispatch.
    $stub = @'
param([switch]$Auto, [string]$ProjectRoot)
Add-Content -LiteralPath $env:HUMORPEDIA_TEST_MARKER 'sync'
if ($env:HUMORPEDIA_TEST_FAIL -eq '1') { throw 'simulated sync failure' }
'@
    Set-Content scripts/dev-sync.ps1 $stub
    # Explicit installation is the only action that replaces the trusted hook runner.
    & scripts/dev-hooks.ps1
    Run-Git @('add', '.')
    Run-Git @('commit', '-m', 'stub external sync')
    $env:HUMORPEDIA_TEST_MARKER = Join-Path $fixture 'sync.log'
    Run-Git @('switch', '-c', 'feature')
    Assert ((Get-Content $env:HUMORPEDIA_TEST_MARKER).Count -eq 1) 'branch switch invokes sync once'
    Run-Git @('checkout', '--', 'README.txt')
    Assert ((Get-Content $env:HUMORPEDIA_TEST_MARKER).Count -eq 1) 'file checkout does not invoke sync'
    Run-Git @('-C', $linked, 'switch', '-c', 'helper-two')
    Assert ((Get-Content $env:HUMORPEDIA_TEST_MARKER).Count -eq 1) 'linked branch switch does not invoke sync'
    $env:HUMORPEDIA_TEST_FAIL = '1'
    & git switch -c hook-failure | Out-Null
    Assert ($LASTEXITCODE -ne 0) 'failed hook surfaces a nonzero exit'
    Assert ((git branch --show-current) -eq 'hook-failure') 'failed hook leaves actual checkout visible'
    Remove-Item Env:HUMORPEDIA_TEST_FAIL

    $remote = Join-Path $fixture 'origin.git'
    Run-Git @('init', '--bare', $remote)
    Run-Git @('remote', 'add', 'origin', $remote)
    Run-Git @('push', '-u', 'origin', 'main')
    Set-Content README.txt 'dirty'
    Expect-Failure { & scripts/dev-finish.ps1 } 'uncommitted'
    Assert ((git branch --show-current) -eq 'hook-failure') 'dirty finish preserves branch'
    Run-Git @('restore', 'README.txt')
    Set-Content feature.txt 'new change'
    Run-Git @('add', '.')
    Run-Git @('commit', '-m', 'feature change')
    Expect-Failure { & scripts/dev-finish.ps1 } 'merged'
    Assert ((git branch --show-current) -eq 'hook-failure') 'unmerged finish preserves branch'
    # Remote main advances, as it would after a GitHub merge, with local main still behind.
    Run-Git @('push', 'origin', 'HEAD:main')
    $before = (Get-Content $env:HUMORPEDIA_TEST_MARKER).Count
    & scripts/dev-finish.ps1
    Assert ((git branch --show-current) -eq 'main') 'finish returns to main'
    Assert ((git rev-parse HEAD) -eq (git rev-parse origin/main)) 'finish fast-forwards to fetched main'
    Assert ((Get-Content $env:HUMORPEDIA_TEST_MARKER).Count -eq ($before + 1)) 'finish syncs once after final HEAD'
    Assert (-not (git status --porcelain)) 'finish leaves a clean checkout'
    Run-Git @('switch', '-c', 'squash-feature')
    Set-Content squash.txt 'squash change'
    Run-Git @('add', '.')
    Run-Git @('commit', '-m', 'feature to squash')
    $prHead = git rev-parse HEAD
    Run-Git @('-c', 'core.hooksPath=', 'switch', 'main')
    Run-Git @('checkout', 'squash-feature', '--', 'squash.txt')
    Run-Git @('commit', '-m', 'squashed feature')
    Run-Git @('push', 'origin', 'main')
    $global:hptestPr = @{state='MERGED';headRefOid=$prHead;baseRefName='main';mergeCommit=@{oid=(git rev-parse HEAD)}}
    function gh { $global:LASTEXITCODE = 0; $global:hptestPr | ConvertTo-Json }
    Run-Git @('switch', 'squash-feature')
    & scripts/dev-finish.ps1 -PullRequest 42
    Assert ((git branch --show-current) -eq 'main') 'confirmed squash PR also returns to main'
    Assert ((git rev-parse HEAD) -eq (git rev-parse origin/main)) 'squash finish uses fetched main'
    & scripts/dev-hooks.ps1 -Uninstall
    Assert (-not (git config --local --get core.hooksPath)) 'uninstall removes only local hook setting'
} finally {
    Pop-Location
    Remove-Item Env:HUMORPEDIA_TEST_MARKER -ErrorAction SilentlyContinue
    Remove-Item Env:HUMORPEDIA_TEST_FAIL -ErrorAction SilentlyContinue
    # Keep fixtures for inspection; they never share the real Docker stack or Mongo volume.
    Write-Host "Fixture: $fixture"
}
