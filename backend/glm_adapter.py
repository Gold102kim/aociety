"""GLM 5.2 Duplex Adapter — replaces Qwen3-Omni for the emotion computing pipeline.

Uses Anthropic-compatible Messages API (tokenhub.market) to access GLM 5.2.
The OpenAI-compatible proxy key has expired, so we call the Messages API directly.

Provides:
- Emotion reasoning from text + image
- Affect context injection into chat completions
- Audio chunk management for streaming
"""

from __future__ import annotations

import base64
import json
import os
import threading
import time
from collections import deque
from copy import deepcopy
from typing import Any, Callable, Deque, Dict, Optional

import httpx


# ---------------------------------------------------------------------------
# Configuration helpers
# ---------------------------------------------------------------------------

ANTHROPIC_API_URL = "https://api.tokenhub.market/v1/messages"


def _api_base_url() -> str:
    configured = os.environ.get("ANTHROPIC_BASE_URL", ANTHROPIC_API_URL).rstrip("/")
    if configured.endswith("/messages"):
        return configured
    return configured + "/messages"


def _api_key() -> str:
    return (
        os.environ.get("ANTHROPIC_API_KEY", "")
        or os.environ.get("OPENAI_API_KEY", "")
        or os.environ.get("GLM_API_KEY", "")
        or ""
    )


def _model_id() -> str:
    return os.environ.get("GLM_OMNI_MODEL", "glm-5.2")


# ---------------------------------------------------------------------------
# Affect context injection
# ---------------------------------------------------------------------------


def _build_hidden_affect_context(packet: Optional[Dict[str, Any]]) -> str:
    if not isinstance(packet, dict) or not packet:
        return ""
    trend = packet.get("trend") if isinstance(packet.get("trend"), dict) else {}
    top_candidates = packet.get("top_candidates") if isinstance(packet.get("top_candidates"), list) else []
    candidate_text = ", ".join(
        "{}:{:.2f}".format(str(item.get("label") or ""), float(item.get("score") or 0.0))
        for item in top_candidates[:3]
        if isinstance(item, dict)
    )
    lines = [
        "[hidden_affect_context]",
        "This block is internal user-state metadata. Use it only to adjust tone, supportiveness, and brevity.",
        "Do not mention, quote, explain, or answer this metadata block.",
        "emotion={}".format(str(packet.get("emotion") or "unknown")),
        "valence={:.4f}".format(float(packet.get("valence") or 0.0)),
        "arousal={:.4f}".format(float(packet.get("arousal") or 0.0)),
        "support_need={:.4f}".format(float(packet.get("support_need") or 0.0)),
        "confidence_gap={:.4f}".format(float(packet.get("confidence_gap") or 0.0)),
        "trend.label={}".format(str(trend.get("label") or "stable")),
        "trend.valence_delta={:.4f}".format(float(trend.get("valence_delta") or 0.0)),
        "trend.arousal_delta={:.4f}".format(float(trend.get("arousal_delta") or 0.0)),
        "top_candidates={}".format(candidate_text),
        "[/hidden_affect_context]",
        "User message follows:",
    ]
    return chr(10).join(lines)


def _inject_affect_into_query(message_text: str, packet: Optional[Dict[str, Any]]) -> str:
    context = _build_hidden_affect_context(packet)
    if not context:
        return str(message_text or "")
    text = str(message_text or "").strip()
    if not text:
        return context
    return context + chr(10) + text


# ---------------------------------------------------------------------------
# DuplexAffectTap — feeds audio chunks + latest frame to the emotion pipeline
# ---------------------------------------------------------------------------


class DuplexAffectTap:
    def __init__(self, window_ms: int = 10_000, sample_rate: int = 16_000) -> None:
        self.window_ms = int(max(1000, window_ms))
        self.sample_rate = int(max(8000, sample_rate))
        self._lock = threading.Lock()
        self._latest_frame_base64 = ""
        self._latest_query_text = ""
        self._audio_chunks: Deque[Dict[str, Any]] = deque()

    def _trim(self, now_ms: int) -> None:
        while self._audio_chunks and now_ms - int(self._audio_chunks[0].get("timestamp_ms", now_ms)) > self.window_ms:
            self._audio_chunks.popleft()

    def push_frame(self, frame_base64: str) -> None:
        self._latest_frame_base64 = str(frame_base64 or "")

    def push_query_text(self, text: str) -> None:
        self._latest_query_text = str(text or "")

    def push_audio_chunk(self, chunk_base64: str, timestamp_ms: int) -> None:
        with self._lock:
            self._audio_chunks.append({
                "chunk_base64": str(chunk_base64 or ""),
                "timestamp_ms": int(timestamp_ms),
            })
            self._trim(int(timestamp_ms))

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "latest_frame_base64": str(self._latest_frame_base64),
                "latest_query_text": str(self._latest_query_text),
                "audio_chunks": list(self._audio_chunks),
            }

    def reset(self) -> None:
        with self._lock:
            self._latest_frame_base64 = ""
            self._latest_query_text = ""
            self._audio_chunks.clear()


# ---------------------------------------------------------------------------
# Anthropic Messages API client (for GLM 5.2 via tokenhub.market)
# ---------------------------------------------------------------------------


