from __future__ import annotations

from collections import OrderedDict
import re
from threading import Lock
import time
import uuid
from typing import Any

from .ark_client import (
    ArkClient,
    DEEPSEEK_MODEL_ID,
    DEEPSEEK_PROVIDER,
    FOREST_LEGACY_TERMS,
)


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

SAFE_SCENE_KEYS = {
    "location",
    "time",
    "weather",
    "interaction",
    "player_position",
    "npc_position",
    "nearby_landmark",
    "activity",
    "event_timestamp",
}

MAX_CONVERSATION_SCOPES = 128
MAX_HISTORY_TURNS = 12
MAX_HISTORY_TEXT_CHARS = 2000
_CONVERSATION_SCOPE_PATTERN = re.compile(r"[a-fA-F0-9]{32}")


class ForestResidentService:
    def __init__(self, ark: ArkClient) -> None:
        self.ark = ark
        # An ephemeral game launch scope separates model context. This is not
        # authentication; knowing a scope grants no account or filesystem rights.
        # Legacy unscoped NPC history is intentionally not imported.
        self._history: OrderedDict[str, dict[str, list[dict[str, str]]]] = OrderedDict()
        self._lock = Lock()

    def chat(
        self,
        *,
        npc_id: str,
        live_event: str,
        mode: str = "player",
        counterpart_id: str = "",
        scene: dict[str, Any] | None = None,
        conversation_scope: str = "",
    ) -> dict[str, Any]:
        resident = RESIDENTS.get(npc_id)
        if not resident:
            dialogue = {
                "npc_id": npc_id,
                "message": "这名居民暂时不在小镇中。",
                "mood": "请求失败",
                "source": "error",
                "model": DEEPSEEK_MODEL_ID,
                "provider": DEEPSEEK_PROVIDER,
                "error_code": "resident_not_found",
                "mode": "player",
                "counterpart_id": "",
            }
            return {**dialogue, "dialogue": dialogue}

        normalized_mode = "ambient" if mode == "ambient" else "player"
        valid_counterpart_id = (
            counterpart_id
            if normalized_mode == "ambient"
            and counterpart_id != npc_id
            and counterpart_id in RESIDENTS
            else ""
        )
        counterpart = RESIDENTS.get(valid_counterpart_id, {})
        safe_scene = self._sanitize_scene(scene)
        scope = self._normalize_scope(conversation_scope)
        scoped_history: dict[str, list[dict[str, str]]] | None = None
        recent: list[dict[str, str]] = []
        counterpart_recent: list[dict[str, str]] = []
        with self._lock:
            if scope:
                scoped_history = self._history.get(scope)
                if scoped_history is None:
                    scoped_history = {}
                    self._history[scope] = scoped_history
                    while len(self._history) > MAX_CONVERSATION_SCOPES:
                        self._history.popitem(last=False)
                else:
                    self._history.move_to_end(scope)
                recent = list(scoped_history.get(npc_id, [])[-8:])
                if counterpart:
                    counterpart_recent = list(scoped_history.get(valid_counterpart_id, [])[-4:])

        request_id = uuid.uuid4().hex[:12]
        generated = self.ark.generate_forest_resident_reply(
            {
                "resident": resident,
                "mode": (
                    "ambient_resident_chat"
                    if normalized_mode == "ambient"
                    else "player_interaction"
                ),
                "live_event": live_event,
                "counterpart": counterpart,
                "scene": {
                    "location": "森林小镇的住宅与林间小路",
                    "time": "白天",
                    "weather": "清朗，偶尔会有轻微天气变化",
                    **safe_scene,
                },
                "recent_dialogue": recent,
                "counterpart_recent_dialogue": counterpart_recent,
                "request_nonce": f"{request_id}-{time.time_ns()}",
            }
        )
        if not self._is_verified_llm_result(generated):
            dialogue = {
                "npc_id": npc_id,
                "message": "DeepSeek V4 Flash 实时思考请求失败，请检查 API 权限、额度或网络。",
                "mood": "请求失败",
                "source": "error",
                "model": getattr(self.ark, "model_id", DEEPSEEK_MODEL_ID),
                "provider": DEEPSEEK_PROVIDER,
                "error_code": "llm_unavailable",
                "request_id": request_id,
                "mode": normalized_mode,
                "counterpart_id": valid_counterpart_id,
            }
            return {**dialogue, "dialogue": dialogue}

        reply = str(generated.get("reply", "")).strip()
        mood = str(generated.get("mood", "平静")).strip() or "平静"
        model = str(generated.get("_meta_model", self.ark.model_id))
        with self._lock:
            # An evicted scope may still have an in-flight model call. Never
            # recreate it or append its reply to a newly created bucket.
            if scope and self._history.get(scope) is scoped_history:
                assert scoped_history is not None
                history = scoped_history.setdefault(npc_id, [])
                history.append(
                    {
                        "kind": "spoken_turn",
                        "event": live_event[:MAX_HISTORY_TEXT_CHARS],
                        "reply": reply[:MAX_HISTORY_TEXT_CHARS],
                        "mood": mood[:80],
                        "counterpart": str(counterpart.get("name", "玩家")),
                    }
                )
                scoped_history[npc_id] = history[-MAX_HISTORY_TURNS:]
                if counterpart:
                    heard = scoped_history.setdefault(valid_counterpart_id, [])
                    heard.append(
                        {
                            "kind": "heard_turn",
                            "speaker": str(resident.get("name", npc_id)),
                            "event": live_event[:MAX_HISTORY_TEXT_CHARS],
                            "heard_reply": reply[:MAX_HISTORY_TEXT_CHARS],
                            "mood": mood[:80],
                        }
                    )
                    scoped_history[valid_counterpart_id] = heard[-MAX_HISTORY_TURNS:]
                self._history.move_to_end(scope)

        dialogue = {
            "npc_id": npc_id,
            "message": reply,
            "mood": mood,
            "source": "llm",
            "model": model or DEEPSEEK_MODEL_ID,
            "provider": str(
                generated.get("_meta_provider", DEEPSEEK_PROVIDER)
            ),
            "request_id": request_id,
            "mode": normalized_mode,
            "counterpart_id": valid_counterpart_id,
        }
        return {**dialogue, "dialogue": dialogue}

    @staticmethod
    def _normalize_scope(scope: str) -> str:
        # Invalid/old clients remain stateless, never joined to a shared inbox.
        if not isinstance(scope, str) or not _CONVERSATION_SCOPE_PATTERN.fullmatch(scope):
            return ""
        return scope.lower()

    @staticmethod
    def _is_verified_llm_result(generated: dict[str, Any] | None) -> bool:
        if not generated:
            return False
        reply = str(generated.get("reply", "")).strip()
        if not reply or any(term in reply for term in FOREST_LEGACY_TERMS):
            return False
        return (
            generated.get("_meta_source") == "llm"
            and generated.get("_meta_provider") == DEEPSEEK_PROVIDER
            and generated.get("_meta_model") == DEEPSEEK_MODEL_ID
        )

    @staticmethod
    def _sanitize_scene(scene: dict[str, Any] | None) -> dict[str, Any]:
        if not isinstance(scene, dict):
            return {}
        sanitized: dict[str, Any] = {}
        for key, value in scene.items():
            if key not in SAFE_SCENE_KEYS:
                continue
            if key == "location":
                sanitized[key] = "森林小镇的住宅与林间小路"
            elif key in {"player_position", "npc_position"} and isinstance(
                value, dict
            ):
                sanitized[key] = {
                    axis: number
                    for axis, number in value.items()
                    if axis in {"x", "y", "z"}
                    and isinstance(number, (int, float))
                }
            elif key == "event_timestamp" and isinstance(value, (int, float)):
                sanitized[key] = value
            elif isinstance(value, str):
                clipped = value.strip()[:160]
                if clipped and not any(term in clipped for term in FOREST_LEGACY_TERMS):
                    sanitized[key] = clipped
        return sanitized
