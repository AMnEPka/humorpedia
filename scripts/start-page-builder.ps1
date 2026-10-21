[CmdletBinding()]
param(
    [switch]$Stop,
    [string]$QueueRoot
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$workerScript = Join-Path $PSScriptRoot 'page-builder\worker.py'
if (-not $QueueRoot) {
    $QueueRoot = Join-Path $repoRoot 'var\page-builder'
}
$QueueRoot = [IO.Path]::GetFullPath($QueueRoot)
$workerState = Join-Path $QueueRoot 'worker.json'

function Quote-ProcessArgument([string]$Value) {
    '"' + $Value.Replace('"', '\"') + '"'
}

function Get-WorkerProcess([int]$ProcessId) {
    if ($ProcessId -le 0) { return $null }
    $process = Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId" -ErrorAction SilentlyContinue
    if ($process -and $process.CommandLine -and $process.CommandLine.Contains($workerScript)) {
        return $process
    }
    return $null
}

if ($Stop) {
    if (-not (Test-Path -LiteralPath $workerState)) {
        Write-Output 'Исполнитель не запущен: worker.json отсутствует.'
        exit 0
    }
    try { $state = Get-Content -LiteralPath $workerState -Raw -Encoding UTF8 | ConvertFrom-Json }
    catch { throw "Не удалось прочитать состояние исполнителя: $($_.Exception.Message)" }
    $process = Get-WorkerProcess ([int]$state.pid)
    if (-not $process) {
        Write-Output 'Активный процесс исполнителя не найден.'
        exit 0
    }
    & taskkill.exe /PID $process.ProcessId /T /F | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Stop-Process -Id $process.ProcessId -Force -ErrorAction Stop
    }
    Write-Output "Исполнитель остановлен (PID $($process.ProcessId))."
    exit 0
}

$pythonExe = $null
$pythonArgs = @()
$bundledPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
if (Test-Path -LiteralPath $bundledPython) {
    $pythonExe = $bundledPython
} elseif (Get-Command py.exe -ErrorAction SilentlyContinue) {
    $pythonExe = (Get-Command py.exe).Source
    $pythonArgs = @('-3')
} elseif (Get-Command python.exe -ErrorAction SilentlyContinue) {
    $pythonExe = (Get-Command python.exe).Source
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonExe = (Get-Command python).Source
}
if (-not $pythonExe) { throw 'Python 3 не найден. Ожидается py -3, python или bundled runtime Codex.' }

New-Item -ItemType Directory -Force -Path $QueueRoot | Out-Null
if (Test-Path -LiteralPath $workerState) {
    try { $state = Get-Content -LiteralPath $workerState -Raw -Encoding UTF8 | ConvertFrom-Json }
    catch { $state = $null }
    $existing = if ($state) { Get-WorkerProcess ([int]$state.pid) } else { $null }
    if ($existing) {
        Write-Output "Исполнитель уже запущен (PID $($existing.ProcessId)); очередь: $QueueRoot"
        exit 0
    }
}

$argumentList = @($pythonArgs) + @(
    (Quote-ProcessArgument $workerScript),
    '--queue-root', (Quote-ProcessArgument $QueueRoot)
)
$process = Start-Process -FilePath $pythonExe -ArgumentList $argumentList -WorkingDirectory $repoRoot -WindowStyle Hidden -PassThru
Write-Output "Запущен локальный исполнитель Humorpedia (PID $($process.Id)); очередь: $QueueRoot"