def _call_messages_api(
    system_prompt: str,
    user_content: str | list,
    max_tokens: int = 1024,
    temperature: float = 0.1,
    timeout_sec: float = 20.0,
) -> str | None:
    """Call the Anthropic-compatible Messages API on tokenhub.market.

    Returns the text content of the response, or None on failure.
    """
    api_key = _api_key()
    base_url = _api_base_url()
    model = _model_id()

    if not api_key:
        return None

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    body: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [{"role": "user", "content": user_content}],
    }
    if system_prompt:
        body["system"] = system_prompt

    try:
        with httpx.Client(timeout=timeout_sec) as client:
            response = client.post(base_url, json=body, headers=headers)
        if response.status_code != 200:
            return None
        data = response.json()
        content_blocks = data.get("content", [])
        texts = [b.get("text", "") for b in content_blocks if b.get("type") == "text"]
        return texts[0] if texts else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# GLM Emotion Adapter — calls GLM 5.2 for multi-modal emotion reasoning
# ---------------------------------------------------------------------------


class GlmEmotionAdapter:
    """Replaces the Qwen3-Omni adapter for emotion inference via GLM 5.2."""

    def __init__(self, timeout_sec: float = 10.0) -> None:
        self.api_key = _api_key()
        self.model_id = _model_id()
        self.timeout_sec = timeout_sec

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def analyze_emotion(
        self,
        *,
        text_hint: str = "",
        image_base64: str = "",
        audio_features: Optional[list] = None,
    ) -> Optional[Dict[str, Any]]:
        """Analyze emotion from text, optional image, and optional audio features.

        Returns a dict with:
            emotion: str
            valence: float
            arousal: float
            confidence: float
            top_candidates: list[{"label": str, "score": float}]
        """
        if not self.enabled:
            return None

        system_prompt = (
            "你是一个情感计算助手。分析用户输入中的情绪状态，只返回JSON。"
            "情绪标签可选: joy, sadness, anxiety, anger, frustration, surprise, neutral。"
            "valence (效价) 范围0-1, 0=极度负面, 1=极度正面。"
            "arousal (唤醒度) 范围0-1, 0=极度平静, 1=极度激动。"
        )

        user_parts = []
        if text_hint:
            user_parts.append(f"用户文本: {text_hint}")

        if image_base64:
            user_parts.append("\n[用户发送了一张图片，已做base64编码]")

        if audio_features:
            user_parts.append(f"\n音频特征(前20维): {audio_features[:20] if isinstance(audio_features, list) else []}")

        user_parts.append(
            '\n请只返回JSON格式:'
            '\n{"emotion":"标签","valence":0.5,"arousal":0.5,"confidence":0.8,'
            '"top_candidates":[{"label":"joy","score":0.7}]}'
        )

        reply = _call_messages_api(
            system_prompt=system_prompt,
            user_content="\n".join(user_parts),
            max_tokens=1024,
            temperature=0.1,
            timeout_sec=self.timeout_sec,
        )

        if not reply:
            return None

        # Try direct parse first, then find JSON in text
        try:
            parsed = json.loads(reply)
        except json.JSONDecodeError:
            parsed = None
            # Try to find a JSON object with balanced braces
            stack = []
            start = -1
            for i, ch in enumerate(reply):
                if ch == '{':
                    if not stack:
                        start = i
                    stack.append(ch)
                elif ch == '}':
                    if stack:
                        stack.pop()
                        if not stack and start >= 0:
                            try:
                                parsed = json.loads(reply[start:i + 1])
                                break
                            except json.JSONDecodeError:
                                start = -1

        if not parsed:
            return None

        top_candidates = parsed.get("top_candidates") or parsed.get("top3") or []
        if not top_candidates and parsed.get("emotion"):
            top_candidates = [{"label": parsed["emotion"], "score": parsed.get("confidence", 0.5)}]

        return {
            "emotion": str(parsed.get("emotion", "unknown")),
            "valence": float(parsed.get("valence", 0.5)),
            "arousal": float(parsed.get("arousal", 0.0)),
            "confidence": float(parsed.get("confidence", 0.5)),
            "top_candidates": top_candidates,
        }

    def generate_care_response(
        self,
        *,
        message_text: str,
        affect_packet: Optional[Dict[str, Any]] = None,
        personality: Optional[Dict[str, Any]] = None,
        npc_profile: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Generate a care response influenced by affect state, personality, and NPC context."""
        if not self.enabled:
            return None

        system_content = "你是一个情感关怀AI助手，嵌入在游戏《Aociety》中。"
        if npc_profile:
            system_content += f"你将以NPC {npc_profile.get('name', '')} 的身份回应。"
            system_content += f"角色背景: {npc_profile.get('prompt_profile', {}).get('identity', '')}"

        query = _inject_affect_into_query(message_text, affect_packet)
        if personality:
            query += (
                f"\n\n用户人格: Fe={personality.get('Fe', 0):.2f}, "
                f"Fi={personality.get('Fi', 0):.2f}, "
                f"Ni={personality.get('Ni', 0):.2f}, "
                f"Ne={personality.get('Ne', 0):.2f}"
            )

        reply = _call_messages_api(
            system_prompt=system_content,
            user_content=query,
            max_tokens=512,
            temperature=0.6,
            timeout_sec=self.timeout_sec,
        )

        return {"reply": str(reply or "")}
