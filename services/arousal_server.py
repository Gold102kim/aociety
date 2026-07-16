"""Arousal 唤醒度/效价分析服务 — 端口 8002

部署要求:
  - 将 roberta-base-go_emotions 模型文件放入 models/arousal/

标准部署后:
  POST /analyze → {"text": "..."} → {"arousal": 0.5, "valence": 0.5, ...}
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Arousal Detection Service", version="0.1.0")

MODEL_PATH = os.environ.get(
    "AROUSAL_MODEL_PATH",
    str(Path(__file__).resolve().parent.parent / "models" / "arousal"),
)


class TextInput(BaseModel):
    text: str = ""


class ArousalOutput(BaseModel):
    arousal: float = 0.0
    arousal_level: str = "medium"
    valence: float = 0.5
    top_emotion: str = "neutral"
    confidence: float = 0.0
    model_name: str = "roberta-base-go_emotions"


# TODO: 部署实际模型后替换此存根
_MODEL_LOADED = False


def _load_model():
    global _MODEL_LOADED
    model_path = Path(MODEL_PATH)
    if model_path.exists():
        _MODEL_LOADED = True
        print(f"[Arousal] 模型已加载: {model_path}")
    else:
        print(f"[Arousal] 模型未找到: {model_path}，使用规则回退")


@app.on_event("startup")
async def startup():
    _load_model()


@app.post("/analyze", response_model=ArousalOutput)
def analyze(input_data: TextInput):
    """分析文本的唤醒度和效价"""
    if _MODEL_LOADED:
        # ── 实际模型推理 ──
        pass

    # ── 规则回退 ──
    return _rule_based_fallback(input_data.text)


def _rule_based_fallback(text: str) -> ArousalOutput:
    text_lower = text.lower()

    high_arousal_words = ["愤怒", "崩溃", "激动", "兴奋", "恐慌", "狂喜", "震惊", "焦虑", "害怕"]
    low_arousal_words = ["累", "困", "疲惫", "无力", "平静", "放松", "无聊", "疲倦"]
    positive_words = ["开心", "快乐", "幸福", "棒", "好", "爱", "喜欢", "美好"]
    negative_words = ["难过", "伤心", "痛苦", "绝望", "糟糕", "差", "恨", "讨厌"]

    high_count = sum(1 for w in high_arousal_words if w in text)
    low_count = sum(1 for w in low_arousal_words if w in text)
    pos_count = sum(1 for w in positive_words if w in text)
    neg_count = sum(1 for w in negative_words if w in text)

    # Arousal
    net_arousal = (high_count - low_count) / max(high_count + low_count, 1)
    arousal = 0.5 + 0.4 * net_arousal
    arousal = max(0.0, min(1.0, arousal))

    if arousal > 0.65:
        level = "high"
    elif arousal < 0.35:
        level = "low"
    else:
        level = "medium"

    # Valence
    net_valence = (pos_count - neg_count) / max(pos_count + neg_count, 1)
    valence = 0.5 + 0.4 * net_valence
    valence = max(0.0, min(1.0, valence))

    # Top emotion
    if pos_count > neg_count and high_count > low_count:
        top_emo = "joy"
    elif pos_count > neg_count:
        top_emo = "contentment"
    elif neg_count > pos_count and high_count > low_count:
        top_emo = "anger"
    elif neg_count > pos_count:
        top_emo = "sadness"
    else:
        top_emo = "neutral"

    return ArousalOutput(
        arousal=round(arousal, 4),
        arousal_level=level,
        valence=round(valence, 4),
        top_emotion=top_emo,
        confidence=0.5,
        model_name="arousal-rule-fallback",
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
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("AROUSAL_PORT", "8002")))
