"""R1-Omni-0.5B 情感推理服务 — 端口 8001

部署要求:
  - 将 R1-Omni-0.5B 模型文件放入 models/r1-omni-0.5b/
  - 或通过 R1_OMNI_MODEL_PATH 环境变量指定路径

标准部署后，此服务提供:
  POST /analyze → {"text": "..."} → {"emotion": "...", "valence": ..., "arousal": ...}
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="R1-Omni-0.5B Emotion Service", version="0.1.0")

MODEL_PATH = os.environ.get("R1_OMNI_MODEL_PATH", str(Path(__file__).resolve().parent.parent / "models" / "r1-omni-0.5b"))


class TextInput(BaseModel):
    text: str = ""
    top_k: int = 3


class EmotionOutput(BaseModel):
    emotion: str = "unknown"
    emotion_label: str = ""
    confidence: float = 0.0
    confidence_gap: float = 0.0
    top_candidates: list[dict[str, Any]] = []
    model_name: str = "r1-omni-0.5b"


# TODO: 部署实际模型后替换此存根
_MODEL_LOADED = False


def _load_model():
    global _MODEL_LOADED
    model_path = Path(MODEL_PATH)
    if model_path.exists() and (model_path / "model.safetensors").exists():
        _MODEL_LOADED = True
        print(f"[R1-Omni] 模型已加载: {model_path}")
    else:
        print(f"[R1-Omni] 模型未找到: {model_path}，使用规则回退")


@app.on_event("startup")
async def startup():
    _load_model()


@app.post("/analyze", response_model=EmotionOutput)
def analyze(input_data: TextInput):
    """分析文本情感"""
    if _MODEL_LOADED:
        # ── 实际模型推理 ──
        # from r1_omni import R1Omni
        # result = model.predict(input_data.text)
        pass

    # ── 规则回退 ──
    return _rule_based_fallback(input_data.text)


def _rule_based_fallback(text: str) -> EmotionOutput:
    """基于关键词的简单情感推断"""
    text_lower = text.lower()
    emotion = "neutral"
    confidence = 0.5

    negative_words = ["难过", "伤心", "焦虑", "愤怒", "累", "烦", "压力", "崩溃", "痛苦", "失望"]
    positive_words = ["开心", "快乐", "高兴", "棒", "好", "不错", "喜欢", "爱", "幸福"]

    neg_count = sum(1 for w in negative_words if w in text)
    pos_count = sum(1 for w in positive_words if w in text)

    if neg_count > pos_count:
        emotion = "sadness"
        confidence = 0.5 + 0.1 * min(neg_count, 5)
    elif pos_count > neg_count:
        emotion = "joy"
        confidence = 0.5 + 0.1 * min(pos_count, 5)

    return EmotionOutput(
        emotion=emotion,
        emotion_label=emotion,
        confidence=min(confidence, 1.0),
        confidence_gap=confidence - 0.1,
        top_candidates=[{"label": emotion, "score": round(confidence, 6)}],
        model_name="r1-omni-0.5b-rule",
    )


@app.get("/health")
def health():
    return {
        "status": "ok",
        "model_loaded": _MODEL_LOADED,
        "model_path": MODEL_PATH,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("R1_OMNI_PORT", "8001")))
