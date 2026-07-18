Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class NativeDllTest {
    [DllImport("kernel32", SetLastError = true, CharSet = CharSet.Unicode)]
    public static extern IntPtr LoadLibrary(string path);
    [DllImport("kernel32", SetLastError = true)]
    public static extern bool FreeLibrary(IntPtr handle);
}
"@

$dlls = @(
    "E:\UE_5.8\Engine\Binaries\Win64\libfbxsdk.dll",
    "E:\UE_5.8\Engine\Binaries\Win64\metalirconverter.dll",
    "E:\UE_5.8\Engine\Binaries\Win64\UnrealEditor-UnrealEd.dll"
)

foreach ($dll in $dlls) {
    try {
        $handle = [NativeDllTest]::LoadLibrary($dll)
        if ($handle -eq [IntPtr]::Zero) {
            $code = [Runtime.InteropServices.Marshal]::GetLastWin32Error()
            throw "LoadLibrary failed with Win32 error $code"
        }
        Write-Output "OK $dll"
        [NativeDllTest]::FreeLibrary($handle) | Out-Null
    }
    catch {
        Write-Output "FAIL $dll"
        Write-Output $_.Exception.Message
    }
}
