"""TTS文字转语音服务 — 顶级甜女声

主方案: Edge TTS (微软) — 云端，超快，世界级甜女声
备选方案: pyttsx3 — 完全离线
备选方案2: CosyVoice (阿里) — 下载到本地后可离线使用

推荐甜女声列表 (Edge TTS):
  zh-CN-XiaoxiaoNeural   晓晓    - 甜、温暖、年轻  ★推荐
  zh-CN-XiaoyiNeural     晓伊    - 温暖、自然
  zh-CN-XiaomengNeural   晓梦    - 可爱、清新
  zh-CN-XiaomoNeural     晓墨    - 文艺、柔和
  zh-CN-XiaoxuanNeural   晓萱    - 温润
  zh-CN-XiaoruiNeural    晓睿    - 成熟
  zh-CN-XiaoqiuNeural    晓秋    - 温和
"""

from __future__ import annotations

import asyncio
import base64
import io
import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Callable, Optional


PROJECT_ROOT = Path(__file__).resolve().parent.parent
TTS_DIR = PROJECT_ROOT / "models" / "tts"


# 顶级甜女声列表
SWEET_VOICES = {
    "xiaoxiao": ("zh-CN", "XiaoxiaoNeural", "晓晓", "sweet-warm-young", True),
    "xiaoyi": ("zh-CN", "XiaoyiNeural", "晓伊", "warm-friendly", True),
    "xiaomeng": ("zh-CN", "XiaomengNeural", "晓梦", "cute-fresh-young", True),
    "xiaomo": ("zh-CN", "XiaomoNeural", "晓墨", "literary-soft", True),
    "xiaoxuan": ("zh-CN", "XiaoxuanNeural", "晓萱", "warm-soft", True),
    "xiaorui": ("zh-CN", "XiaoruiNeural", "晓睿", "mature-warm", True),
    "xiaojiao": ("zh-CN", "XiaojiaoNeural", "晓骄", "news-anchor", True),
    "yunxi": ("zh-CN", "YunxiNeural", "云希", "male-young", False),
}

DEFAULT_VOICE = "xiaoxiao"  # 默认甜女声 - 晓晓


