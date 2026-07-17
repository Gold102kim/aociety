"""音频处理服务 — VAD + SenseVoice ASR (阿里达摩院) + 声学特征提取

顶级中文语音识别方案:
  1. SenseVoice - 阿里达摩院多语言(中/英/日/韩/粤)，情感识别，超快
  2. FunASR Paraformer - 阿里云工业级高精度
  3. 降级到 sherpa-onnx Paraformer

处理流程:
  麦克风 → VAD活动检测 → SenseVoice ASR → 文本 → 情感分析
                        → 声学特征 → 唤醒度分析
                        → 情感识别（SenseVoice内置）
"""

from __future__ import annotations

import base64
import os
import threading
import time
from pathlib import Path
from typing import Any, Callable, Optional

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = PROJECT_ROOT / "models"


class AudioService:
    """实时音频处理服务 — SenseVoice ASR + VAD + 声学特征"""

    def __init__(self, sample_rate: int = 16000, chunk_sec: float = 1.0):
        self.sample_rate = sample_rate
        self.chunk_sec = chunk_sec
        self.chunk_size = int(sample_rate * chunk_sec)

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # 状态
        self._latest_text = ""
        self._latest_emotion = ""  # SenseVoice内置情感识别
        self._vad_active = False
        self._rms = 0.0
        self._audio_buffer = np.array([], dtype=np.int16)

        # 回调
        self.on_transcript: Optional[Callable[[str, str], None]] = None
        self.on_features: Optional[Callable[[list[float], float], None]] = None

        # 初始化ASR
        self._asr_kind = None
        self._sense_voice = None
        self._paraformer = None
        self._funasr = None
        self._init_asr()

        # VAD参数
        self._vad_threshold = 500
        self._silence_counter = 0
        self._silence_timeout = 20  # 静音20帧后清空缓冲区 (~1.5s)

    def _init_asr(self) -> None:
        """初始化 ASR - 优先级 SenseVoice > FunASR > sherpa-onnx"""

        # 1. 尝试 sherpa-onnx SenseVoice (最理想:本地ONNX)
        sv_search_paths = [
            MODELS_DIR / "asr" / "sensevoice",
            MODELS_DIR / "asr" / "sensevoice_cache" / "iic" / "SenseVoiceSmall",
        ]
        for sv_dir in sv_search_paths:
            if sv_dir.exists() and (sv_dir / "tokens.txt").exists():
                try:
                    import sherpa_onnx
                    sv_files = list(sv_dir.glob("*.onnx"))
                    model_path = sv_files[0] if sv_files else None
                    if model_path:
                        cfg = sherpa_onnx.OfflineRecognizerConfig(
                            model=sherpa_onnx.OfflineModelConfig(
                                sense_voice=sherpa_onnx.OfflineSenseVoiceModelConfig(
                                    model=str(model_path),
                                    language="auto",
                                    use_itn=True,
                                ),
                                tokens=str(sv_dir / "tokens.txt"),
                                num_threads=2,
                            ),
                        )
                        self._sense_voice = sherpa_onnx.OfflineRecognizer(cfg)
                        self._asr_kind = "sense_voice"
                        print(f"[Audio] SenseVoice (本地ONNX @ {sv_dir.name})")
                        return
                except Exception as e:
                    print(f"[Audio] SenseVoice ONNX加载失败 ({sv_dir}): {e}")

        # 2. 尝试 FunASR SenseVoice (本地PT模型)
        for sv_dir in sv_search_paths:
            if sv_dir.exists() and (sv_dir / "model.pt").exists():
                try:
                    from funasr import AutoModel
                    self._funasr = AutoModel(
                        model=str(sv_dir),
                        disable_update=True,
                        disable_log=True,
                    )
                    self._asr_kind = "funasr"
                    print(f"[Audio] FunASR SenseVoice (本地PT @ {sv_dir.name})")
                    return
                except Exception as e:
                    print(f"[Audio] FunASR SenseVoice失败 ({sv_dir}): {e}")

        # 3. 降级到 sherpa-onnx Paraformer
        try:
            import sherpa_onnx
            model_path = MODELS_DIR / "asr" / "sherpa" / "sherpa-onnx-paraformer-zh-small-2024-03-09" / "model.int8.onnx"
            tokens_path = model_path.parent / "tokens.txt"
            if model_path.exists():
                cfg = sherpa_onnx.OfflineRecognizerConfig(
                    model=sherpa_onnx.OfflineModelConfig(
                        paraformer=sherpa_onnx.OfflineParaformerModelConfig(str(model_path)),
                        tokens=str(tokens_path), num_threads=2,
                    ),
                )
                self._paraformer = sherpa_onnx.OfflineRecognizer(cfg)
                self._asr_kind = "paraformer"
                print(f"[Audio] sherpa-onnx Paraformer 降级方案")
        except Exception as e:
            print(f"[Audio] 全部ASR方案加载失败: {e}")

    @property
    def asr_engine(self) -> str:
        return self._asr_kind or "none"

    def start(self) -> None:
        try:
            import sounddevice as sd
            self._running = True
            self._thread = threading.Thread(target=self._capture_loop, daemon=True)
            self._thread.start()
            print(f"[Audio] 麦克风已启动 ({self.sample_rate}Hz, ASR: {self._asr_kind})")
        except ImportError:
            print("[Audio] sounddevice 未安装")

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        print("[Audio] 已停止")

    @property
    def latest_text(self) -> str:
        with self._lock:
            return self._latest_text

    def _transcribe(self, audio_int16: np.ndarray) -> tuple[str, str]:
        """转写一段音频，返回(文本, 情感)"""
        if self._sense_voice:
            try:
                import sherpa_onnx
                stream = self._sense_voice.create_stream()
                stream.accept_waveform(self.sample_rate, audio_int16.tolist())
                self._sense_voice.decode_stream(stream)
                raw_text = stream.result.text.strip()
                text = raw_text
                emotion = ""
                if "<|" in raw_text and "|>" in raw_text:
                    tag = raw_text.split("|")[1] if "|>" in raw_text else ""
                    emotion_map = {
                        "HAPPY": "joy", "SAD": "sadness", "ANGRY": "anger",
                        "NEUTRAL": "neutral", "SURPRISE": "surprise", "FEAR": "anxiety",
                    }
                    emotion = emotion_map.get(tag, "")
                    text = raw_text[raw_text.index("|>") + 2:].split("<|")[0].strip()
                # 包装情感信息给GLM (当SenseVoice识别出真实情感时)
                if emotion and emotion != "neutral":
                    text = f"[用户说: {text}] [用户当前情绪:{emotion}]"
                return text, emotion
            except Exception as e:
                print(f"[Audio] SenseVoice error: {e}")
                return "", ""

        if self._funasr:
            try:
                # FunASR 需要 float32 数组（不能是 int16）
                if audio_int16.dtype != np.float32:
                    audio_f32 = audio_int16.astype(np.float32) / 32768.0
                else:
                    audio_f32 = audio_int16
                result = self._funasr.generate(
                    input=audio_f32,
                    cache={},
                    language="auto",
                    use_itn=True,
                    ban_emo_emo=False,  # 允许情感前缀
                )
                if result and len(result) > 0:
                    raw_text = result[0]["text"]
                    text = raw_text
                    emotion = ""
                    if "<|" in raw_text:
                        parts = raw_text.split("|")
                        for p in parts[1:]:
                            tag = p.split("|>")[0]
                            if tag in ["HAPPY", "SAD", "ANGRY", "NEUTRAL", "SURPRISE", "FEAR"]:
                                emotion = {"HAPPY": "joy", "SAD": "sadness",
                                          "ANGRY": "anger", "NEUTRAL": "neutral",
                                          "SURPRISE": "surprise", "FEAR": "anxiety"}.get(tag, "")
                                break
                        if "woitn" not in raw_text:
                            text = raw_text[raw_text.rindex("|>") + 2:].split("<|")[0].strip()
                        else:
                            text = raw_text.split("woitn")[-1].strip()
                    # 包装成GLM能理解情感的文本 - 把SenseVoice内置情感加入
                    if emotion and emotion != "neutral":
                        text = f"[用户说: {text}] [用户当前情绪:{emotion}]"
                    return text, emotion
            except Exception as e:
                print(f"[Audio] FunASR error: {e}")
                return "", ""

        if self._paraformer:
            try:
                import sherpa_onnx
                stream = self._paraformer.create_stream()
                stream.accept_waveform(self.sample_rate, audio_int16.tolist())
                self._paraformer.decode_stream(stream)
                return stream.result.text.strip(), ""
            except Exception as e:
                return "", ""

        return "", ""

    def _capture_loop(self) -> None:
        import sounddevice as sd

        def callback(indata, frames, _time_info, _status):
            if not self._running:
                return

            audio_chunk = indata[:, 0].copy()
            audio_int16 = (audio_chunk * 32767).astype(np.int16)
            ts = int(time.time() * 1000)

            # VAD检测
            rms = float(np.sqrt(np.mean(audio_chunk ** 2)))
            is_speech = rms > (self._vad_threshold / 32767.0)

            with self._lock:
                self._rms = rms
                self._vad_active = is_speech

            if is_speech:
                self._silence_counter = 0
                with self._lock:
                    self._audio_buffer = np.concatenate([self._audio_buffer, audio_int16])
                    max_buffer = self.sample_rate * 30  # 30秒
                    if len(self._audio_buffer) > max_buffer:
                        self._audio_buffer = self._audio_buffer[-max_buffer:]
            else:
                self._silence_counter += 1

            # 语音段落结束 → ASR转写
            if (not is_speech) and self._silence_counter >= self._silence_timeout and len(self._audio_buffer) > self.sample_rate * 0.3:
                audio_data = None
                with self._lock:
                    audio_data = self._audio_buffer.copy()
                    self._audio_buffer = np.array([], dtype=np.int16)

                if audio_data is not None:
                    text, emotion = self._transcribe(audio_data)
                    if text:
                        with self._lock:
                            self._latest_text = text
                            self._latest_emotion = emotion
                        if self.on_transcript:
                            self.on_transcript(text, emotion)

            # 声学特征回调
            if self.on_features:
                features = [
                    float(rms),
                    float(np.std(audio_chunk)),
                    float(np.max(np.abs(audio_chunk))),
                    float(self._zero_crossing_rate(audio_chunk)),
                    float(np.percentile(np.abs(audio_chunk), 95)),
                ]
                self.on_features(features, ts)

        stream = sd.InputStream(
            samplerate=self.sample_rate, channels=1,
            blocksize=self.chunk_size, callback=callback,
        )
        with stream:
            while self._running:
                time.sleep(0.1)

    def _zero_crossing_rate(self, audio: np.ndarray) -> float:
        """过零率 - 衡量音频高频含量"""
        return float(np.sum(np.diff(np.sign(audio)) != 0) / max(len(audio), 1))

    def analyze_audio_features(self, pcm_int16: np.ndarray) -> dict:
        """
        离线音频特征提取 — 给后端使用
        返回声学特征用于唤醒度推断
        """
        audio = pcm_int16.astype(np.float32) / 32767.0
        rms = float(np.sqrt(np.mean(audio ** 2)))
        zcr = self._zero_crossing_rate(audio)
        peak = float(np.max(np.abs(audio)))
        energy_high = float(np.mean(audio[audio > 0.5] ** 2)) if np.any(audio > 0.5) else 0
        return {
            "rms": rms,
            "zcr": zcr,
            "peak": peak,
            "energy_high": energy_high,
            "arousal_hint": min(1.0, rms * 3 + zcr * 0.5),
        }
