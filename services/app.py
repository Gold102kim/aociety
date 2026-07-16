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

from .engine import WorldEngine


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
        if key in {
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY",
            "GLM_API_KEY",
            "GLM_BASE_URL",
            "GLM_MODEL_ID",
            "GLM_OMNI_MODEL",
        }:
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


class AIPulseRequest(BaseModel):
    trigger: str = "manual"
    current_district: str = ""
    player_position: dict[str, float] = Field(default_factory=dict)
    screenshot_b64: str = ""
    scene_context: dict[str, Any] = Field(default_factory=dict)


PULSE_INTERVAL_SECONDS = int(os.getenv("SHELL_MARKET_PULSE_SECONDS", "60"))
engine = WorldEngine(pulse_interval_seconds=PULSE_INTERVAL_SECONDS)


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


app = FastAPI(title="Shell And Market Service", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "pulse_interval_seconds": engine.pulse_interval_seconds,
        "glm_enabled": engine.ark.enabled,
        "glm_model": getattr(engine.ark, 'model_id', 'glm-5.2'),
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
