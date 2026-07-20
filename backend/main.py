"""Aociety 统一后端 — 融合情感计算引擎与游戏世界服务

架构：
  UE5 ←→ REST API + WebSocket ←→ Python Backend ←→ GLM 5.2 API (云端)
                                                     ←→ 本地模型 (R1-Omni, Arousal, FER+)

端口: 8010 (硬件情感API), 8001 (R1-Omni), 8002 (Arousal)
"""

from __future__ import annotations

import base64
import json
import os
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional

# ── 加载 .env 文件 ──
def _load_dotenv() -> None:
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        # The project-local GLM credential must win over stale user/session keys.
        os.environ[key.strip()] = value.strip()
_load_dotenv()

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ── 情感计算模块 ──
from backend.affect_runtime import AffectRuntime
from backend.glm_adapter import GlmEmotionAdapter, DuplexAffectTap
from backend.assessment_engine import (
    build_initial_session, select_next_question, score_answer_heuristic,
    should_finish, build_final_profile, merge_scoring,
    extract_turn_analysis_from_model, compute_dimension_confidence,
    build_memory_summary, derive_type_code,
)
from backend.openclaw_gateway import OpenClawGatewayConfig, OpenClawGatewayClient

# Simple in-memory memory store for now (OpenClaw requires runtime)
class SimpleMemoryStore:
    """In-memory key-value store with search, replacing OpenClaw dependency."""
    def __init__(self):
        self._store: dict[str, dict] = {}

    def search(self, query: str = "", limit: int = 10) -> list:
        results = []
        for key, entry in self._store.items():
            if query.lower() in key.lower() or query.lower() in str(entry.get("value", "")).lower():
                results.append({"key": key, **entry})
        return results[:limit]

    def store(self, key: str = "", value: str = "", tags: list[str] | None = None) -> None:
        self._store[key] = {"value": value, "tags": tags or [], "timestamp": time.time()}

openclaw = SimpleMemoryStore()

# ── 游戏世界模块 ──
from services.engine import WorldEngine
from services.ark_client import ArkClient as WorldGlmClient
from services.tts_service import TTSService, SWEET_VOICES

# ────────────────────────────────────────────────────────────────
# 配置
# ────────────────────────────────────────────────────────────────

DATA_DIR = Path(__file__).resolve().parent / "game" / "data"
PULSE_INTERVAL_SECONDS = int(os.environ.get("WORLD_PULSE_SECONDS", "60"))
ENABLE_EMOTION = os.environ.get("ENABLE_EMOTION", "1").strip() in {"1", "true", "yes"}

# ────────────────────────────────────────────────────────────────
# 全局实例
# ────────────────────────────────────────────────────────────────

world_engine = WorldEngine(pulse_interval_seconds=PULSE_INTERVAL_SECONDS)
affect_runtime = AffectRuntime(window_ms=10_000)
glm_emotion = GlmEmotionAdapter(timeout_sec=10.0)
duplex_tap = DuplexAffectTap(window_ms=10_000)
# assessment_engine uses functional API — import the functions directly above
openclaw = SimpleMemoryStore()
npc_glm = WorldGlmClient()

# TTS 甜女声服务
tts_service = TTSService(voice_name=os.environ.get("TTS_VOICE", "xiaoxiao"))

# WebSocket 连接池
active_websockets: dict[str, WebSocket] = {}


# ────────────────────────────────────────────────────────────────
# 生命周期
# ────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(_app: FastAPI):
    world_engine.reset()
    yield


# ────────────────────────────────────────────────────────────────
# FastAPI 应用
# ────────────────────────────────────────────────────────────────

