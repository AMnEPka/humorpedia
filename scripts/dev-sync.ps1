[CmdletBinding()]
param(
    [switch]$SkipBuild,
    [switch]$SkipFrontendDependencies,
    [switch]$Auto,
    [string]$ProjectRoot
)

$ErrorActionPreference = 'Stop'
if (-not $ProjectRoot) { $ProjectRoot = Split-Path -Parent $PSScriptRoot }
. "$PSScriptRoot/dev-common.ps1"
$context = Get-DevContext $ProjectRoot
$projectRoot = $context.Root
$inputs = Get-DevInputs $projectRoot
$previous = Read-DevState $context.StateFile
$sameBuild = $previous -and $previous.Status -eq 'synced' -and $previous.Root -eq $projectRoot -and $previous.Inputs.Build -eq $inputs.Build
$sameFrontend = $previous -and $previous.Status -eq 'synced' -and $previous.Inputs.Frontend -eq $inputs.Frontend
if ($SkipBuild -and -not $sameBuild) { throw 'Build inputs changed or no successful sync exists. Run a full dev-sync.' }
if ($SkipFrontendDependencies -and -not $sameFrontend) { throw 'Frontend dependencies changed or no successful sync exists. Run a full dev-sync.' }

function Invoke-DockerCompose {
    param([Parameter(Mandatory = $true)][string[]]$Arguments)

    & docker compose @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose $($Arguments -join ' ') завершился с кодом $LASTEXITCODE"
    }
}

function Wait-HttpEndpoint {
    param(
        [Parameter(Mandatory = $true)][string]$Uri,
        [Parameter(Mandatory = $true)][string]$Name,
        [int]$Attempts = 90
    )

    for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri $Uri -TimeoutSec 3
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 400) {
                Write-Host "$Name готов: $Uri"
                return
            }
        } catch {
            # Сервис может ещё запускаться; окончательную ошибку выдаём после цикла.
        }
        if ($attempt -lt $Attempts) {
            Start-Sleep -Seconds 1
        }
    }
    throw "$Name не стал доступен по адресу $Uri"
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw 'Docker CLI не найден'
}

$lock = $null
try {
    $lock = [IO.File]::Open((Join-Path $context.GitDir 'humorpedia-dev.lock'), [IO.FileMode]::OpenOrCreate, [IO.FileAccess]::Write, [IO.FileShare]::None)
} catch { throw 'Another dev-sync is running. Wait for it before retrying.' }
$state = [ordered]@{Status='syncing'; Root=$projectRoot; Branch=$context.Branch; Head=$context.Head; Inputs=$inputs; UpdatedAt=[DateTime]::UtcNow.ToString('o')}
Push-Location $projectRoot
try {
    $state | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $context.StateFile -Encoding UTF8
    Invoke-DockerCompose -Arguments @('version')
    $configuration = Get-DevComposeConfiguration $projectRoot
    $state.Configuration = $configuration.Hash
    $autoMongoImage = $null
    if ($Auto) { $autoMongoImage = $configuration.MongoImage }
    Assert-DevExistingCheckout $projectRoot $autoMongoImage

    if ($Auto -and $sameBuild) {
        try {
            $running = Get-DevContainers
            Assert-DevContainers $projectRoot $running
            foreach ($container in $running) {
                if ($previous.Images.($container.Name) -ne $container.Image) { $sameBuild = $false }
            }
        } catch { $sameBuild = $false }
    }
    if ($Auto) {
        $SkipBuild = $sameBuild
        $SkipFrontendDependencies = $sameBuild -and $sameFrontend
    }
    Write-Host "Checkout: $($context.Branch) $($context.Head.Substring(0, 7)) ($projectRoot)"

    if (-not $SkipBuild) {
        Invoke-DockerCompose -Arguments @('build', 'backend', 'frontend')
    }

    if (-not $SkipFrontendDependencies) {
        # frontend_node_modules — именованный volume, поэтому обновляем его отдельно от image.
        # Останавливаем dev-server, чтобы yarn не менял используемые им пакеты на лету.
        Invoke-DockerCompose -Arguments @('stop', 'frontend')
        Invoke-DockerCompose -Arguments @(
            'run', '--rm', '--no-deps', 'frontend',
            'yarn', 'install', '--frozen-lockfile'
        )
    }

    Invoke-DockerCompose -Arguments @('up', '-d', '--remove-orphans')
    Wait-HttpEndpoint -Uri 'http://localhost:8001/api/health' -Name 'Backend'
    Wait-HttpEndpoint -Uri 'http://localhost:3000' -Name 'Frontend'

    Invoke-DockerCompose -Arguments @('ps')
    $containers = Get-DevContainers
    Assert-DevContainers $projectRoot $containers
    $images = @{}
    foreach ($container in $containers) { $images[$container.Name] = $container.Image }
    $state.Images = $images
    $state.Status = 'synced'
    $state.UpdatedAt = [DateTime]::UtcNow.ToString('o')
    $state | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $context.StateFile -Encoding UTF8
    Write-Host 'Локальный Docker-стек синхронизирован с текущей веткой.'
} catch {
    $state.Status = 'failed'
    $state.UpdatedAt = [DateTime]::UtcNow.ToString('o')
    $state | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $context.StateFile -Encoding UTF8
    throw
} finally {
    Pop-Location
    $lock.Dispose()
}
