"""身体姿态/动作检测服务 — MediaPipe PoseLandmarker (新版API)

新版 MediaPipe 0.10+ 使用 Tasks API:
  mp.tasks.vision.PoseLandmarker

分析维度:
  - 身体姿态 (33个关键点)
  - 身体活动度 (通过关键点运动计算唤醒度)
  - 坐姿/站姿检测
  - 弓背/塌腰等姿态问题
"""

from __future__ import annotations

import base64
import os
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any, Callable, Optional

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = PROJECT_ROOT / "models"
POSE_MODEL = MODELS_DIR / "mediapipe" / "pose_landmarker.task"


class BodyPoseService:
    """实时身体姿态分析"""

    LANDMARK_NAMES = [
        "nose", "left_eye_inner", "left_eye", "left_eye_outer",
        "right_eye_inner", "right_eye", "right_eye_outer",
        "left_ear", "right_ear", "mouth_left", "mouth_right",
        "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
        "left_wrist", "right_wrist", "left_pinky", "right_pinky",
        "left_index", "right_index", "left_thumb", "right_thumb",
        "left_hip", "right_hip", "left_knee", "right_knee",
        "left_ankle", "right_ankle", "left_heel", "right_heel",
        "left_foot_index", "right_foot_index",
    ]

    def __init__(self, camera_id: int = 0, width: int = 640, height: int = 480):
        self.camera_id = camera_id
        self.width = width
        self.height = height
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._cap = None

        # 状态
        self._lock = threading.Lock()
        self._latest_landmarks: list[dict] = []
        self._pose_detected = False
        self._posture_score = 0.5
        self._activity_level = 0.0
        self._gesture_intensity = 0.0
        self._is_sitting = False

        # 轨迹用于动作估计
        self._landmark_history: dict[int, deque] = {
            i: deque(maxlen=10) for i in range(33)
        }

        # 回调
        self.on_features: Optional[Callable[[dict], None]] = None

        # 模型
        self._pose_landmarker = None
        self._init_model()

    def _init_model(self) -> None:
        """初始化 MediaPipe PoseLandmarker (Tasks API) - 优雅降级"""
        if not POSE_MODEL.exists():
            print(f"[BodyPose] 模型不存在: {POSE_MODEL}")
            print(f"[BodyPose] 优雅降级: 姿态特征使用默认值 (0.5)")
            return  # 没有模型时跳过，不影响其他服务

        try:
            import mediapipe as mp
            from mediapipe.tasks import python
            from mediapipe.tasks.python import vision

            base_options = python.BaseOptions(model_asset_path=str(POSE_MODEL))
            options = vision.PoseLandmarkerOptions(
                base_options=base_options,
                num_poses=1,
                min_pose_detection_confidence=0.3,
                min_pose_presence_confidence=0.3,
                min_tracking_confidence=0.3,
                output_segmentation_masks=False,
            )
            self._pose_landmarker = vision.PoseLandmarker.create_from_options(options)
            print("[BodyPose] MediaPipe PoseLandmarker (Tasks API) 已加载")
        except Exception as e:
            print(f"[BodyPose] Pose 加载失败: {e}")
            print("[BodyPose] 优雅降级: 姿态特征使用默认值 (0.5)")

    def _auto_download_model(self) -> None:
        """下载 pose_landmarker.task 从 MediaPipe 官方源"""
        try:
            import urllib.request
            POSE_MODEL.parent.mkdir(parents=True, exist_ok=True)
            url = "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task"
            urllib.request.urlretrieve(url, str(POSE_MODEL))
            print(f"[BodyPose] 已下载: {POSE_MODEL}")
        except Exception as e:
            print(f"[BodyPose] 下载失败: {e}")

    def start(self) -> None:
        try:
            import cv2
        except ImportError:
            print("[BodyPose] cv2 not installed")
            return

        self._cap = cv2.VideoCapture(self.camera_id)
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self._cap.set(cv2.CAP_PROP_FPS, 10)

        self._running = True
        self._thread = threading.Thread(target=self._process_loop, daemon=True)
        self._thread.start()
        print(f"[BodyPose] Started (camera={self.camera_id})")

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        if self._cap:
            self._cap.release()
        print("[BodyPose] Stopped")

    @property
    def latest_features(self) -> dict:
        with self._lock:
            return {
                "pose_detected": self._pose_detected,
                "posture_score": self._posture_score,
                "activity_level": self._activity_level,
                "gesture_intensity": self._gesture_intensity,
                "is_sitting": self._is_sitting,
                "landmark_count": len(self._latest_landmarks),
            }

    def process_frame(self, frame_bgr) -> dict:
        """处理单帧，返回姿态特征"""
        import cv2
        ts = int(time.time() * 1000)
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)

        landmarks_dict = []
        pose_detected = False
        posture_score = 0.5
        activity_level = 0.0
        gesture_intensity = 0.0
        is_sitting = False

        if self._pose_landmarker:
            try:
                import mediapipe as mp
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                result = self._pose_landmarker.detect(mp_image)

                if result and result.pose_landmarks:
                    landmarks = result.pose_landmarks[0]
                    pose_detected = True
                    landmarks_dict = [
                        {
                            "name": self.LANDMARK_NAMES[i] if i < len(self.LANDMARK_NAMES) else f"lm_{i}",
                            "x": lm.x, "y": lm.y, "z": lm.z,
                            "visibility": lm.visibility,
                        }
                        for i, lm in enumerate(landmarks)
                    ]

                    # 更新轨迹
                    now = time.time()
                    for i, lm in enumerate(landmarks):
                        if i in self._landmark_history:
                            self._landmark_history[i].append({
                                "x": lm.x, "y": lm.y, "z": lm.z, "t": now
                            })
            except Exception:
                pass

        if pose_detected:
            posture_score = self._compute_posture_score(landmarks_dict)
            activity_level = self._compute_activity_level()
            gesture_intensity = self._compute_gesture_intensity()
            is_sitting = self._detect_sitting(landmarks_dict)

        with self._lock:
            self._latest_landmarks = landmarks_dict
            self._pose_detected = pose_detected
            self._posture_score = posture_score
            self._activity_level = activity_level
            self._gesture_intensity = gesture_intensity
            self._is_sitting = is_sitting

        return {
            "timestamp_ms": ts,
            "pose_detected": pose_detected,
            "posture_score": posture_score,
            "activity_level": activity_level,
            "gesture_intensity": gesture_intensity,
            "is_sitting": is_sitting,
            "landmarks": landmarks_dict,
        }

    def _process_loop(self) -> None:
        import cv2
        while self._running:
            ret, frame = self._cap.read()
            if not ret:
                time.sleep(0.03)
                continue
            result = self.process_frame(frame)
            if self.on_features:
                try:
                    self.on_features(result)
                except Exception:
                    pass

    def _compute_posture_score(self, landmarks: list[dict]) -> float:
        """姿态端正度 0-1"""
        try:
            l_shoulder = next(lm for lm in landmarks if lm["name"] == "left_shoulder")
            r_shoulder = next(lm for lm in landmarks if lm["name"] == "right_shoulder")
            l_hip = next(lm for lm in landmarks if lm["name"] == "left_hip")
            r_hip = next(lm for lm in landmarks if lm["name"] == "right_hip")
            nose = next(lm for lm in landmarks if lm["name"] == "nose")

            shoulder_tilt = abs(l_shoulder["y"] - r_shoulder["y"])
            shoulder_score = max(0, 1 - shoulder_tilt * 5)

            shoulder_mid_x = (l_shoulder["x"] + r_shoulder["x"]) / 2
            hip_mid_x = (l_hip["x"] + r_hip["x"]) / 2
            torso_dx = abs(shoulder_mid_x - hip_mid_x)
            torso_score = max(0, 1 - torso_dx * 4)

            nose_forward = (nose["z"] < -0.05)
            posture_score = shoulder_score * 0.4 + torso_score * 0.4 + (0 if nose_forward else 1) * 0.2
            return max(0.0, min(1.0, posture_score))
        except Exception:
            return 0.5

    def _compute_activity_level(self) -> float:
        """通过关键点速度估计活动水平"""
        velocities = []
        for idx, history in self._landmark_history.items():
            if len(history) < 2:
                continue
            if idx not in [0, 11, 12, 23, 24]:  # nose, shoulders, hips
                continue
            history_list = list(history)
            p1, p2 = history_list[-2], history_list[-1]
            dt = max(p2["t"] - p1["t"], 1e-3)
            v = np.sqrt((p2["x"] - p1["x"]) ** 2 + (p2["y"] - p1["y"]) ** 2) / dt
            velocities.append(v)

        if not velocities:
            return 0.0
        avg_v = float(np.mean(velocities))
        return min(1.0, avg_v * 5)

    def _compute_gesture_intensity(self) -> float:
        """手势/上肢运动强度"""
        hand_points = [15, 16, 17, 18, 19, 20]
        motion = []
        for idx in hand_points:
            if idx not in self._landmark_history:
                continue
            history_list = list(self._landmark_history[idx])
            if len(history_list) < 2:
                continue
            dx = sum(abs(history_list[i]["x"] - history_list[i-1]["x"]) for i in range(-5, 0))
            motion.append(dx)
        if not motion:
            return 0.0
        avg_motion = float(np.mean(motion))
        return min(1.0, avg_motion * 10)

    def _detect_sitting(self, landmarks: list[dict]) -> bool:
        """简单坐姿检测: hip y > 0.55"""
        try:
            l_hip = next(lm for lm in landmarks if lm["name"] == "left_hip")
            r_hip = next(lm for lm in landmarks if lm["name"] == "right_hip")
            hip_y = (l_hip["y"] + r_hip["y"]) / 2
            return hip_y > 0.55
        except Exception:
            return False

    def analyze_base64(self, frame_b64: str) -> dict:
        import cv2
        raw = base64.b64decode(frame_b64)
        arr = np.frombuffer(raw, dtype=np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if frame is None:
            return {"pose_detected": False}
        return self.process_frame(frame)