app = FastAPI(title="Aociety Unified Backend", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ════════════════════════════════════════════════════════════════
# 数据模型
# ════════════════════════════════════════════════════════════════


class EmotionFrameIn(BaseModel):
    """情感帧输入 — UE5 从摄像头/麦克风采集后发送"""
    image_base64: str = ""
    audio_base64: str = ""
    text_hint: str = ""
    timestamp_ms: int = Field(default_factory=lambda: int(time.time() * 1000))


class EmotionOut(BaseModel):
    """情感分析输出"""
    emotion: str = "unknown"
    valence: float = 0.5
    arousal: float = 0.0
    support_need: float = 0.0
    trend: dict[str, Any] = Field(default_factory=dict)
    confidence_gap: float = 0.0
    top_candidates: list[dict[str, Any]] = Field(default_factory=list)
    degraded: bool = True
    source_models: dict[str, Any] = Field(default_factory=dict)


class CareRequest(BaseModel):
    """主动关怀请求"""
    npc_id: str = ""
    scene_context: dict[str, Any] = Field(default_factory=dict)


class CareResponse(BaseModel):
    """关怀响应"""
    npc_line: str = ""
    action: str = ""
    care_level: str = "nudge"
    duration_seconds: float = 5.0
    # Optional voice payload used by the UE client.  Keep these fields on the
    # schema so the GLM/rule fallback can be enriched with synthesized audio
    # without relying on pydantic's runtime extra-attribute behavior.
    audio_base64: str = ""
    audio_format: str = "mp3"
    voice: str = ""
    voice_name_cn: str = ""


class AIPulseRequest(BaseModel):
    """游戏世界自治脉冲；只负责 NPC 思考和世界演化。"""
    trigger: str = "manual"
    current_district: str = ""
    player_position: dict[str, float] = Field(default_factory=dict)
    screenshot_b64: str = ""
    scene_context: dict[str, Any] = Field(default_factory=dict)


class PlayerTalkRequest(BaseModel):
    """玩家与游戏内 GLM Agent 的一轮对话。"""
    npc_id: str
    district: str = ""
    topic_id: str = ""
    approach: str = "cautious"
    intent: str = ""
    player_input: str = ""
    player_position: dict[str, float] = Field(default_factory=dict)
    screenshot_b64: str = ""
    scene_context: dict[str, Any] = Field(default_factory=dict)
    audio_base64: str = ""
    audio_format: str = ""
    voice: str = ""
    voice_name_cn: str = ""


# ════════════════════════════════════════════════════════════════
# 端点: 健康检查
# ════════════════════════════════════════════════════════════════


@app.get("/health")
def health():
    return {
        "status": "ok",
        "version": "1.0.0",
        "emotion_enabled": ENABLE_EMOTION,
        "glm_enabled": glm_emotion.enabled,
        "world_glm_enabled": npc_glm.enabled,
    }


# ════════════════════════════════════════════════════════════════
# 端点: 情感计算 (UE5 → 后端)
# ════════════════════════════════════════════════════════════════


@app.post("/emotion/analyze", response_model=EmotionOut)
def analyze_emotion(frame: EmotionFrameIn):
    """分析单帧情感状态 (UE5 发送摄像头/麦克风数据)

    支持多模态输入:
      - image_base64 → 本地MediaPipe人脸检测 + FER+表情分析
      - audio_base64 → 本地VAD + 声学特征提取
      - text_hint → GLM 5.2 云端情感推理
    """
    if not ENABLE_EMOTION:
        return EmotionOut(degraded=True, status="disabled")

    ts = frame.timestamp_ms or int(time.time() * 1000)

    # ── 1. 视觉处理 (本地) ──
    local_expr_label = "neutral"
    local_expr_conf = 0.5
    face_present = False

    if frame.image_base64:
        try:
            import cv2
            import numpy as np
            import mediapipe as mp

            # 解码JPEG
            jpeg_bytes = base64.b64decode(frame.image_base64)
            nparr = np.frombuffer(jpeg_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

            # MediaPipe人脸检测
            with mp.solutions.face_mesh.FaceMesh(
                max_num_faces=1, refine_landmarks=True,
                min_detection_confidence=0.5,
            ) as face_mesh:
                results = face_mesh.process(rgb)
                face_present = results is not None and results.multi_face_landmarks is not None

            # FER+表情分类
            if face_present:
                model_path = Path(__file__).resolve().parent.parent / "models" / "ferplus" / "emotion-ferplus-8.onnx"
                if model_path.exists():
                    try:
                        import onnxruntime as ort
                        session = ort.InferenceSession(str(model_path))
                        input_name = session.get_inputs()[0].name

                        face_cascade = cv2.CascadeClassifier(
                            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
                        )
                        faces = face_cascade.detectMultiScale(gray, 1.1, 5)
                        for (fx, fy, fw, fh) in faces:
                            roi = gray[fy:fy + fh, fx:fx + fw]
                            resized = cv2.resize(roi, (64, 64))
                            normed = resized.astype(np.float32) / 255.0
                            input_tensor = normed[np.newaxis, np.newaxis, :, :]
                            outputs = session.run(None, {input_name: input_tensor})
                            probs = outputs[0][0]
                            idx = int(np.argmax(probs))
                            local_expr_conf = float(probs[idx])
                            labels = ["neutral", "happiness", "surprise", "sadness",
                                      "anger", "disgust", "fear", "contempt"]
                            if idx < len(labels):
                                local_expr_label = labels[idx]
                            break
                    except Exception:
                        pass

            duplex_tap.push_frame(frame.image_base64)
        except Exception:
            pass

    # ── 2. 音频处理 (本地ASR) ──
    audio_text = ""
    if frame.audio_base64 and not frame.text_hint:
        try:
            import numpy as np
            pcm_bytes = base64.b64decode(frame.audio_base64)
            audio_int16 = np.frombuffer(pcm_bytes, dtype=np.int16)
            rms = float(np.sqrt(np.mean(audio_int16.astype(np.float32) ** 2)))
            if rms > 100:
                # ASR转写 (如果有sherpa-onnx)
                try:
                    import sherpa_onnx
                    model_dir = Path(__file__).resolve().parent.parent / "models" / "asr" / "sherpa" / "sherpa-onnx-paraformer-zh-small-2024-03-09"
                    model_path = model_dir / "model.int8.onnx"
                    tokens_path = model_dir / "tokens.txt"
                    if model_path.exists() and tokens_path.exists():
                        recognizer = sherpa_onnx.OfflineRecognizer(
                            decoder=sherpa_onnx.OfflineParaformerDecoderConfig(),
                            model=sherpa_onnx.OfflineModelConfig(
                                paraformer=sherpa_onnx.OfflineParaformerModelConfig(str(model_path)),
                                tokens=str(tokens_path), num_threads=2,
                            ),
                        )
                        stream = recognizer.create_stream()
                        stream.accept_waveform(16000, audio_int16.tolist())
                        recognizer.decode_stream(stream)
                        audio_text = stream.result.text.strip()
                except Exception:
                    pass
        except Exception:
            pass

    # ── 3. 文本拼接 + GLM 5.2 云端推理 ──
    combined_text = frame.text_hint or audio_text or ""

    glm_result = glm_emotion.analyze_emotion(
        text_hint=combined_text,
        image_base64=frame.image_base64,
    )

    if glm_result and isinstance(glm_result, dict) and glm_result.get("emotion", "unknown") != "unknown":
        # GLM 成功 → 使用云端结果
        emotion = glm_result.get("emotion", "neutral")
        valence = glm_result.get("valence", 0.5)
        arousal = glm_result.get("arousal", 0.0)
        confidence = glm_result.get("confidence", 0.5)
        top_candidates = glm_result.get("top_candidates", [{"label": emotion, "score": confidence}])

        packet = affect_runtime.update(
            timestamp_ms=ts,
            emotion=emotion,
            valence=valence,
            arousal=arousal,
            confidence_gap=confidence,
            top_candidates=top_candidates,
            source_models={"emotion": "glm-5.2", "va": "glm-5.2"},
            degraded=False,
        )
    else:
        # GLM 不可用 → 本地视觉/规则回退
        packet = affect_runtime.build_packet(
            timestamp_ms=ts,
            image_data_url=f"data:image/jpeg;base64,{frame.image_base64}" if frame.image_base64 else "",
            width=640, height=480,
            audio_features=[],
            audio_pcm16_base64=frame.audio_base64 or "",
            sample_rate=16_000,
            text_hint=combined_text,
            legacy_remote_result=None,
            local_expr_label=local_expr_label,
            local_expr_conf=local_expr_conf,
        )

    return EmotionOut(**packet)


@app.post("/emotion/care", response_model=CareResponse)
def get_npc_care(req: CareRequest):
    """获取 NPC 对当前玩家情绪的关怀回应"""
    affect = affect_runtime.latest_packet()

    # 从 NPC 配置中获取角色信息
    npc_profile = {}
    for npc in world_engine.state.get("npcs", []):
        if npc.get("id") == req.npc_id:
            npc_profile = npc
            break

    if npc_glm.enabled:
        result = npc_glm.generate_care_dialogue(
            npc_profile=npc_profile,
            player_emotion=affect,
        )
        if result:
            return CareResponse(**result)

    # Fallback: 基于规则的关怀
    return _rule_based_care(affect, npc_profile)


def _rule_based_care(affect: dict, npc_profile: dict) -> CareResponse:
    support = affect.get("support_need", 0.0)
    emotion = affect.get("emotion", "neutral")

    if support > 0.8:
        return CareResponse(
            npc_line="…你还好吗？要不要坐会儿？",
            action="offer_seat",
            care_level="guard",
            duration_seconds=12.0,
        )
    elif support > 0.6:
        return CareResponse(
            npc_line="看你脸色不太好，今天是不是太拼了？",
            action="speak_kindly",
            care_level="care",
            duration_seconds=8.0,
        )
    elif support > 0.4:
        return CareResponse(
            npc_line="来，刚烤的面包，趁热吃。",
            action="offer_food",
            care_level="nudge",
            duration_seconds=5.0,
        )
    return CareResponse(
        npc_line="",
        action="none",
        care_level="nudge",
    )


@app.get("/emotion/state")
def get_emotion_state():
    """获取当前情感状态摘要"""
    return affect_runtime.latest_packet()


@app.post("/emotion/reset")
def reset_emotion():
    """重置情感状态"""
    affect_runtime = AffectRuntime(window_ms=10_000)
    duplex_tap.reset()
    return {"status": "ok"}


# ════════════════════════════════════════════════════════════════
# 端点: TTS 文字转语音 (甜女声)
# ════════════════════════════════════════════════════════════════


class TTSRequest(BaseModel):
    text: str
    voice: str = "xiaoxiao"  # 默认晓晓甜女声


class TTSResponse(BaseModel):
    audio_base64: str = ""
    audio_format: str = "mp3"
    voice: str = "xiaoxiao"
    voice_name_cn: str = "晓晓"
    duration_estimate: float = 0.0
    text: str = ""


@app.get("/tts/voices")
def list_tts_voices():
    """列出可用甜女声"""
    return {"voices": tts_service.list_voices(), "current": tts_service.voice_name}


@app.post("/tts/voices/{voice_name}")
def set_tts_voice(voice_name: str):
    """切换甜女声"""
    if tts_service.set_voice(voice_name):
        return {"status": "ok", "current": tts_service.voice_name}
    return {"error": f"Unknown voice: {voice_name}", "available": list(tts_service.list_voices())}


@app.post("/tts/synthesize", response_model=TTSResponse)
def synthesize_speech(req: TTSRequest):
    """
    文字转语音 - 返回base64编码的音频

    推荐女声:
      - xiaoxiao  晓晓  甜+温暖+年轻  ★最推荐
      - xiaoyi    晓伊  温暖+自然
      - xiaomeng  晓梦  可爱+清新
      - xiaomo    晓墨  文艺+柔和
    """
    if req.voice != tts_service.voice_name:
        tts_service.set_voice(req.voice)

    audio_bytes = tts_service.synthesize(req.text)
    if not audio_bytes:
        return TTSResponse(
            text=req.text,
            voice=req.voice,
            voice_name_cn=SWEET_VOICES.get(req.voice, ("", "", "晓晓", ""))[2],
            duration_estimate=len(req.text) * 0.15,
        )

    return TTSResponse(
        audio_base64=base64.b64encode(audio_bytes).decode("utf-8"),
        audio_format="mp3",
        voice=req.voice,
        voice_name_cn=SWEET_VOICES.get(req.voice, ("", "", "晓晓", ""))[2],
        duration_estimate=len(audio_bytes) / 16000.0,
        text=req.text,
    )


@app.post("/emotion/care_with_voice", response_model=CareResponse)
def get_npc_care_with_voice(req: CareRequest):
    """获取 NPC 关怀回应 — 同时返回甜女声MP3"""
    affect = affect_runtime.latest_packet()
    npc_profile = {}
    for npc in world_engine.state.get("npcs", []):
        if npc.get("id") == req.npc_id:
            npc_profile = npc
            break

    # Use the same GLM care policy as /emotion/care.  This endpoint is the
    # game-facing convenience path: it adds TTS but must not silently fall
    # back to rules while GLM is available.
    care = None
    if npc_glm.enabled:
        result = npc_glm.generate_care_dialogue(
            npc_profile=npc_profile,
            player_emotion=affect,
        )
        if result:
            care = CareResponse(**result)
    if care is None:
        care = _rule_based_care(affect, npc_profile)
    if not care.npc_line:
        return care

    # 用甜女声合成
    audio = tts_service.synthesize(care.npc_line)
    if audio:
        care.audio_base64 = base64.b64encode(audio).decode("utf-8")
        care.audio_format = "mp3"
        care.voice = tts_service.voice_name
        care.voice_name_cn = SWEET_VOICES[tts_service.voice_name][2]

    return care


# ════════════════════════════════════════════════════════════════
# 端点: 性格评估 (UE5 使用)
# ════════════════════════════════════════════════════════════════

_assessment_sessions: dict[str, dict] = {}


@app.post("/assessment/start")
def start_assessment(player_id: str = ""):
    """开始8维性格评估"""
    import time
    session = build_initial_session(int(time.time() * 1000))
    session_id = session.get("session_id", str(uuid.uuid4()))
    _assessment_sessions[session_id] = session
    return {"session_id": session_id, "message": "评估已开始"}


@app.post("/assessment/turn")
def assessment_turn(session_id: str = "", player_input: str = ""):
    """评估对话轮次"""
    session = _assessment_sessions.get(session_id)
    if not session:
        return {"error": "session not found"}
    import time
    now_ms = int(time.time() * 1000)
    # Score the answer
    from backend.assessment_engine import _append_dialogue_turn
    current_q = session.get("current_question", {})
    scoring = score_answer_heuristic(current_q, player_input)
    scores = merge_scoring(session, scoring)
    session["scores"] = scores
    session["dialogue_turns"] = _append_dialogue_turn(
        session.get("dialogue_turns", []), "user", player_input, now_ms
    )
    # Check if should finish
    finish, reason = should_finish(session)
    if finish:
        return {"finished": True, "reason": reason, "scores": scores}
    # Next question
    asked = [q.get("id", "") for q in session.get("asked_questions", [])]
    conf = compute_dimension_confidence(scores, asked)
    next_q = select_next_question(scores, asked, conf)
    session["current_question"] = next_q
    _assessment_sessions[session_id] = session
    return {
        "finished": False,
        "question": next_q.get("question", ""),
        "dimension": next_q.get("dimension", ""),
        "progress": len(asked) / 16,
    }


@app.get("/assessment/state/{session_id}")
def assessment_state(session_id: str):
    """获取评估进度"""
    session = _assessment_sessions.get(session_id, {})
    return {
        "progress": len(session.get("asked_questions", [])) / 16,
        "scores": session.get("scores", {}),
        "turns": len(session.get("dialogue_turns", [])),
    }


@app.post("/assessment/finish/{session_id}")
def finish_assessment(session_id: str):
    """完成评估并返回人格画像"""
    session = _assessment_sessions.get(session_id, {})
    if not session:
        return {"error": "session not found"}
    profile = build_final_profile(session)
    return {"profile": profile}


# ════════════════════════════════════════════════════════════════
# 端点: 开放记忆 (OpenClaw)
# ════════════════════════════════════════════════════════════════


@app.get("/memory/search")
def search_memory(query: str = "", limit: int = 10):
    """搜索记忆"""
    return {"results": openclaw.search(query, limit)}


@app.post("/memory/store")
def store_memory(key: str = "", value: str = "", tags: list[str] = []):
    """存储记忆"""
    openclaw.store(key, value, tags)
    return {"status": "ok"}


# ════════════════════════════════════════════════════════════════
# 端点: 游戏世界 (来自 services/app.py)
# ════════════════════════════════════════════════════════════════


@app.get("/world/state")
def world_state():
    return {"world_state": world_engine.snapshot_cached()}


@app.get("/ai/probe")
def ai_probe():
    """验证游戏世界 GLM 链路，不触发硬件端主动关怀。"""
    return npc_glm.probe()


@app.post("/world/action")
def world_action(action_type: str = "", district: str = "", payload: dict = {}):
    result = world_engine.action(action_type, district, payload)
    return {"message": result.message, "world_state": result.world_state}


@app.post("/world/end_day")
def world_end_day():
    result = world_engine.end_day()
    return {"message": result.message, "world_state": result.world_state}


@app.post("/world/reset")
def world_reset():
    result = world_engine.reset_world()
    return {"message": result.message, "world_state": result.world_state}


@app.post("/ai/pulse")
def ai_pulse(req: AIPulseRequest):
    """AI 世界脉冲 — NPC 决策与演化"""
    allow_live_llm = req.trigger not in {"scheduled", "scheduled_scene"}
    result = world_engine.ai_pulse(
        trigger=req.trigger,
        allow_live_llm=allow_live_llm,
        scene_observation={
            "current_district": req.current_district,
            "player_position": req.player_position,
            "screenshot_b64": req.screenshot_b64,
            "scene_context": req.scene_context,
        },
    )
    return {"message": result.message, "world_state": result.world_state}


@app.post("/npc/player_talk")
def npc_player_talk(req: PlayerTalkRequest):
    """玩家与NPC对话"""
    result = world_engine.player_talk(
        req.npc_id, req.district, req.topic_id, req.approach, req.intent, req.player_input,
        scene_observation={
            "current_district": req.district,
            "player_position": req.player_position,
            "screenshot_b64": req.screenshot_b64,
            "scene_context": req.scene_context,
        },
    )
    return {
        "message": result.message,
        "world_state": result.world_state,
        "dialogue": result.world_state.get("last_dialogue", {}),
    }


@app.get("/npc/list")
def npc_list():
    """获取所有NPC列表"""
    return {"npcs": world_engine.state.get("npcs", [])}


@app.get("/npc/{npc_id}")
def npc_detail(npc_id: str):
    """获取NPC详细信息"""
    for npc in world_engine.state.get("npcs", []):
        if npc.get("id") == npc_id:
            return {"npc": npc}
    return {"error": "NPC not found"}


# ════════════════════════════════════════════════════════════════
# WebSocket: 情感流 (UE5 实时推送)
# ════════════════════════════════════════════════════════════════


@app.websocket("/ws/emotion")
async def emotion_websocket(ws: WebSocket):
    """WebSocket 实时情感流 — UE5 持续推送帧，后端实时返回情感"""
    await ws.accept()
    client_id = str(uuid.uuid4())
    active_websockets[client_id] = ws

    try:
        while True:
            data = await ws.receive_json()
            frame = EmotionFrameIn(**data)

            # 分析情感
            glm_result = glm_emotion.analyze_emotion(
                text_hint=frame.text_hint,
                image_base64=frame.image_base64,
            ) if ENABLE_EMOTION else None

            packet = affect_runtime.build_packet(
                timestamp_ms=frame.timestamp_ms or int(time.time() * 1000),
                image_data_url=f"data:image/jpeg;base64,{frame.image_base64}" if frame.image_base64 else "",
                width=640, height=480,
                audio_features=[],
                audio_pcm16_base64=frame.audio_base64 or "",
                sample_rate=16_000,
                text_hint=frame.text_hint or "",
                legacy_remote_result=None,
                local_expr_label="neutral",
                local_expr_conf=0.5,
            )

            await ws.send_json(packet)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        active_websockets.pop(client_id, None)


@app.websocket("/ws/world")
async def world_websocket(ws: WebSocket):
    """WebSocket 世界状态流"""
    await ws.accept()
    client_id = str(uuid.uuid4())
    active_websockets[client_id] = ws
    try:
        while True:
            data = await ws.receive_json()
            _type = data.get("type", "")
            if _type == "get_state":
                await ws.send_json({"type": "world_state", "data": world_engine.snapshot_cached()})
            elif _type == "action":
                result = world_engine.action(
                    data.get("action_type", ""),
                    data.get("district", ""),
                    data.get("payload", {}),
                )
                await ws.send_json({"type": "world_state", "data": result.world_state})
    except WebSocketDisconnect:
        pass
    finally:
        active_websockets.pop(client_id, None)


# ════════════════════════════════════════════════════════════════
# 启动入口
# ════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("HARDWARE_CARE_PORT", "8010"))
    uvicorn.run("backend.main:app", host="0.0.0.0", port=port, reload=True)
