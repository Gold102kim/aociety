"""完整情感计算管线 — Vision + Audio (SenseVoice) + Pose + Backend

三模态融合管线:
  摄像头 → VisionService → MediaPipe人脸 + FER+表情 + MediaPipe Pose姿态动作
  麦克风 → AudioService → VAD + SenseVoice ASR + 声学特征

  ↓

  三模态数据 → Backend /emotion/analyze → GLM 5.2情感推理
                                    → AffectRuntime 融合
                                    → 主动关怀触发
                                    → TTS 甜女声回复
"""

from __future__ import annotations

import base64
import json
import threading
import time
from typing import Any, Optional

import httpx

from .vision_service import VisionService
from .audio_service import AudioService
from .body_pose_service import BodyPoseService
from .tts_service import TTSService


class EmotionPipeline:
    """全模态情感计算管线 — 多线程协同"""

    def __init__(self, backend_url: str = "http://127.0.0.1:8000"):
        self.backend_url = backend_url.rstrip("/")
        self._http = httpx.Client(base_url=self.backend_url, timeout=15.0)

        # 子服务
        self.vision = VisionService()
        self.audio = AudioService()
        self.pose = BodyPoseService()
        self.tts = TTSService(voice_name="xiaoxiao")

        # 状态
        self._latest_emotion: dict[str, Any] = {}
        self._lock = threading.Lock()

        # 运行控制
        self._running = False
        self._process_thread: Optional[threading.Thread] = None

        # 关怀队列
        self._care_queue: list[dict] = []
        self._care_lock = threading.Lock()

    def start(
        self,
        enable_vision: bool = True,
        enable_audio: bool = True,
        enable_pose: bool = True,
    ) -> None:
        """启动所有采集与处理"""
        if enable_vision:
            self.vision.on_result = self._on_vision
            self.vision.start()

        if enable_audio:
            self.audio.on_transcript = self._on_transcript
            self.audio.start()

        if enable_pose:
            self.pose.on_features = self._on_pose
            self.pose.start()

        self._running = True
        self._process_thread = threading.Thread(target=self._periodic_loop, daemon=True)
        self._process_thread.start()

        print(f"[Pipeline] 完整情感管线已启动 → {self.backend_url}")
        print(f"[Pipeline] 摄像头: {enable_vision} | 麦克风: {enable_audio} | 姿态: {enable_pose}")
        print(f"[Pipeline] 甜女声TTS: {self.tts.voice_name} ({TTSService.SWEET_VOICES[self.tts.voice_name][2]})")

    def stop(self) -> None:
        self._running = False
        self.vision.stop()
        self.audio.stop()
        self.pose.stop()
        if self._process_thread:
            self._process_thread.join(timeout=2.0)
        self._http.close()
        print("[Pipeline] 已停止")

    # ── 回调函数 ──

    def _on_vision(self, result: dict) -> None:
        """处理视觉结果 — 发送摄像头帧给后端"""
        try:
            self._http.post("/emotion/analyze", json={
                "image_base64": result.get("frame_b64", ""),
                "text_hint": "",
                "timestamp_ms": result.get("timestamp_ms", int(time.time() * 1000)),
            }, timeout=10)
            with self._lock:
                self._latest_emotion["expr"] = result.get("expression", "neutral")
                self._latest_emotion["expr_conf"] = result.get("expression_conf", 0.0)
                self._latest_emotion["face"] = result.get("face_present", False)
        except Exception:
            pass

    def _on_transcript(self, text: str, emotion: str = "") -> None:
        """处理 ASR 转写结果"""
        try:
            self._http.post("/emotion/analyze", json={
                "text_hint": text,
                "timestamp_ms": int(time.time() * 1000),
            }, timeout=10)
            with self._lock:
                self._latest_emotion["transcript"] = text
                if emotion:
                    self._latest_emotion["sv_emotion"] = emotion
        except Exception:
            pass

    def _on_pose(self, features: dict) -> None:
        """处理姿态/动作特征"""
        # 不直接发送原始landmarks，改为定期调用时才带上pose信息
        with self._lock:
            self._latest_emotion["pose"] = features

    def _periodic_loop(self) -> None:
        """定期轮询情感状态 & 检查关怀触发"""
        last_care_check = 0
        while self._running:
            try:
                # 1. 拉取情感状态
                r = self._http.get("/emotion/state", timeout=5)
                if r.status_code == 200:
                    with self._lock:
                        self._latest_emotion.update(r.json())
            except Exception:
                pass

            # 2. 检查是否需要触发关怀（每3秒一次）
            now = time.time()
            if now - last_care_check > 3.0:
                last_care_check = now
                self._check_care_trigger()

            time.sleep(1.0)

    def _check_care_trigger(self) -> None:
        """检查主动关怀触发条件"""
        emo = self._latest_emotion
        support_need = emo.get("support_need", 0.0)
        emotion = emo.get("emotion", "neutral")
        arousal = emo.get("arousal", 0.0)

        # 关怀触发条件：关怀需求高 或 检测到负面情绪+姿态差
        should_trigger = support_need > 0.7 or (
            emotion in ["sadness", "frustration", "anxiety"] and support_need > 0.5
        )

        if not should_trigger:
            return

        # 限流：避免重复触发
        with self._care_lock:
            now = time.time()
            self._care_queue = [c for c in self._care_queue if now - c.get("ts", 0) < 60]
            if self._care_queue:
                return
            self._care_queue.append({
                "emotion": emotion,
                "support_need": support_need,
                "ts": now,
            })

        # 调用关怀API
        try:
            r = self._http.post("/emotion/care", json={"npc_id": "npc_01"}, timeout=10)
            if r.status_code == 200:
                care = r.json()
                line = care.get("npc_line", "")
                action = care.get("action", "")
                if line and action != "none":
                    print(f"[Care] {action}: {line}")
                    # 用TTS播放
                    if self.tts:
                        self.tts.synthesize(line)
        except Exception:
            pass

    @property
    def current_emotion(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._latest_emotion)

    def get_npc_care(self, npc_id: str = "") -> dict[str, Any]:
        try:
            r = self._http.post("/emotion/care", json={"npc_id": npc_id})
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        return {"npc_line": "", "action": "none", "care_level": "nudge"}


