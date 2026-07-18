param(
    [Parameter(Mandatory = $true)]
    [string]$DllPath
)

$dumpbin = "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Tools\MSVC\14.44.35207\bin\Hostx64\x64\dumpbin.exe"
$dependencies = & $dumpbin /dependents $DllPath |
    ForEach-Object { $_.Trim() } |
    Where-Object { $_ -match '^[A-Za-z0-9_.-]+\.dll$' }

$engineDlls = Get-ChildItem -LiteralPath "E:\UE_5.8\Engine" -Filter "*.dll" -Recurse -ErrorAction SilentlyContinue |
    Group-Object -Property Name -AsHashTable -AsString

Write-Output "DEPENDENCY_COUNT $($dependencies.Count)"

foreach ($dependency in $dependencies) {
    if ($dependency -match '^(KERNEL32|ADVAPI32|SHELL32|MSVCP140|VCRUNTIME140|VCRUNTIME140_1|api-ms-win-crt-)') {
        continue
    }
    if (-not $engineDlls.ContainsKey($dependency)) {
        Write-Output "MISSING $dependency"
    }
    elseif (-not (Test-Path -LiteralPath (Join-Path "E:\UE_5.8\Engine\Binaries\Win64" $dependency))) {
        $source = $engineDlls[$dependency] | Select-Object -First 1 -ExpandProperty FullName
        Write-Output "NOT_IN_OUTPUT $dependency <- $source"
    }
}
