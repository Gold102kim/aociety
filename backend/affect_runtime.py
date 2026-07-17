from __future__ import annotations

import os
import json
import threading
import time
from collections import deque
from copy import deepcopy
from typing import Any, Deque, Dict, List, Optional

import httpx


def _env(name: str, default: str = "") -> str:
    value = os.environ.get(name)
    return value if value is not None and value != "" else default


def _env_bool(name: str, default: bool = False) -> bool:
    raw = _env(name, "1" if default else "0").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _normalize_emotion_label(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return "unknown"
    mapping = {
        "happiness": "joy",
        "happy": "joy",
        "sad": "sadness",
        "fear": "anxiety",
        "neutrality": "neutral",
    }
    return mapping.get(raw, raw)


def _emotion_prior(label: str) -> float:
    mapping = {
        "joy": 0.10,
        "neutral": 0.10,
        "sadness": 0.70,
        "anxiety": 0.80,
        "anger": 0.75,
        "frustration": 0.70,
    }
    return float(mapping.get(_normalize_emotion_label(label), 0.35))


def _normalize_top_candidates(raw: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    normalized: List[Dict[str, Any]] = []
    for item in raw[:5]:
        if isinstance(item, dict):
            label = _normalize_emotion_label(item.get("label"))
            score = _clamp(item.get("score", item.get("confidence", 0.0)))
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            label = _normalize_emotion_label(item[0])
            score = _clamp(item[1])
        else:
            continue
        if not label:
            continue
        normalized.append({"label": label, "score": round(score, 6)})
    normalized.sort(key=lambda row: row.get("score", 0.0), reverse=True)
    return normalized


def _compute_confidence_gap(top_candidates: List[Dict[str, Any]], fallback_confidence: float) -> float:
    if len(top_candidates) >= 2:
        return _clamp(_safe_float(top_candidates[0].get("score")) - _safe_float(top_candidates[1].get("score")))
    if len(top_candidates) == 1:
        return _clamp(_safe_float(top_candidates[0].get("score", fallback_confidence)))
    return _clamp(fallback_confidence)


class JsonServiceClient:
    def __init__(self, env_key: str, default_url: str = "", timeout_sec: float = 6.0) -> None:
        self.url = _env(env_key, default_url).strip()
        self.timeout_sec = timeout_sec

    @property
    def enabled(self) -> bool:
        return bool(self.url)

    def infer(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self.enabled:
            return None
        try:
            with httpx.Client(timeout=self.timeout_sec, trust_env=False) as client:
                response = client.post(self.url, json=payload)
            response.raise_for_status()
            data = response.json()
            return data if isinstance(data, dict) else None
        except Exception:
            return None


class AffectRuntime:
    def __init__(self, window_ms: int = 10_000) -> None:
        self.window_ms = int(max(1000, window_ms))
        self._lock = threading.Lock()
        self._history: Deque[Dict[str, Any]] = deque()
        self._latest: Optional[Dict[str, Any]] = None
        self.enable_legacy_fallback = _env_bool("AFFECT_ENABLE_LEGACY_VISUALFOCUS", False)
        self.enable_rjcma_service = _env_bool(
            "AFFECT_ENABLE_VA",
            _env_bool("AFFECT_ENABLE_RJCMA", False),
        )
        self.r1_client = JsonServiceClient("AFFECT_R1_URL", default_url="")
        self.arousal_client = JsonServiceClient("AFFECT_AROUSAL_URL", default_url="", timeout_sec=4.0)
        self.rjcma_client = JsonServiceClient("AFFECT_RJCMA_URL")
        self.legacy_client = JsonServiceClient(
            "LUNWEN_REMOTE_EMOTION_URL",
            timeout_sec=12.0,
        )
        # Build default URLs from CF_TUNNEL_URL if individual URLs not set
        cf_url = _env("CF_TUNNEL_URL", "").strip()
        if cf_url:
            cf_url = cf_url.rstrip("/")
            if not self.r1_client.url:
                self.r1_client.url = f"{cf_url}/r1/v1/chat/completions"
            if not self.arousal_client.url:
                self.arousal_client.url = f"{cf_url}/arousal/analyze"

    def _trim(self, now_ms: int) -> None:
        while self._history and now_ms - int(self._history[0].get("timestamp_ms", now_ms)) > self.window_ms:
            self._history.popleft()

    def service_status(self) -> Dict[str, Any]:
        return {
            "r1_enabled": self.r1_client.enabled,
            "rjcma_enabled": self.rjcma_client.enabled,
            "arousal_enabled": self.arousal_client.enabled,
            "r1_url": self.r1_client.url,
            "rjcma_url": self.rjcma_client.url,
            "arousal_url": self.arousal_client.url,
            "va_enabled": self.rjcma_client.enabled or self.arousal_client.enabled,
            "va_url": self.rjcma_client.url or self.arousal_client.url,
            "hgrjca_enabled": self.rjcma_client.enabled,
            "legacy_enabled": self.enable_legacy_fallback,
            "rjcma_active": self.enable_rjcma_service,
            "va_active": self.enable_rjcma_service,
        }

    def latest_packet(self) -> Dict[str, Any]:
        with self._lock:
            if self._latest:
                return deepcopy(self._latest)
        return self.default_packet()

    def default_packet(self) -> Dict[str, Any]:
        return {
            "emotion": "unknown",
            "valence": 0.5,
            "arousal": 0.0,
            "support_need": 0.0,
            "trend": {
                "window_ms": self.window_ms,
                "emotion_stability": 0.0,
                "valence_delta": 0.0,
                "arousal_delta": 0.0,
                "support_need_delta": 0.0,
                "label": "stable",
            },
            "confidence_gap": 0.0,
            "top_candidates": [],
            "timestamp_ms": int(time.time() * 1000),
            "source_models": {},
            "degraded": True,
            "status": "degraded",
        }

    def _support_need(
        self,
        emotion: str,
        valence: float,
        arousal: float,
        confidence_gap: float,
        valence_delta: float,
        arousal_delta: float,
    ) -> float:
        negative_valence = 1.0 - _clamp(valence)
        high_arousal = _clamp(max(arousal - 0.5, 0.0) * 2.0)
        negative_trend = _clamp((-valence_delta + arousal_delta) / 2.0)
        uncertainty = 1.0 - _clamp(confidence_gap)
        emotion_prior = _emotion_prior(emotion)
        return _clamp(
            0.40 * negative_valence
            + 0.20 * high_arousal
            + 0.20 * emotion_prior
            + 0.15 * negative_trend
            + 0.05 * uncertainty
        )

    def _trend_label(self, valence_delta: float, arousal_delta: float) -> str:
        if valence_delta < -0.08 and arousal_delta >= -0.02:
            return "downward_negative"
        if valence_delta > 0.08 and arousal_delta <= 0.02:
            return "upward_relief"
        if arousal_delta > 0.10:
            return "high_arousal_rising"
        return "stable"

    def update(
        self,
        *,
        timestamp_ms: int,
        emotion: str,
        valence: float,
        arousal: float,
        confidence_gap: float,
        top_candidates: List[Dict[str, Any]],
        source_models: Dict[str, Any],
        degraded: bool,
    ) -> Dict[str, Any]:
        emotion = _normalize_emotion_label(emotion)
        valence = _clamp(valence)
        arousal = _clamp(arousal)
        confidence_gap = _clamp(confidence_gap)
        top_candidates = _normalize_top_candidates(top_candidates)
        sample = {
            "timestamp_ms": int(timestamp_ms),
            "emotion": emotion,
            "valence": valence,
            "arousal": arousal,
            "confidence_gap": confidence_gap,
            "top_candidates": top_candidates,
        }
        with self._lock:
            self._history.append(sample)
            self._trim(int(timestamp_ms))
            history = list(self._history)
            first = history[0]
            last = history[-1]
            valence_delta = round(_safe_float(last["valence"]) - _safe_float(first["valence"]), 6)
            arousal_delta = round(_safe_float(last["arousal"]) - _safe_float(first["arousal"]), 6)
            stability_hits = sum(1 for row in history if row.get("emotion") == emotion)
            emotion_stability = round(stability_hits / max(len(history), 1), 6)
            support_need = self._support_need(emotion, valence, arousal, confidence_gap, valence_delta, arousal_delta)
            first_support = self._support_need(
                _normalize_emotion_label(first.get("emotion")),
                _safe_float(first.get("valence"), 0.5),
                _safe_float(first.get("arousal"), 0.0),
                _safe_float(first.get("confidence_gap"), 0.0),
                0.0,
                0.0,
            )
            support_need_delta = round(support_need - first_support, 6)
            packet = {
                "emotion": emotion,
                "valence": round(valence, 6),
                "arousal": round(arousal, 6),
                "support_need": round(support_need, 6),
                "trend": {
                    "window_ms": self.window_ms,
                    "emotion_stability": emotion_stability,
                    "valence_delta": valence_delta,
                    "arousal_delta": arousal_delta,
                    "support_need_delta": support_need_delta,
                    "label": self._trend_label(valence_delta, arousal_delta),
                },
                "confidence_gap": round(confidence_gap, 6),
                "top_candidates": top_candidates,
                "timestamp_ms": int(timestamp_ms),
                "source_models": dict(source_models or {}),
                "degraded": bool(degraded),
                "status": "degraded" if degraded else "ok",
            }
            self._latest = deepcopy(packet)
            return packet

    def build_packet(
        self,
        *,
        timestamp_ms: int,
        image_data_url: str,
        width: int,
        height: int,
        audio_features: List[float],
        audio_pcm16_base64: str = "",
        sample_rate: int = 16_000,
        text_hint: str = "",
        legacy_remote_result: Optional[Dict[str, Any]],
        local_expr_label: str,
        local_expr_conf: float,
        allow_legacy_fallback: Optional[bool] = None,
        use_rjcma_service: Optional[bool] = None,
    ) -> Dict[str, Any]:
        if allow_legacy_fallback is None:
            allow_legacy_fallback = self.enable_legacy_fallback
        if use_rjcma_service is None:
            use_rjcma_service = self.enable_rjcma_service
        payload = {
            "timestamp_ms": int(timestamp_ms),
            "image_data_url": image_data_url,
            "width": int(width),
            "height": int(height),
            "audio_features": list(audio_features or []),
            "audio_pcm16_base64": str(audio_pcm16_base64 or ""),
            "sample_rate": int(sample_rate or 16000),
            "text_hint": str(text_hint or ""),
        }
        if not isinstance(legacy_remote_result, dict) and allow_legacy_fallback:
            legacy_remote_result = self.legacy_client.infer(payload)
        # R1-Omni emotion reasoning: use chat completions format with text_hint
        r1_raw = None
        if self.r1_client.enabled and text_hint:
            r1_payload = {
                "model": "R1-Omni-0.5B",
                "messages": [
                    {"role": "system", "content": "你是一个情感分析助手。分析用户文本中的情感状态，返回JSON格式：{\"emotion\":\"情感标签\",\"confidence\":0.0-1.0}"},
                    {"role": "user", "content": text_hint},
                ],
                "max_tokens": 128,
            }
            r1_raw = self.r1_client.infer(r1_payload)
        rjcma_raw = self.rjcma_client.infer(payload) if use_rjcma_service else None
        # Arousal detection: use text-based arousal analysis
        arousal_raw = None
        if self.arousal_client.enabled and text_hint:
            arousal_raw = self.arousal_client.infer({"text": text_hint})

        top_candidates: List[Dict[str, Any]] = []
        emotion = _normalize_emotion_label(local_expr_label)
        confidence = _clamp(local_expr_conf)
        source_models: Dict[str, Any] = {}
        degraded = False

        if isinstance(r1_raw, dict) and (
            r1_raw.get("emotion") is not None
            or r1_raw.get("emotion_label") is not None
            or r1_raw.get("label") is not None
        ):
            source_models["emotion"] = str(r1_raw.get("model_name") or r1_raw.get("model") or "r1-omni-0.5b")
            emotion = _normalize_emotion_label(
                r1_raw.get("emotion")
                or r1_raw.get("emotion_label")
                or r1_raw.get("label")
                or emotion
            )
            top_candidates = _normalize_top_candidates(
                r1_raw.get("emotion_topk")
                or r1_raw.get("top_candidates")
                or r1_raw.get("top3")
            )
            confidence = _clamp(
                r1_raw.get("confidence_gap")
                or r1_raw.get("confidence")
                or (top_candidates[0].get("score") if top_candidates else confidence)
            )
        elif isinstance(r1_raw, dict) and r1_raw.get("choices"):
            # R1-Omni returned a chat completion response — parse the text content
            try:
                content = str(r1_raw["choices"][0].get("message", {}).get("content", "")).strip()
                import re as _re
                json_match = _re.search(r'\{[^}]+\}', content)
                if json_match:
                    parsed = json.loads(json_match.group())
                    if parsed.get("emotion") or parsed.get("emotion_label") or parsed.get("label"):
                        source_models["emotion"] = "r1-omni-0.5b"
                        emotion = _normalize_emotion_label(
                            parsed.get("emotion") or parsed.get("emotion_label") or parsed.get("label") or emotion
                        )
                        confidence = _clamp(parsed.get("confidence", confidence))
                        top_candidates = [{"label": emotion, "score": round(confidence, 6)}]
                else:
                    source_models["emotion"] = "r1-omni-0.5b-text"
                    emotion = _normalize_emotion_label(content.split()[0] if content else emotion)
                    confidence = _clamp(0.6)
                    top_candidates = [{"label": emotion, "score": round(confidence, 6)}]
            except Exception:
                source_models["emotion"] = "r1-omni-0.5b-parse-failed"
                top_candidates = [{"label": emotion, "score": round(confidence, 6)}]
        elif isinstance(legacy_remote_result, dict) and legacy_remote_result:
            pred = dict(legacy_remote_result.get("emotion_prediction", {}) or {})
            emotion = _normalize_emotion_label(pred.get("label") or emotion)
            top_candidates = _normalize_top_candidates(pred.get("top3"))
            confidence = _clamp(pred.get("confidence", confidence))
            source_models["emotion"] = str(legacy_remote_result.get("model_name") or "legacy_visualfocus_fallback")
            degraded = True
        else:
            top_candidates = [{"label": emotion, "score": round(confidence, 6)}]
            source_models["emotion"] = "local_expression_fallback"
            degraded = True

        confidence_gap = _compute_confidence_gap(top_candidates, confidence)

        if isinstance(rjcma_raw, dict) and (
            rjcma_raw.get("valence") is not None or rjcma_raw.get("arousal") is not None
        ):
            source_models["va"] = str(rjcma_raw.get("model_name") or rjcma_raw.get("model") or "abaw8-hgrjca-va")
            valence = _clamp(rjcma_raw.get("valence", 0.5))
            arousal = _clamp(rjcma_raw.get("arousal", 0.0))
        elif isinstance(arousal_raw, dict) and (
            arousal_raw.get("arousal") is not None
        ):
            # Arousal detection service (roberta-base-go_emotions on 8093)
            source_models["va"] = str(arousal_raw.get("top_emotion", "")) + "+arousal-service"
            arousal = _clamp(arousal_raw.get("arousal", 0.0))
            valence = _clamp(0.5 + (0.3 if arousal_raw.get("arousal_level") == "high" else -0.1 if arousal_raw.get("arousal_level") == "low" else 0.0))
        elif isinstance(legacy_remote_result, dict) and legacy_remote_result:
            state_vector = dict(legacy_remote_result.get("state_vector", {}) or {})
            valence = _clamp(state_vector.get("valence", 0.5))
            arousal = _clamp(state_vector.get("arousal", 0.0))
            source_models["va"] = str(legacy_remote_result.get("model_name") or "legacy_visualfocus_fallback")
            degraded = True
        else:
            latest = self.latest_packet()
            valence = _clamp(latest.get("valence", 0.5))
            arousal = _clamp(latest.get("arousal", 0.0))
            source_models["va"] = "va_fallback_latest_packet"
            degraded = True

        return self.update(
            timestamp_ms=timestamp_ms,
            emotion=emotion,
            valence=valence,
            arousal=arousal,
            confidence_gap=confidence_gap,
            top_candidates=top_candidates,
            source_models=source_models,
            degraded=degraded,
        )
