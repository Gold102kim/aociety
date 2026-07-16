from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "story_overrides.generated.json"


def _load_story_overrides() -> dict[str, dict[str, Any]]:
    if not DATA_PATH.exists():
        return {}
    raw = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    return raw if isinstance(raw, dict) else {}


NPC_STORY_OVERRIDES: dict[str, dict[str, Any]] = _load_story_overrides()
