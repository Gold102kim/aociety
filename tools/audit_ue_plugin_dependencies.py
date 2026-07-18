from pathlib import Path
import re


root = Path(r"E:\UE_5.8\Engine\Plugins")
for descriptor in root.rglob("*.uplugin"):
    text = descriptor.read_text(encoding="utf-8-sig", errors="ignore")
    if not re.search(r'"Name"\s*:\s*"(?:Interchange|GeometryScripting)"', text):
        continue
    enabled = re.search(r'"EnabledByDefault"\s*:\s*(true|false)', text, re.I)
    print(enabled.group(1) if enabled else "unspecified", descriptor)
