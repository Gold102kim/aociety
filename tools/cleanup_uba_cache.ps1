[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'High')]
param([switch]$IncludeSharedCache)

$ErrorActionPreference = 'Stop'
$taskTempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd([IO.Path]::DirectorySeparatorChar)
$taskTempTarget = [IO.Path]::GetFullPath((Join-Path $taskTempRoot 'UnrealBuildTool'))
if (-not $taskTempTarget.StartsWith($taskTempRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Cache target must remain in the current user temporary directory.'
}
$targets = @($taskTempTarget)
if ($IncludeSharedCache) {
    $sharedRoot = [Environment]::GetFolderPath([Environment+SpecialFolder]::CommonApplicationData)
    if (-not $sharedRoot) { throw 'Shared cache root is unavailable.' }
    $targets += [IO.Path]::GetFullPath((Join-Path $sharedRoot 'Epic\UnrealBuildAccelerator\cas'))
}
if (Get-Process -Name UnrealEditor, UnrealBuildTool, UbaAgent -ErrorAction SilentlyContinue) {
    throw 'Close Unreal Editor and active build jobs before cleaning their caches.'
}

foreach ($target in $targets) {
    if (-not (Test-Path -LiteralPath $target)) {
        continue
    }

    $resolved = (Resolve-Path -LiteralPath $target).ProviderPath
    if ($resolved -ne $target) {
        throw "Refusing unexpected cleanup target: $resolved"
    }

    if ((Get-Item -LiteralPath $resolved -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw 'Refusing a linked cache directory.'
    }
    foreach ($item in Get-ChildItem -LiteralPath $resolved -Force) {
        $itemPath = [IO.Path]::GetFullPath($item.FullName)
        if (-not $itemPath.StartsWith($resolved.TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
            throw 'Cache item escaped the validated target.'
        }
        $links = @($item | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint })
        if ($item.PSIsContainer) {
            $links += @(Get-ChildItem -LiteralPath $itemPath -Recurse -Force | Where-Object { $_.Attributes -band [IO.FileAttributes]::ReparsePoint })
        }
        if ($links.Count) { Write-Warning 'Skipping a cache item containing a junction or symbolic link.'; continue }
        if ($PSCmdlet.ShouldProcess($itemPath, 'Remove regenerable Unreal cache item')) {
            Remove-Item -LiteralPath $itemPath -Recurse -Force
        }
    }
}
