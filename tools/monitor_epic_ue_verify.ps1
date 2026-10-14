[CmdletBinding()]
param(
    [string]$LogPath = (Join-Path ([Environment]::GetFolderPath([Environment+SpecialFolder]::LocalApplicationData)) 'EpicGamesLauncher\Saved\Logs\EpicGamesLauncher.log'),
    [ValidateRange(1, 180)][int]$TimeoutMinutes = 45,
    [ValidateRange(1, 60)][int]$PollSeconds = 30
)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $LogPath -PathType Leaf)) { throw 'Epic verification log was not found. Pass -LogPath explicitly.' }
$deadline = (Get-Date).AddMinutes($TimeoutMinutes)
$currentLog = Get-Item -LiteralPath $LogPath
$offset = $currentLog.Length
$createdAt = $currentLog.CreationTimeUtc

while ((Get-Date) -lt $deadline) {
    Start-Sleep -Seconds $PollSeconds
    $currentLog = Get-Item -LiteralPath $LogPath -ErrorAction SilentlyContinue
    if (-not $currentLog) { continue }
    if ($currentLog.Length -lt $offset -or $currentLog.CreationTimeUtc -ne $createdAt) {
        $offset = 0
        $createdAt = $currentLog.CreationTimeUtc
    }
    if ($currentLog.Length -eq $offset) { continue }
    $stream = [IO.FileStream]::new($currentLog.FullName, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete)
    $reader = $null
    try {
        [void]$stream.Seek($offset, [IO.SeekOrigin]::Begin)
        $reader = [IO.StreamReader]::new($stream, [Text.Encoding]::UTF8, $true)
        $recent = $reader.ReadToEnd()
        $offset = $stream.Position
    } finally {
        if ($reader) { $reader.Dispose() } else { $stream.Dispose() }
    }

    if ($recent -match "Installer complete\. Success:1") {
        Write-Output "VERIFY_COMPLETE"
        exit 0
    }

    if ($recent -match "EBuildPatchInstallError" -and
        $recent -notmatch "Constructing file") {
        Write-Output "VERIFY_ERROR"
        exit 2
    }

    # Never echo account data, credential URLs or filenames from launcher logs.
    if ($recent -match 'Install|Verif|Constructing file|Completing:') { Write-Output 'VERIFY_IN_PROGRESS' }
}

Write-Output "VERIFY_TIMEOUT"
exit 3
