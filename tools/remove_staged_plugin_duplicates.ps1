$pluginRoot = "E:\UE_5.8\Engine\Plugins"
$outputRoot = "E:\UE_5.8\Engine\Binaries\Win64"
Write-Output "cleanup-start"

$resolvedOutput = (Resolve-Path -LiteralPath $outputRoot).Path
if ($resolvedOutput -ne $outputRoot) {
    throw "Unexpected output directory: $resolvedOutput"
}

$names = Get-ChildItem -LiteralPath $pluginRoot -Filter "*.dll" -Recurse -ErrorAction SilentlyContinue |
    Where-Object { $_.DirectoryName -like "*\Binaries\Win64" } |
    Select-Object -ExpandProperty Name -Unique
Write-Output "plugin-dll-names: $($names.Count)"
Write-Output "first-name: $($names[0])"
Write-Output "first-target-exists: $(Test-Path -LiteralPath (Join-Path $outputRoot $names[0]))"
Write-Output "contains-water: $($names -contains 'UnrealEditor-Water.dll')"

$removed = 0
foreach ($name in $names) {
    $target = Join-Path $outputRoot $name
    if (Test-Path -LiteralPath $target) {
        $resolvedTarget = (Resolve-Path -LiteralPath $target).Path
        if (-not $resolvedTarget.StartsWith($resolvedOutput + "\", [StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing unexpected target: $resolvedTarget"
        }
        Remove-Item -LiteralPath $resolvedTarget -Force
        $removed++
    }
}

Write-Output "Removed duplicate plugin DLLs: $removed"
