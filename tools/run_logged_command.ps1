[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Command,

    [string]$Label = "command",

    [string]$WorkingDirectory = "",

    [int]$TailLines = 60,

    [int]$KeyLines = 30,

    [string]$ArtifactDirectory = ""
)

$ErrorActionPreference = "Continue"
$projectRoot = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($WorkingDirectory)) {
    $WorkingDirectory = $projectRoot
}
if ([string]::IsNullOrWhiteSpace($ArtifactDirectory)) {
    $ArtifactDirectory = Join-Path $projectRoot ".runtime\codex-tool-runs"
}

New-Item -ItemType Directory -Force -Path $ArtifactDirectory | Out-Null
$safeLabel = ($Label -replace '[^A-Za-z0-9._-]', '_').Trim('_')
if ([string]::IsNullOrWhiteSpace($safeLabel)) {
    $safeLabel = "command"
}
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$suffix = [guid]::NewGuid().ToString("N").Substring(0, 8)
$baseName = "$stamp-$safeLabel-$suffix"
$commandPath = Join-Path $ArtifactDirectory "$baseName.command.ps1"
$stdoutPath = Join-Path $ArtifactDirectory "$baseName.stdout.log"
$stderrPath = Join-Path $ArtifactDirectory "$baseName.stderr.log"
$combinedPath = Join-Path $ArtifactDirectory "$baseName.log"

Set-Content -LiteralPath $commandPath -Value $Command -Encoding utf8
New-Item -ItemType File -Force -Path $combinedPath | Out-Null

$timer = [System.Diagnostics.Stopwatch]::StartNew()
$exitCode = 1
$runError = $null
$hostPath = (Get-Process -Id $PID).Path

try {
    $startArgs = @(
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy", "Bypass",
        "-File", $commandPath
    )
    $process = Start-Process -FilePath $hostPath -ArgumentList $startArgs `
        -WorkingDirectory $WorkingDirectory `
        -RedirectStandardOutput $stdoutPath `
        -RedirectStandardError $stderrPath `
        -Wait -PassThru -WindowStyle Hidden
    $exitCode = [int]$process.ExitCode
}
catch {
    $runError = $_ | Out-String
    Add-Content -LiteralPath $combinedPath -Value $runError -Encoding utf8
    $exitCode = 1
}
finally {
    $timer.Stop()
}

$utf8NoBom = [System.Text.UTF8Encoding]::new($false)
$stdoutText = if (Test-Path -LiteralPath $stdoutPath) { [System.IO.File]::ReadAllText($stdoutPath) } else { "" }
$stderrText = if (Test-Path -LiteralPath $stderrPath) { [System.IO.File]::ReadAllText($stderrPath) } else { "" }
[System.IO.File]::WriteAllText($combinedPath, $stdoutText + $stderrText, $utf8NoBom)

$logItem = Get-Item -LiteralPath $combinedPath -ErrorAction SilentlyContinue
$logBytes = if ($logItem) { $logItem.Length } else { 0 }
$status = if ($exitCode -eq 0) { "ok" } else { "failed" }
$errorPattern = '(?i)(^|\b)(error|failed|failure|fatal|exception|not ok|timed out|denied|panic)(\b|:)'

$keyMatches = @()
if ($logBytes -gt 0) {
    $keyMatches = @(
        Select-String -LiteralPath $combinedPath -Pattern $errorPattern -ErrorAction SilentlyContinue |
            Select-Object -First $KeyLines |
            ForEach-Object { $_.Line.Trim() }
    )
}
$tail = @()
if ($logBytes -gt 0) {
    $tail = @(Get-Content -LiteralPath $combinedPath -Tail $TailLines -ErrorAction SilentlyContinue)
}

Write-Output "TOOL_RESULT"
Write-Output "status=$status"
Write-Output "exit_code=$exitCode"
Write-Output "duration_ms=$([math]::Round($timer.Elapsed.TotalMilliseconds))"
Write-Output "artifact=$combinedPath"
Write-Output "command_script=$commandPath"
Write-Output "stdout_artifact=$stdoutPath"
Write-Output "stderr_artifact=$stderrPath"
Write-Output "log_bytes=$logBytes"
Write-Output "working_directory=$WorkingDirectory"

if ($keyMatches.Count -gt 0) {
    Write-Output "--- key_lines ($($keyMatches.Count)) ---"
    $keyMatches | ForEach-Object { Write-Output $_ }
}

if ($tail.Count -gt 0) {
    Write-Output "--- tail ($($tail.Count)) ---"
    $tail | ForEach-Object { Write-Output $_ }
}

exit $exitCode