class TTSService:
    """文字转语音服务 — 微软Edge TTS + 离线备选"""

    def __init__(self, voice_name: str = DEFAULT_VOICE):
        self.voice_name = voice_name
        self._tts_method = "edge"  # 'edge' or 'pyttsx3'
        self._edge_tts_module = None
        self._pyttsx3_engine = None
        self._init_tts()

    @staticmethod
    def list_voices() -> list[dict]:
        """列出可用甜女声"""
        return [
            {"id": k, "name_cn": v[2], "description": v[3], "sweet": v[4]}
            for k, v in SWEET_VOICES.items()
        ]

    def _init_tts(self) -> None:
        # 优先 Edge TTS (在线，质量高)
        try:
            import edge_tts
            self._edge_tts_module = edge_tts
            self._tts_method = "edge"
            print(f"[TTS] edge-tts loaded (声音: {self.voice_name})")
        except ImportError:
            print("[TTS] edge-tts 未安装")
            self._init_pyttsx3()
        except Exception as e:
            print(f"[TTS] edge-tts 错误: {e}")
            self._init_pyttsx3()

    def _init_pyttsx3(self) -> None:
        """降级到本地 pyttsx3 TTS"""
        try:
            import pyttsx3
            self._pyttsx3_engine = pyttsx3.init()
            self._pyttsx3_engine.setProperty("rate", 150)
            self._pyttsx3_engine.setProperty("volume", 1.0)
            self._tts_method = "pyttsx3"
            print("[TTS] pyttsx3 loaded (offline fallback)")
        except Exception as e:
            print(f"[TTS] pyttsx3 加载失败: {e}")

    def set_voice(self, voice_name: str) -> bool:
        """切换甜女声"""
        if voice_name in SWEET_VOICES:
            self.voice_name = voice_name
            print(f"[TTS] 已切换到: {SWEET_VOICES[voice_name][2]} ({voice_name})")
            return True
        return False

    async def _edge_synthesize(self, text: str) -> Optional[bytes]:
        """用 Edge TTS 合成语音 (异步)"""
        if not self._edge_tts_module:
            return None
        voice_info = SWEET_VOICES.get(self.voice_name, SWEET_VOICES[DEFAULT_VOICE])
        voice_id = f"{voice_info[0]}-{voice_info[1]}"
        try:
            communicate = self._edge_tts_module.Communicate(text, voice_id)
            audio_data = b""
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_data += chunk["data"]
            return audio_data if audio_data else None
        except Exception as e:
            print(f"[TTS] Edge合成失败: {e}")
            return None

    def _edge_synthesize_sync(self, text: str) -> Optional[bytes]:
        """Edge TTS同步合成"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(self._edge_synthesize(text))
        except Exception:
            return None
        finally:
            try:
                loop.close()
            except Exception:
                pass

    def synthesize(self, text: str, save_path: Optional[str] = None) -> Optional[bytes]:
        """
        合成语音

        Args:
            text: 要合成的文字
            save_path: 可选，保存到的文件路径

        Returns:
            bytes 音频数据 (MP3格式) 或 None
        """
        if not text or not text.strip():
            return None

        if self._tts_method == "edge":
            audio = self._edge_synthesize_sync(text)
            if save_path and audio:
                with open(save_path, "wb") as f:
                    f.write(audio)
            return audio
        elif self._tts_method == "pyttsx3":
            # pyttsx3 直接播放，不返回bytes
            try:
                self._pyttsx3_engine.say(text)
                self._pyttsx3_engine.runAndWait()
                return None
            except Exception as e:
                print(f"[TTS] pyttsx3错误: {e}")
                return None
        return None

    def synthesize_to_file(self, text: str, save_path: str) -> bool:
        """合成并保存到文件"""
        result = self.synthesize(text, save_path)
        return result is not None or os.path.exists(save_path)

    def play_immediately(self, text: str) -> bool:
        """立即播放（pyttsx3 同步播放）"""
        if self._tts_method == "pyttsx3":
            try:
                self._pyttsx3_engine.say(text)
                self._pyttsx3_engine.runAndWait()
                return True
            except Exception:
                return False
        else:
            # Edge TTS 异步播放
            audio = self.synthesize(text)
            if audio:
                return self._play_bytes(audio)
            return False

    def _play_bytes(self, audio_bytes: bytes) -> bool:
        """播放音频bytes (默认系统播放器)"""
        try:
            # Windows: 通过系统播放
            import tempfile
            tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            tmp.write(audio_bytes)
            tmp.close()
            if os.name == "nt":
                os.startfile(tmp.name)
            else:
                subprocess.run(["afplay" if os.uname().sysname == "Darwin" else "mpg123", tmp.name])
            return True
        except Exception:
            return False


# ── 测试演示 ──
if __name__ == "__main__":
    print("=" * 50)
    print("甜女声列表:")
    for v in TTSService.list_voices():
        star = "[recommended]" if v["sweet"] and v["id"] == "xiaoxiao" else ""
        print(f"  {v['id']:10s} | {v['name_cn']} - {v['description']:25s} {star}")

    print()
    service = TTSService(voice_name="xiaoxiao")
    print(f"默认声音: {SWEET_VOICES[service.voice_name][2]}")

    # 合成测试
    test_text = "主人，看你一直在电脑前坐着，要不要起来喝杯水，活动活动？"
    print(f"\n合成文本: {test_text}")
    out_path = str(PROJECT_ROOT / "test_sweet_voice.mp3")
    audio = service.synthesize(test_text, save_path=out_path)
    if audio:
        print(f"✓ 合成成功: {len(audio)} bytes → {out_path}")
    else:
        print(f"✗ 合成失败")
