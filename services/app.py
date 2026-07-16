from __future__ import annotations

import asyncio
import contextlib
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

from .ark_client import ArkClient
from .engine import WorldEngine
from .forest_residents import RESIDENTS, ForestResidentService


def load_dotenv_file() -> None:
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        # Keep the game backend deterministic: stale user/session credentials
        # must not override the project-local GLM endpoint and model settings.
        if key in {"TOKENHUB_API_KEY", "TOKENHUB_BASE_URL", "TOKENHUB_MODEL"}:
            os.environ[key] = value
        else:
            os.environ.setdefault(key, value)


load_dotenv_file()


class WorldActionRequest(BaseModel):
    action_type: str
    district: str
    payload: dict[str, Any] = Field(default_factory=dict)


class ConversationRequest(BaseModel):
    speaker_id: str
    listener_id: str
    trigger: str = "街头搭话"
    current_district: str = ""
    player_position: dict[str, float] = Field(default_factory=dict)
    screenshot_b64: str = ""
    scene_context: dict[str, Any] = Field(default_factory=dict)


class HearingRequest(BaseModel):
    speaker_id: str
    listener_id: str
    line: str


class PlayerTalkRequest(BaseModel):
    npc_id: str
    district: str = ""
    topic_id: str = ""
    approach: str = "cautious"
    intent: str = ""
    player_input: str = ""
    player_position: dict[str, float] = Field(default_factory=dict)
    screenshot_b64: str = ""
    scene_context: dict[str, Any] = Field(default_factory=dict)


class ForestResidentRequest(BaseModel):
    npc_id: str
    player_input: str = ""
    mode: str = "player"
    counterpart_id: str = ""
    scene_context: dict[str, Any] = Field(default_factory=dict)


class AIPulseRequest(BaseModel):
    trigger: str = "manual"
    current_district: str = ""
    player_position: dict[str, float] = Field(default_factory=dict)
    screenshot_b64: str = ""
    scene_context: dict[str, Any] = Field(default_factory=dict)


PULSE_INTERVAL_SECONDS = int(os.getenv("SHELL_MARKET_PULSE_SECONDS", "60"))
engine = WorldEngine(pulse_interval_seconds=PULSE_INTERVAL_SECONDS)
# The forest demo has its own client/cooldown. Legacy simulation requests must
# not block or inject state into real-time resident dialogue.
forest_ark = ArkClient()
forest_residents = ForestResidentService(forest_ark)


async def pulse_loop() -> None:
    while True:
        await asyncio.sleep(engine.pulse_interval_seconds)
        with contextlib.suppress(Exception):
            if engine._route_choice_required():
                engine.state["last_tick_at"] = time.time()
                continue
            await asyncio.to_thread(engine.ai_pulse, trigger="scheduled", allow_live_llm=False)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    engine.reset()
    task = asyncio.create_task(pulse_loop())
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


app = FastAPI(title="Aociety Forest Town Service", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "pulse_interval_seconds": engine.pulse_interval_seconds,
        "glm_enabled": forest_ark.enabled,
        "glm_configured": forest_ark.configured,
        "glm_model": getattr(forest_ark, "model_id", "glm-5.2"),
        "glm_provider": getattr(forest_ark, "provider", "tokenhub"),
        "glm_base_url": getattr(
            forest_ark, "base_url", "https://api.tokenhub.market/v1/"
        ).rstrip("/"),
    }


@app.get("/world/state")
def world_state() -> dict[str, Any]:
    return {"world_state": engine.snapshot_cached(), "message": ""}


@app.post("/world/action")
def world_action(payload: WorldActionRequest) -> dict[str, Any]:
    result = engine.action(payload.action_type, payload.district, payload.payload)
    return {"message": result.message, "world_state": result.world_state}


@app.post("/world/end_day")
def world_end_day(_payload: WorldActionRequest) -> dict[str, Any]:
    result = engine.end_day()
    return {"message": result.message, "world_state": result.world_state}


