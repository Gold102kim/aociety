"""Aociety 摄像头/麦克风采集模块

从笔记本摄像头和麦克风采集数据，发送到情感计算后端。
支持两种模式：
  1. 独立采集模式 (直接运行) — 用于调试
  2. 模块导入模式 — UE5 通过 Python 插件调用
"""

from __future__ import annotations

import base64
import io
import json
import os
import queue
import sys
import threading
import time
from typing import Any, Callable, Optional

import numpy as np


# ────────────────────────────────────────────────────────────────
# 摄像头采集
# ────────────────────────────────────────────────────────────────


class CameraCapture:
    """笔记本摄像头采集器 — 输出 JPEG base64 帧"""

    def __init__(self, camera_id: int = 0, width: int = 640, height: int = 480, fps: int = 15):
        self.camera_id = camera_id
        self.width = width
        self.height = height
        self.fps = fps
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._cap = None
        self._latest_frame: Optional[str] = None
        self._lock = threading.Lock()
        self.on_frame: Optional[Callable[[str], None]] = None

    def start(self) -> None:
        """启动摄像头采集线程"""
        try:
            import cv2
        except ImportError:
            print("[Camera] opencv-python 未安装，摄像头不可用")
            return

        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        print(f"[Camera] 已启动 (camera_id={self.camera_id}, {self.width}x{self.height} @ {self.fps}fps)")

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        try:
            import cv2
            if self._cap is not None:
                self._cap.release()
        except ImportError:
            pass
        print("[Camera] 已停止")

    @property
    def latest_frame_base64(self) -> str:
        with self._lock:
            return str(self._latest_frame or "")

    def _capture_loop(self) -> None:
        import cv2
        self._cap = cv2.VideoCapture(self.camera_id)
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)

        interval = 1.0 / max(self.fps, 1)
        while self._running:
            ret, frame = self._cap.read()
            if ret:
                # JPEG 编码 → base64
                _, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                b64 = base64.b64encode(buffer).decode("utf-8")
                with self._lock:
                    self._latest_frame = b64
                if self.on_frame:
                    try:
                        self.on_frame(b64)
                    except Exception:
                        pass
            time.sleep(interval)


# ────────────────────────────────────────────────────────────────
# 麦克风采集
# ────────────────────────────────────────────────────────────────


class MicCapture:
    """笔记本麦克风采集器 — 输出 PCM16 base64 音频块"""

    def __init__(self, sample_rate: int = 16000, chunk_sec: float = 1.0, device: Optional[int] = None):
        self.sample_rate = sample_rate
        self.chunk_sec = chunk_sec
        self.device = device
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._queue: queue.Queue = queue.Queue()
        self.on_audio: Optional[Callable[[str, int], None]] = None

    def start(self) -> None:
        """启动麦克风采集线程"""
        try:
            import pyaudio
        except ImportError:
            print("[Mic] pyaudio 未安装，尝试 sounddevice...")
            try:
                import sounddevice  # noqa: F401
            except ImportError:
                print("[Mic] 无可用的音频库，麦克风不可用")
                return

        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        print(f"[Mic] 已启动 (rate={self.sample_rate}Hz, chunk={self.chunk_sec}s)")

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        print("[Mic] 已停止")

    def _capture_loop(self) -> None:
        chunk_size = int(self.sample_rate * self.chunk_sec)
        try:
            import pyaudio
            p = pyaudio.PyAudio()
            stream = p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=chunk_size,
            )
            while self._running:
                data = stream.read(chunk_size, exception_on_overflow=False)
                b64 = base64.b64encode(data).decode("utf-8")
                ts = int(time.time() * 1000)
                if self.on_audio:
                    try:
                        self.on_audio(b64, ts)
                    except Exception:
                        pass
            stream.stop_stream()
            stream.close()
            p.terminate()
        except ImportError:
            # Fallback to sounddevice
            import sounddevice as sd
            def callback(indata, frames, _time_info, _status):
                if self._running:
                    b64 = base64.b64encode(indata.tobytes()).decode("utf-8")
                    ts = int(time.time() * 1000)
                    if self.on_audio:
                        try:
                            self.on_audio(b64, ts)
                        except Exception:
                            pass
            with sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                blocksize=chunk_size,
                callback=callback,
            ):
                while self._running:
                    time.sleep(0.1)


# ────────────────────────────────────────────────────────────────
# 统一采集器 — 同时管理摄像头和麦克风
# ────────────────────────────────────────────────────────────────


class AocietyCapture:
    """统一采集器 — 摄像头 + 麦克风 → 情感分析"""

    def __init__(self, backend_url: str = "http://127.0.0.1:8000"):
        self.backend_url = backend_url.rstrip("/")
        self.camera = CameraCapture()
        self.mic = MicCapture()
        self._session = None
        self._running = False

    def start(self, enable_camera: bool = True, enable_mic: bool = True) -> None:
        """启动采集"""
        import httpx
        self._session = httpx.Client(base_url=self.backend_url, timeout=5.0)

        if enable_camera:
            self.camera.on_frame = self._on_camera_frame
            self.camera.start()

        if enable_mic:
            self.mic.on_audio = self._on_audio_chunk
            self.mic.start()

        self._running = True
        print(f"[AocietyCapture] 已启动 → {self.backend_url}")

    def stop(self) -> None:
        self._running = False
        self.camera.stop()
        self.mic.stop()
        if self._session:
            self._session.close()
        print("[AocietyCapture] 已停止")

    def _on_camera_frame(self, b64: str) -> None:
        if not self._running or not self._session:
            return
        try:
            self._session.post("/emotion/analyze", json={"image_base64": b64})
        except Exception:
            pass

    def _on_audio_chunk(self, b64: str, ts: int) -> None:
        if not self._running or not self._session:
            return
        try:
            self._session.post("/emotion/analyze", json={"audio_base64": b64, "timestamp_ms": ts})
        except Exception:
            pass

    def get_emotion_state(self) -> dict[str, Any]:
        if not self._session:
            return {"error": "not connected"}
        try:
            resp = self._session.get("/emotion/state")
            return resp.json()
        except Exception as e:
            return {"error": str(e)}


# ────────────────────────────────────────────────────────────────
# 独立运行模式 — 用于调试
# ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Aociety 采集调试工具")
    parser.add_argument("--backend", default="http://127.0.0.1:8000", help="后端地址")
    parser.add_argument("--no-camera", action="store_true", help="禁用摄像头")
    parser.add_argument("--no-mic", action="store_true", help="禁用麦克风")
    args = parser.parse_args()

    cap = AocietyCapture(backend_url=args.backend)
    cap.start(enable_camera=not args.no_camera, enable_mic=not args.no_mic)

    try:
        print("\n按 Ctrl+C 停止并显示最新情感状态\n")
        while True:
            time.sleep(5)
            state = cap.get_emotion_state()
            print(f"  情绪: {state.get('emotion', '?')}  "
                  f"效价: {state.get('valence', 0):.3f}  "
                  f"唤醒度: {state.get('arousal', 0):.3f}  "
                  f"关怀需求: {state.get('support_need', 0):.3f}")
    except KeyboardInterrupt:
        print("\n停止中...")
    finally:
        cap.stop()
