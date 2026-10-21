param(
    [Parameter(Mandatory = $true)][string]$BuildDirectory,
    [string]$PlaywrightModules,
    [string]$ChromiumChannel = '',
    [int]$Port = 18001
)
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$buildPath = (Resolve-Path -LiteralPath $BuildDirectory).Path
if (-not (Test-Path -LiteralPath (Join-Path $buildPath 'index.html'))) { throw 'Нет production build/index.html' }
$runId = [guid]::NewGuid().ToString('N')
$scratch = Join-Path ([IO.Path]::GetTempPath()) "humorpedia-browser-$runId"
$snapshot = Join-Path $scratch 'source'
$envFile = Join-Path $scratch 'container.env'
$containerName = "humorpedia-browser-$runId"
$oldNodePath = $env:NODE_PATH
$oldRunId = $env:SMOKE_RUN_ID
$oldBaseUrl = $env:SMOKE_BASE_URL
$oldChannel = $env:SMOKE_BROWSER_CHANNEL
$oldArtifacts = $env:SMOKE_ARTIFACT_DIR
New-Item -ItemType Directory -Path $snapshot -Force | Out-Null
$started = $false
Push-Location $projectRoot
try {
    # Только опубликованный код приложения; параллельное dirty-дерево не попадает в процесс.
    $archive = Join-Path $scratch 'source.tar'
    git archive --format=tar --output $archive HEAD backend scripts
    if ($LASTEXITCODE -ne 0) { throw 'Не удалось экспортировать HEAD' }
    tar -xf $archive -C $snapshot
    if ($LASTEXITCODE -ne 0) { throw 'Не удалось распаковать HEAD' }
    $harness = Join-Path $snapshot 'scripts/browser-smoke'
    New-Item -ItemType Directory -Path $harness -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'server.py') -Destination (Join-Path $harness 'server.py')
    $backend = @(docker inspect humorpedia-backend | ConvertFrom-Json)[0]
    if ($LASTEXITCODE -ne 0) { throw 'Нужен существующий local-first backend-контейнер' }
    $networks = @($backend.NetworkSettings.Networks.PSObject.Properties.Name)
    if ($networks.Count -ne 1) { throw 'Нельзя однозначно выбрать Docker network' }
    # Учётные данные Mongo передаются в env-file и не выводятся в журнал.
    $mongoSettings = @($backend.Config.Env | Where-Object { $_ -match '^MONGO_(URL|HOST|PORT|USER|PASSWORD|AUTH_SOURCE)=' })
    $settings = $mongoSettings + @("DB_NAME=humorpedia_browser_test_$runId", "SMOKE_RUN_ID=$runId", 'SMOKE_BIND=0.0.0.0', 'SMOKE_PORT=8001', 'BROWSER_BUILD_DIR=/browser-build')
    [IO.File]::WriteAllLines($envFile, $settings, [Text.UTF8Encoding]::new($false))
    docker run --detach --rm --name $containerName --network $networks[0] --publish "127.0.0.1:${Port}:8001" --env-file $envFile --mount "type=bind,source=$snapshot,target=/smoke,readonly" --mount "type=bind,source=$buildPath,target=/browser-build,readonly" --workdir /smoke/backend $backend.Image python /smoke/scripts/browser-smoke/server.py | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Smoke-контейнер не запущен' }
    $started = $true
    $baseUrl = "http://127.0.0.1:$Port"
    $ready = $false
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        try {
            $status = Invoke-RestMethod "$baseUrl/__browser_smoke__/status" -TimeoutSec 1
            if ($status.run_id -eq $runId) { $ready = $true; break }
        } catch { Start-Sleep -Milliseconds 500 }
    }
    if (-not $ready) { docker logs --tail 35 $containerName; throw 'Smoke-сервер не готов' }
    if ($PlaywrightModules) { $env:NODE_PATH = $PlaywrightModules }
    $env:SMOKE_RUN_ID = $runId
    $env:SMOKE_BASE_URL = $baseUrl
    $env:SMOKE_BROWSER_CHANNEL = $ChromiumChannel
    $env:SMOKE_ARTIFACT_DIR = Join-Path $scratch 'artifacts'
    node (Join-Path $PSScriptRoot 'run.cjs')
    if ($LASTEXITCODE -ne 0) { throw "Browser smoke не прошёл; артефакты: $scratch" }
} finally {
    if ($started) {
        docker stop --time 20 $containerName | Out-Null
        if ($LASTEXITCODE -ne 0) { Write-Warning "Не подтверждена остановка $containerName" }
    }
    if (Test-Path -LiteralPath $envFile) { Remove-Item -LiteralPath $envFile }
    $env:NODE_PATH = $oldNodePath
    $env:SMOKE_RUN_ID = $oldRunId
    $env:SMOKE_BASE_URL = $oldBaseUrl
    $env:SMOKE_BROWSER_CHANNEL = $oldChannel
    $env:SMOKE_ARTIFACT_DIR = $oldArtifacts
    Pop-Location
}
