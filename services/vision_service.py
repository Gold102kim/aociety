"""视觉处理服务 — MediaPipe FaceLandmarker (新版API) + FER+表情识别

新版 MediaPipe 0.10+ 使用 Tasks API:
  mp.tasks.vision.FaceLandmarker

输出:
  - 478个面部关键点
  - 视线/姿态/表情信息
  - 基础面部几何用于疲劳检测
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
FACE_MODEL = MODELS_DIR / "mediapipe" / "face_landmarker.task"


class VisionService:
    """实时视觉情感分析服务 — 使用 MediaPipe Tasks API (v0.10+)"""

    def __init__(self, camera_id: int = 0, width: int = 640, height: int = 480):
        self.camera_id = camera_id
        self.width = width
        self.height = height
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._cap = None
        self._lock = threading.Lock()

        # 状态
        self._latest_frame_b64 = ""
        self._latest_expression = "neutral"
        self._latest_expression_conf = 0.0
        self._face_present = False
        self._gaze_x = self._gaze_y = 0.0
        self._head_pitch = 0.0
        self._face_blendshapes: dict = {}

        # 回调
        self.on_result: Optional[Callable[[dict], None]] = None

        # 模型
        self._face_landmarker = None
        self._fer_session = None
        self._fer_input_name = None
        self._face_cascade = None
        self._init_models()

    def _init_models(self) -> None:
        """初始化 MediaPipe FaceLandmarker (Tasks API) + FER+"""
        # FER+ ONNX 表情分类器
        fer_path = str(MODELS_DIR / "ferplus" / "emotion-ferplus-8.onnx")
        if Path(fer_path).exists():
            try:
                import onnxruntime as ort
                self._fer_session = ort.InferenceSession(fer_path)
                self._fer_input_name = self._fer_session.get_inputs()[0].name
                print(f"[Vision] FER+ 表情模型已加载: {fer_path}")
            except Exception as e:
                print(f"[Vision] FER+ 加载失败: {e}")

        # Haar 级联（用于在 FaceLandmarker 找到的 bbox 内做FER+ ROI）
        try:
            import cv2
            self._face_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            )
        except Exception:
            pass

        # MediaPipe FaceLandmarker (新Tasks API)
        if FACE_MODEL.exists():
            try:
                import mediapipe as mp
                from mediapipe.tasks import python
                from mediapipe.tasks.python import vision

                base_options = python.BaseOptions(model_asset_path=str(FACE_MODEL))
                options = vision.FaceLandmarkerOptions(
                    base_options=base_options,
                    output_face_blendshapes=True,
                    output_facial_transformation_matrixes=True,
                    num_faces=1,
                    min_face_detection_confidence=0.3,
                    min_face_presence_confidence=0.3,
                    min_tracking_confidence=0.3,
                )
                self._face_landmarker = vision.FaceLandmarker.create_from_options(options)
                print(f"[Vision] MediaPipe FaceLandmarker (Tasks API) 已加载")
            except Exception as e:
                print(f"[Vision] FaceLandmarker 加载失败: {e}")
        else:
            print(f"[Vision] 模型文件不存在: {FACE_MODEL}")

    @property
    def latest_frame_base64(self) -> str:
        with self._lock:
            return self._latest_frame_b64

    @property
    def latest_features(self) -> dict:
        with self._lock:
            return {
                "face_present": self._face_present,
                "expression": self._latest_expression,
                "expression_conf": self._latest_expression_conf,
                "gaze_x": self._gaze_x,
                "gaze_y": self._gaze_y,
                "head_pitch": self._head_pitch,
                "blendshapes": self._face_blendshapes,
            }

    def start(self) -> None:
        try:
            import cv2
        except ImportError:
            print("[Vision] opencv-python not installed")
            return

        self._cap = cv2.VideoCapture(self.camera_id)
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self._cap.set(cv2.CAP_PROP_FPS, 15)

        self._running = True
        self._thread = threading.Thread(target=self._process_loop, daemon=True)
        self._thread.start()
        print(f"[Vision] Started (camera={self.camera_id})")

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        if self._cap:
            self._cap.release()
        print("[Vision] Stopped")

    def process_frame(self, frame_bgr) -> dict:
        """处理单帧图像，返回情感特征 (可独立于摄像头调用)"""
        import cv2
        ts = int(time.time() * 1000)
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)

        face_present = False
        expression = "neutral"
        expression_conf = 0.0
        gaze_x = gaze_y = 0.0
        head_pitch = 0.0
        blendshapes = {}

        # MediaPipe FaceLandmarker (新版)
        if self._face_landmarker:
            try:
                import mediapipe as mp
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                result = self._face_landmarker.detect(mp_image)

                if result and result.face_landmarks:
                    face_present = True
                    landmarks = result.face_landmarks[0]

                    # 视线估计: 取眼睛中心 (landmark 33, 263)
                    if len(landmarks) > 263:
                        left_eye = landmarks[33]
                        right_eye = landmarks[263]
                        gaze_x = float((left_eye.x + right_eye.x) / 2 - 0.5)
                        gaze_y = float((left_eye.y + right_eye.y) / 2 - 0.5)

                    # 头部姿态 (用面部transformation matrix)
                    if result.facial_transformation_matrixes:
                        mat = result.facial_transformation_matrixes[0]
                        # Y轴旋转 (俯仰角)
                        head_pitch = float(mat[1][3] if len(mat) > 1 else 0.0)

                    # 表情blendshapes
                    if result.face_blendshapes:
                        bs = result.face_blendshapes[0]
                        blendshapes = {c.category_name: c.score for c in bs[:15]}

                        # 提取 FER+ 等价类别
                        # MediaPipe blendshapes 含 smile, browDown, jawOpen 等
                        smile = blendshapes.get("mouthSmile", 0.0) - blendshapes.get("mouthFrown", 0.0)
                        brow_down = blendshapes.get("browDownLeft", 0.0) + blendshapes.get("browDownRight", 0.0)
                        brow_inner_up = blendshapes.get("browInnerUp", 0.0)
                        jaw_open = blendshapes.get("jawOpen", 0.0)
                        eye_wide = blendshapes.get("eyeWideLeft", 0.0) + blendshapes.get("eyeWideRight", 0.0)
                        mouth_frown = blendshapes.get("mouthFrown", 0.0)

                        # 启发式表情分类
                        if smile > 0.3:
                            expression = "happiness"
                            expression_conf = min(0.9, smile)
                        elif brow_inner_up > 0.5 and eye_wide > 0.3:
                            expression = "surprise"
                            expression_conf = min(0.8, eye_wide)
                        elif mouth_frown > 0.3 and brow_down > 0.3:
                            expression = "sadness"
                            expression_conf = min(0.8, mouth_frown)
                        elif brow_down > 0.6:
                            expression = "anger"
                            expression_conf = min(0.8, brow_down)
                        elif jaw_open > 0.5:
                            expression = "surprise"
                            expression_conf = min(0.7, jaw_open)
                        else:
                            expression = "neutral"
                            expression_conf = 0.5
            except Exception as e:
                pass

        # FER+ 第二路推断（如果人脸已经找到）
        if face_present and self._fer_session:
            try:
                gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
                if self._face_cascade is not None:
                    faces = self._face_cascade.detectMultiScale(gray, 1.1, 5)
                    for (fx, fy, fw, fh) in faces:
                        roi = gray[fy:fy + fh, fx:fx + fw]
                        resized = cv2.resize(roi, (64, 64))
                        normed = resized.astype(np.float32) / 255.0
                        out = self._fer_session.run(
                            None, {self._fer_input_name: normed[np.newaxis, np.newaxis, :, :]}
                        )[0][0]
                        FER_LABELS = ["neutral", "happiness", "surprise", "sadness",
                                      "anger", "disgust", "fear", "contempt"]
                        fer_idx = int(np.argmax(out))
                        if fer_idx < len(FER_LABELS):
                            # 用FER+ 推算时，只在confidence高于blendshape时才覆盖
                            fer_conf = float(out[fer_idx])
                            if fer_conf > expression_conf + 0.1:
                                expression = FER_LABELS[fer_idx]
                                expression_conf = fer_conf
                        break
            except Exception:
                pass

        return {
            "timestamp_ms": ts,
            "face_present": face_present,
            "expression": expression,
            "expression_conf": expression_conf,
            "gaze_x": gaze_x,
            "gaze_y": gaze_y,
            "head_pitch": head_pitch,
            "blendshapes": blendshapes,
        }

    def _process_loop(self) -> None:
        import cv2
        while self._running:
            ret, frame = self._cap.read()
            if not ret:
                time.sleep(0.03)
                continue

            ts = int(time.time() * 1000)

            # JPEG编码
            _, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            frame_b64 = base64.b64encode(jpeg).decode("utf-8")

            # 处理
            result = self.process_frame(frame)
            result["frame_b64"] = frame_b64

            # 更新状态
            with self._lock:
                self._latest_frame_b64 = frame_b64
                self._face_present = result["face_present"]
                self._latest_expression = result["expression"]
                self._latest_expression_conf = result["expression_conf"]
                self._gaze_x = result["gaze_x"]
                self._gaze_y = result["gaze_y"]
                self._head_pitch = result["head_pitch"]
                self._face_blendshapes = result.get("blendshapes", {})

            if self.on_result:
                try:
                    self.on_result(result)
                except Exception:
                    pass

    def analyze_base64(self, frame_b64: str) -> dict:
        """分析base64编码的单帧"""
        import cv2
        raw = base64.b64decode(frame_b64)
        arr = np.frombuffer(raw, dtype=np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if frame is None:
            return {"face_present": False, "expression": "neutral"}
        return self.process_frame(frame)
