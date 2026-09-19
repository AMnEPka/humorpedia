[CmdletBinding()]
param(
    [switch]$SkipBuild,
    [switch]$SkipFrontendDependencies
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot

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

Push-Location $projectRoot
try {
    Invoke-DockerCompose -Arguments @('version')

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
    Write-Host 'Локальный Docker-стек синхронизирован с текущей веткой.'
} finally {
    Pop-Location
}