# ── 独立运行 ──
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="情感计算全管线 (视频+音频+姿态+ASR+GLM+TTS)")
    parser.add_argument("--backend", default="http://127.0.0.1:8000")
    parser.add_argument("--no-vision", action="store_true", help="禁用摄像头")
    parser.add_argument("--no-audio", action="store_true", help="禁用麦克风")
    parser.add_argument("--no-pose", action="store_true", help="禁用姿态检测")
    args = parser.parse_args()

    pipeline = EmotionPipeline(backend_url=args.backend)
    print("=" * 60)
    print("情感计算全管线 - 你可以说中文试试看!")
    print(f"摄像头: {'禁用' if args.no_vision else '启用'}")
    print(f"麦克风: {'禁用' if args.no_audio else '启用'} (ASR: SenseVoice)")
    print(f"姿态: {'禁用' if args.no_pose else '启用'} (MediaPipe Pose)")
    print("=" * 60)

    pipeline.start(
        enable_vision=not args.no_vision,
        enable_audio=not args.no_audio,
        enable_pose=not args.no_pose,
    )

    try:
        while True:
            time.sleep(3)
            emo = pipeline.current_emotion

            expr = emo.get("expr", "?")
            has_face = "👤" if emo.get("face") else "❌"
            emotion = emo.get("emotion", "?")
            valence = emo.get("valence", 0)
            arousal = emo.get("arousal", 0)
            support = emo.get("support_need", 0)
            transcript = emo.get("transcript", "")
            sv_emo = emo.get("sv_emotion", "")
            pose = emo.get("pose", {})

            print(
                f"\r  [{has_face}] 面:{expr:8s} GLM:{emotion:10s}"
                f" V:{valence:.2f} A:{arousal:.2f} Need:{support:.2f}"
                + (f" 🎤\"{transcript[:30]}\"" if transcript else "")
                + (f" 姿态:{pose.get('posture_score',0):.1f}活动:{pose.get('activity_level',0):.1f}" if pose else "")
                + "      ",
                end="", flush=True
            )
    except KeyboardInterrupt:
        print("\n停止中...")
    finally:
        pipeline.stop()
