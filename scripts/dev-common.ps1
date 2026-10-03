# Shared by the checkout scripts and the installed hook fallback (PowerShell 5.1+).
function Invoke-DevGit {
    param([string]$Root, [string[]]$Arguments)
    $result = & git -C $Root @Arguments
    if ($LASTEXITCODE -ne 0) { throw "git $($Arguments -join ' ') failed ($LASTEXITCODE)" }
    return $result
}

function Get-DevContext {
    param([string]$Root)
    $rootPath = [IO.Path]::GetFullPath($Root).TrimEnd('\', '/')
    if (-not (Test-Path -LiteralPath (Join-Path $rootPath '.git') -PathType Container)) {
        throw 'Docker is managed only from the primary checkout, never a linked worktree.'
    }
    $top = Invoke-DevGit $rootPath @('rev-parse', '--show-toplevel')
    if ([IO.Path]::GetFullPath($top).TrimEnd('\', '/') -ne $rootPath) { throw 'Run from the repository root.' }
    $configuredRoot = & git -C $rootPath config --local --get humorpedia.devRoot
    if ($configuredRoot -and [IO.Path]::GetFullPath($configuredRoot).TrimEnd('\', '/') -ne $rootPath) {
        throw 'This is not the configured primary checkout.'
    }
    [pscustomobject]@{
        Root = $rootPath
        GitDir = Join-Path $rootPath '.git'
        StateFile = Join-Path $rootPath '.git/humorpedia-dev-state.json'
        Branch = Invoke-DevGit $rootPath @('branch', '--show-current')
        Head = Invoke-DevGit $rootPath @('rev-parse', 'HEAD')
    }
}

function Get-DevInputs {
    param([string]$Root)
    $frontend = @('frontend/package.json', 'frontend/yarn.lock')
    $build = $frontend + @('backend/Dockerfile', 'backend/.dockerignore', 'backend/start.sh',
        'frontend/Dockerfile', 'frontend/.dockerignore', 'docker-compose.yml',
        'docker-compose.override.yml', 'docker-compose.override.yaml', '.env')
    $build += @(Get-ChildItem -LiteralPath "$Root/backend" -Filter 'requirements*.txt' | ForEach-Object { 'backend/' + $_.Name })
    $hashes = @{}
    foreach ($group in @(@{Name='Build'; Paths=$build}, @{Name='Frontend'; Paths=$frontend})) {
        [string[]]$paths = $group.Paths
        # PS5/NLS and PS7/ICU sort '-' differently; fingerprints must be shared.
        [Array]::Sort($paths, [StringComparer]::Ordinal)
        $lines = foreach ($path in $paths) {
            $file = Join-Path $Root $path
            $hash = 'missing'
            if (Test-Path -LiteralPath $file -PathType Leaf) {
                # Git/Windows writes CRLF; backend startup normalizes start.sh to LF.
                # These inputs are text, so only content changes invalidate the cache.
                $content = [IO.File]::ReadAllText($file).Replace("`r`n", "`n")
                $fileSha = [Security.Cryptography.SHA256]::Create()
                try { $hash = [BitConverter]::ToString($fileSha.ComputeHash([Text.Encoding]::UTF8.GetBytes($content))).Replace('-', '') }
                finally { $fileSha.Dispose() }
            }
            "$path=$hash"
        }
        $sha = [Security.Cryptography.SHA256]::Create()
        try { $hashes[$group.Name] = [BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes(($lines -join "`n")))).Replace('-', '') }
        finally { $sha.Dispose() }
    }
    [pscustomobject]$hashes
}

function Read-DevState {
    param([string]$Path)
    if (Test-Path -LiteralPath $Path) {
        try { Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json } catch { return $null }
    }
}

function Get-DevComposeConfiguration {
    param([string]$Root)
    # config can contain expanded secrets: retain only a SHA256, never print or save it.
    $config = & docker compose --project-directory $Root config --format json
    if ($LASTEXITCODE -ne 0) { throw 'Cannot resolve effective Compose configuration.' }
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        $hash = [BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes(($config -join "`n")))).Replace('-', '')
        $resolved = $config | ConvertFrom-Json
        [pscustomobject]@{Hash=$hash; MongoImage=$resolved.services.mongodb.image}
    }
    finally { $sha.Dispose() }
}

function Get-DevContainers {
    $json = & docker inspect humorpedia-backend humorpedia-frontend humorpedia-mongodb
    if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect the local Docker stack.' }
    @($json | ConvertFrom-Json)
}

function Assert-DevMounts {
    param([string]$Root, [object[]]$Containers)
    foreach ($container in $Containers) {
        if ($container.Name -eq '/humorpedia-mongodb') { continue }
        $service = $container.Name.Replace('/humorpedia-', '')
        $mount = @($container.Mounts | Where-Object { $_.Destination -eq '/app' })
        $expected = ($Root.Replace('\', '/').TrimEnd('/') + '/' + $service).ToLowerInvariant()
        $actual = $mount[0].Source.Replace('\', '/').ToLowerInvariant()
        # Docker Desktop can report either C:/... or /run/desktop/mnt/host/c/....
        if ($actual -ne $expected -and $actual -ne ('/run/desktop/mnt/host/' + $expected.Replace(':', ''))) {
            throw "Container $service is mounted from another checkout: $actual"
        }
    }
}

function Assert-DevContainers {
    param([string]$Root, [object[]]$Containers)
    Assert-DevMounts $Root $Containers
    foreach ($container in $Containers) {
        if (-not $container.State.Running) { throw "Container $($container.Name) is stopped." }
        $tagImage = & docker image inspect $container.Config.Image --format '{{.Id}}'
        if ($LASTEXITCODE -ne 0 -or $tagImage -ne $container.Image) {
            throw "Image tag differs from the running container: $($container.Name)"
        }
        if ($container.Name -eq '/humorpedia-mongodb' -and $container.State.Health.Status -ne 'healthy') { throw 'MongoDB is not healthy.' }
    }
}

function Assert-DevExistingCheckout {
    param([string]$Root, [string]$AutoMongoImage)
    $names = @(& docker ps -a --format '{{.Names}}' | Where-Object { $_ -in @('humorpedia-backend', 'humorpedia-frontend', 'humorpedia-mongodb') })
    if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect Docker before sync.' }
    if ($names.Count) {
        $json = & docker inspect @names
        if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect existing app containers.' }
        $containers = $json | ConvertFrom-Json
        Assert-DevMounts $Root $containers
        if ($AutoMongoImage) {
            $mongo = @($containers | Where-Object { $_.Name -eq '/humorpedia-mongodb' })
            if ($mongo.Count -and $mongo[0].Config.Image -ne $AutoMongoImage) {
                throw 'MongoDB image differs from the existing shared database. Automatic branch sync cannot upgrade/downgrade it; validate the database change separately.'
            }
        }
    }
}

function Assert-DevClean {
    param([object]$Context)
    if (Invoke-DevGit $Context.Root @('status', '--porcelain')) { throw 'There are uncommitted changes. Commit or save them explicitly before returning to main.' }
    foreach ($marker in @('MERGE_HEAD', 'CHERRY_PICK_HEAD', 'REVERT_HEAD', 'rebase-merge', 'rebase-apply')) {
        if (Test-Path -LiteralPath (Join-Path $Context.GitDir $marker)) { throw 'Finish the active Git operation first.' }
    }
}