@app.post("/ai/pulse")
def ai_pulse(payload: AIPulseRequest) -> dict[str, Any]:
    trigger = str(payload.trigger or "manual")
    allow_live_llm = trigger not in {"scheduled", "scheduled_scene"}
    if engine._route_choice_required():
        engine.state["last_tick_at"] = time.time()
        return {"message": "先选路线。", "world_state": engine.snapshot_cached()}
    result = engine.ai_pulse(
        trigger=trigger,
        allow_live_llm=allow_live_llm,
        scene_observation={
            "current_district": payload.current_district,
            "player_position": payload.player_position,
            "screenshot_b64": payload.screenshot_b64,
            "scene_context": payload.scene_context,
        },
    )
    return {"message": result.message, "world_state": result.world_state}


@app.post("/world/reset")
def world_reset() -> dict[str, Any]:
    result = engine.reset_world()
    return {"message": result.message, "world_state": result.world_state}


@app.post("/ai/probe")
def ai_probe() -> dict[str, Any]:
    result = engine.probe_ai()
    return {"message": result.message, "world_state": result.world_state}


@app.post("/npc/conversation")
def npc_conversation(payload: ConversationRequest) -> dict[str, Any]:
    if payload.speaker_id in RESIDENTS:
        return forest_residents.chat(
            npc_id=payload.speaker_id,
            live_event=payload.trigger.strip()
            or "你在林间小路遇到了另一名居民，请自然回应此刻的相遇。",
            mode="ambient",
            counterpart_id=payload.listener_id,
            scene={
                "current_district": payload.current_district,
                "player_position": payload.player_position,
                **payload.scene_context,
            },
        )
    result = engine.conversation(
        payload.speaker_id,
        payload.listener_id,
        payload.trigger,
        scene_observation={
            "current_district": payload.current_district,
            "player_position": payload.player_position,
            "screenshot_b64": payload.screenshot_b64,
            "scene_context": payload.scene_context,
        },
        # Explicit in-game resident encounters use GLM. Background scheduled
        # simulation remains rate-limited by the engine's pulse/budget rules.
        allow_llm=True,
    )
    return {"message": result.message, "world_state": result.world_state}


@app.post("/forest/probe")
def forest_probe() -> dict[str, Any]:
    result = forest_ark.probe()
    return {
        **result,
        "provider": "tokenhub",
        "base_url": forest_ark.base_url.rstrip("/"),
    }


@app.get("/npc/list")
def npc_list() -> dict[str, Any]:
    snapshot = engine.snapshot_cached()
    return {"npcs": snapshot.get("npcs", [])}


@app.post("/npc/hearing_event")
def npc_hearing(payload: HearingRequest) -> dict[str, Any]:
    result = engine.hearing_event(payload.speaker_id, payload.listener_id, payload.line)
    return {"message": result.message, "world_state": result.world_state}


@app.post("/npc/player_talk")
def npc_player_talk(payload: PlayerTalkRequest) -> dict[str, Any]:
    if payload.npc_id in RESIDENTS:
        live_event = payload.player_input.strip() or payload.intent.strip()
        if not live_event:
            live_event = "玩家刚刚走近并主动与你交互，请根据此刻的场景自然开口。"
        return forest_residents.chat(
            npc_id=payload.npc_id,
            live_event=live_event,
            mode="player",
            scene={
                "current_district": payload.district,
                "player_position": payload.player_position,
                **payload.scene_context,
            },
        )
    result = engine.player_talk(
        payload.npc_id,
        payload.district,
        payload.topic_id,
        payload.approach,
        payload.intent,
        payload.player_input,
        scene_observation={
            "current_district": payload.district,
            "player_position": payload.player_position,
            "screenshot_b64": payload.screenshot_b64,
            "scene_context": payload.scene_context,
        },
    )
    return {
        "message": result.message,
        "world_state": result.world_state,
        "dialogue": result.world_state.get("last_dialogue", {}),
    }


@app.post("/forest/resident_chat")
def forest_resident_chat(payload: ForestResidentRequest) -> dict[str, Any]:
    mode = "ambient" if payload.mode == "ambient" else "player"
    live_event = payload.player_input.strip()
    if not live_event:
        live_event = (
            "你在小镇散步时遇到了另一名居民，请根据当下心情自然说一句话。"
            if mode == "ambient"
            else "玩家刚刚走近并主动与你交互，请实时判断后自然开口。"
        )
    return forest_residents.chat(
        npc_id=payload.npc_id,
        live_event=live_event,
        mode=mode,
        counterpart_id=payload.counterpart_id,
        scene=payload.scene_context,
    )
