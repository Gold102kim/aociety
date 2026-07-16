from __future__ import annotations

from collections import defaultdict
from threading import Lock
import time
import uuid
from typing import Any

from .ark_client import ArkClient


RESIDENTS: dict[str, dict[str, str]] = {
    "npc_01": {
        "id": "npc_01",
        "name": "林汐",
        "personality": "安静温和，观察细致，说话不急，喜欢读书和傍晚散步。",
        "daily_life": "住在森林小镇，平时整理住处、阅读，也会关心邻居近况。",
    },
    "npc_02": {
        "id": "npc_02",
        "name": "小樱",
        "personality": "亲切活泼，有一点好奇心，表达轻快，但不会过度卖萌。",
        "daily_life": "住在森林小镇，喜欢料理、照顾花草，并常在小路附近散步。",
    },
}


class ForestResidentService:
    def __init__(self, ark: ArkClient) -> None:
        self.ark = ark
        self._history: dict[str, list[dict[str, str]]] = defaultdict(list)
        self._lock = Lock()

    def chat(
        self,
        *,
        npc_id: str,
        live_event: str,
        mode: str = "player",
        counterpart_id: str = "",
        scene: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        resident = RESIDENTS.get(npc_id)
        if not resident:
            return {
                "npc_id": npc_id,
                "message": "这名居民暂时不在小镇中。",
                "source": "error",
                "model": "",
            }

        counterpart = RESIDENTS.get(counterpart_id, {})
        with self._lock:
            recent = list(self._history[npc_id][-6:])

        request_id = uuid.uuid4().hex[:12]
        generated = self.ark.generate_forest_resident_reply(
            {
                "resident": resident,
                "mode": "ambient_resident_chat" if mode == "ambient" else "player_interaction",
                "live_event": live_event,
                "counterpart": counterpart,
                "scene": {
                    "location": "森林小镇的住宅与林间小路",
                    "time": "白天",
                    "weather": "清朗，偶尔会有轻微天气变化",
                    **(scene or {}),
                },
                "recent_dialogue": recent,
                "request_nonce": f"{request_id}-{time.time_ns()}",
            }
        )
        if not generated:
            return {
                "npc_id": npc_id,
                "message": "我刚才走神了一下，等我重新想想。",
                "mood": "短暂走神",
                "source": "error",
                "model": getattr(self.ark, "model_id", "glm-5.2"),
                "request_id": request_id,
            }

        reply = str(generated.get("reply", "")).strip()
        mood = str(generated.get("mood", "平静")).strip() or "平静"
        model = str(generated.get("_meta_model", self.ark.model_id))
        with self._lock:
            self._history[npc_id].append(
                {
                    "event": live_event,
                    "reply": reply,
                    "mood": mood,
                    "counterpart": str(counterpart.get("name", "玩家")),
                }
            )
            self._history[npc_id] = self._history[npc_id][-12:]

        dialogue = {
            "npc_id": npc_id,
            "message": reply,
            "mood": mood,
            "source": "llm",
            "model": model,
            "request_id": request_id,
        }
        return {**dialogue, "dialogue": dialogue}
