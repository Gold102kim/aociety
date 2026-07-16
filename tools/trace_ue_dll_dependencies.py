import os
import re
import subprocess
import sys
from collections import deque
from pathlib import Path


ENGINE = Path(r"E:\UE_5.8\Engine")
DUMPBIN = Path(
    r"C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Tools\MSVC\14.44.35207\bin\Hostx64\x64\dumpbin.exe"
)
SYSTEM_PREFIXES = (
    "kernel32.dll",
    "advapi32.dll",
    "shell32.dll",
    "user32.dll",
    "ole32.dll",
    "oleaut32.dll",
    "gdi32.dll",
    "comdlg32.dll",
    "winmm.dll",
    "ws2_32.dll",
    "msvcp140.dll",
    "vcruntime140.dll",
    "vcruntime140_1.dll",
    "api-ms-win-",
)


index = {}
for root, _, files in os.walk(ENGINE):
    for filename in files:
        if filename.lower().endswith(".dll"):
            index.setdefault(filename.lower(), []).append(Path(root) / filename)

queue = deque([Path(sys.argv[1])])
visited = set()
while queue:
    dll = queue.popleft()
    key = str(dll).lower()
    if key in visited:
        continue
    visited.add(key)
    output = subprocess.run(
        [str(DUMPBIN), "/dependents", str(dll)],
        capture_output=True,
        text=True,
        errors="ignore",
    ).stdout
    dependencies = re.findall(r"^\s+([A-Za-z0-9_.-]+\.dll)\s*$", output, re.M | re.I)
    for dependency in dependencies:
        lower = dependency.lower()
        if lower.startswith(SYSTEM_PREFIXES):
            continue
        matches = index.get(lower, [])
        if not matches:
            print(f"MISSING {dependency} required_by={dll}")
            continue
        queue.append(matches[0])

print(f"VISITED {len(visited)}")
