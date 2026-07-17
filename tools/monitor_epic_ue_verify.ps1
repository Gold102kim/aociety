$logPath = "C:\Users\jingk\AppData\Local\EpicGamesLauncher\Saved\Logs\EpicGamesLauncher.log"
$deadline = (Get-Date).AddMinutes(45)
$startLength = (Get-Item -LiteralPath $logPath).Length

while ((Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 30
    $log = Get-Content -LiteralPath $logPath -Tail 600
    $recent = $log -join "`n"

    if ($recent -match "Installer complete\. Success:1" -and
        (Get-Item -LiteralPath $logPath).Length -gt $startLength) {
        Write-Output "VERIFY_COMPLETE"
        exit 0
    }

    if ($recent -match "EBuildPatchInstallError" -and
        $recent -notmatch "Constructing file") {
        Write-Output "VERIFY_ERROR"
        exit 2
    }

    $lastProgress = $log |
        Where-Object { $_ -match "Install|Verif|Constructing file|Completing:" } |
        Select-Object -Last 1
    if ($lastProgress) {
        Write-Output $lastProgress
    }
}

Write-Output "VERIFY_TIMEOUT"
exit 3
