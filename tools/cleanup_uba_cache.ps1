$ErrorActionPreference = "SilentlyContinue"

$targets = @(
    "C:\ProgramData\Epic\UnrealBuildAccelerator\cas",
    "C:\Users\jingk\AppData\Local\Temp\UnrealBuildTool"
)

foreach ($target in $targets) {
    if (-not (Test-Path -LiteralPath $target)) {
        continue
    }

    $resolved = (Resolve-Path -LiteralPath $target).Path
    if ($resolved -ne $target) {
        throw "Refusing unexpected cleanup target: $resolved"
    }

    Get-ChildItem -LiteralPath $resolved -Force |
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
}

Get-PSDrive -Name C |
    Select-Object Name,
        @{Name = "FreeGB"; Expression = {[math]::Round($_.Free / 1GB, 2)}},
        @{Name = "UsedGB"; Expression = {[math]::Round($_.Used / 1GB, 2)}}
