# Aociety-NEW — 完整情感AI虚拟世界 (升级版)

## 🎯 全栈功能

```
UE5 ←→ Python Backend (端口 8000) ←→ GLM 5.2 云端 (tokenhub.market)
                              ↓
                          本地模型
                              ├── MediaPipe Face + FER+ 表情识别
                              ├── MediaPipe Pose 姿态动作 (33关键点)
                              ├── SenseVoice (阿里达摩院) ASR
                              └── Edge TTS (微软) 甜女声
```

---

## 🚀 启动

### 基础启动
```powershell
uvicorn backend.main:app --reload --port 8000
```

### 完整启动 (后端 + 摄像头 + 麦克风 + ASR)
```powershell
.\start_full.bat
```

### 仅情感计算管线 (摄像/麦克风)
```powershell
python -m services.emotion_pipeline --backend http://127.0.0.1:8000
```

---

## 📦 已部署的本地模型

| 模型 | 来源 | 用途 | 大小 |
|------|------|------|------|
| **GLM 5.2** | 智谱AI (中转) | 主对话 / 情感推理 | 云端 |
| **SenseVoice-Small** | 阿里达摩院 (ModelScope) | 多语种 ASR + 情感识别 | ~900MB |
| **FER+ ONNX** | Microsoft | 表情识别 (8 类) | ~10MB |
| **MediaPipe Face Landmark** | Google | 人脸关键点 + 视线 + 姿态 | ~3MB |
| **MediaPipe Pose** | Google | 身体姿态33点 + 动作分析 | ~3MB |
| **Edge TTS** | Microsoft | 甜女声 (晓晓/晓伊/...) | 云端 |

---

## 🎤 甜女声

通过 `GET /tts/voices` 列出所有：

| ID | 中文名 | 描述 |
|----|--------|------|
| `xiaoxiao` | 晓晓 | **甜、温暖、年轻** ★推荐 |
| `xiaoyi` | 晓伊 | 温暖、自然 |
| `xiaomeng` | 晓梦 | 可爱、清新 |
| `xiaomo` | 晓墨 | 文艺、柔和 |
| `xiaoxuan` | 晓萱 | 温润 |

切换：
```bash
POST /tts/voices/xiaoxiao
```

合成：
```bash
POST /tts/synthesize  {"text": "主人，要不要起来活动活动？", "voice": "xiaoxiao"}
```

UE5 集成见 `docs/UE5_INTEGRATION.md` 和 `docs/*.cpp/.h`。

---

## 🎮 UE5.8 对接

完整 C++ 实现见：
- `docs/AocietyClientSubsystem.h/.cpp` — 主客户端
- `docs/CameraCaptureComponent.h/.cpp` — 摄像头
- `docs/MicCaptureComponent.h/.cpp` — 麦克风
- `docs/TTSPlayer.h/.cpp` — 甜女声播放器

集成步骤：
1. 创建 `Source/Aociety/` 模块
2. 把上述 .h/.cpp 文件复制到对应目录
3. `Build.cs` 加上 `HTTP`, `Json`, `JsonUtilities`, `WebSockets`
4. GameInstance 上拿到 `UAocietyClientSubsystem` 引用
5. BeginPlay 时调用 `Connect()` + `StartCapture()`

详细 API、蓝图示例、UMG 蓝图在 `docs/UE5_INTEGRATION.md`。

---

## 📊 情感计算管线工作流

```
笔记本摄像头 ─┐
              ├─→  VisionService ─→ MediaPipe Face/FER+  ──┐
SenseVoice ASR ┼→  AudioService ─→ funasr SenseVoice     ─┼→ Backend  ─→  GLM 5.2
笔记本麦克风 ─┘                  ─→ VAD                  ─┘     │          情感推理
                                                                  │    AffectRuntime 融合
笔记本摄像头 ─→  BodyPoseService ─→ MediaPipe Pose            ──→│    output → 数值
              (33关键点、姿态、活动、手势、坐/站)                  ┘
                                                                  │
                                                                  ↓
                                                            主动关怀触发
                                                                  │
                                                                  ↓
                                                                TTS 甜女声
                                                                  │
                                                                  ↓
                                                            UE5 NPC 关怀动画/对话
                                                            （由UE5客户端接收）
```

---

## 🧪 端到端测试

### 1. 启动后端
```bash
cd E:/Aociety-NEW
uvicorn backend.main:app --reload --port 8000
```

### 2. 健康检查
```bash
curl http://127.0.0.1:8000/health
```

### 3. 多模态测试
```bash
# 纯文本
curl -X POST http://127.0.0.1:8000/emotion/analyze \
  -H "Content-Type: application/json" \
  -d "{\"text_hint\":\"今天好累啊\"}"

# 当前情感状态
curl http://127.0.0.1:8000/emotion/state

# TTS 甜女声
curl -X POST http://127.0.0.1:8000/tts/synthesize \
  -H "Content-Type: application/json" \
  -d "{\"text\":\"主人，看你脸色不太好\"\",\"voice\":\"xiaoxiao\"}"
```

### 4. 全管线测试
```bash
python -m services.emotion_pipeline --backend http://127.0.0.1:8000
```
然后对着麦克风说话，看到情绪分析结果。

---

## 📁 目录

```
E:/Aociety-NEW/
├── backend/                # FastAPI 后端
│   ├── main.py             # 主服务 (8000)
│   ├── glm_adapter.py      # GLM 5.2 情感适配器
│   ├── affect_runtime.py   # 情感运行时
│   ├── assessment_engine.py
│   └── ...
├── services/               # 业务服务
│   ├── engine.py           # WorldEngine (36 NPC)
│   ├── ark_client.py       # GLM 5.2 客户端 (Ark)
│   ├── vision_service.py   # 摄像头+表情+姿态 → 情感特征
│   ├── audio_service.py    # 麦克风+ASR → 文本
│   ├── body_pose_service.py # 身体姿态/动作 (MediaPipe Pose)
│   ├── emotion_pipeline.py # 全管线协调器
│   ├── tts_service.py      # 甜女声 TTS (Edge TTS)
│   ├── r1_omni_server.py   # 本地 R1-Omni 模型服务
│   └── arousal_server.py   # 本地 Arousal 服务
├── engine/                 # 情感计算核心引擎 (旧)
├── models/                 # 本地模型
│   ├── ferplus/            # 表情 ONNX
│   ├── mediapipe/          # Face Landmarker
│   ├── asr/
│   │   ├── sensevoice/     # 阿里 SenseVoice (ModelScope)
│   │   └── sherpa/         # sherpa-onnx paraformer 备选
│   └── tts/                # 甜女声模型位置
├── docs/                   # 文档
│   ├── API_UE5.md          # REST/WebSocket API
│   ├── UE5_INTEGRATION.md  # 完整集成指南
│   ├── AocietyClientSubsystem.{h,cpp}  # UE5 C++ 类
│   ├── CameraCaptureComponent.{h,cpp}
│   ├── MicCaptureComponent.{h,cpp}
│   └── TTSPlayer.{h,cpp}
├── data/                   # 游戏世界 JSON 数据
├── scripts/                # 工具脚本
├── .env                    # 环境变量 (含GLM 5.2 API key)
├── start_full.bat          # 一键全启动
└── README.md
```

---

## 📝 关键环境变量 (.env)

```
ANTHROPIC_API_KEY=mk_7DJ8D9XH4G9DNXRQKA279UPTZ72XG92W
OPENAI_API_KEY=...
GLM_BASE_URL=https://api.tokenhub.market/v1
GLM_MODEL_ID=glm-5.2
TTS_VOICE=xiaoxiao
AOCIETY_PORT=8000
ENABLE_EMOTION=1
```

---

## 状态统计 (2026-07-10)

- ✅ **AI 部分**：GLM 5.2 替代豆包/Qwen-Omni，配置完成 ✓
- ✅ **情感计算引擎**：全栈迁移 ✓
- ✅ **用户性格评估**：8 维评估 ✓
- ✅ **每日总结**：从 lunwen 迁移 ✓
- ✅ **OpenClaw 记忆**：从 lunwen 迁移 ✓
- ✅ **动作/姿态**：MediaPipe Pose 集成 ✓
- ✅ **顶级 ASR**：阿里 SenseVoice (多语种+情感识别) ✓
- ✅ **甜女声 TTS**：晓晓 (默认) + 6 个甜女声备选 ✓
- ✅ **摄像头采集**：本地 + UE5 双实现 ✓
- ✅ **麦克风采集**：本地 + UE5 双实现 ✓
- ✅ **UE5 对接**：完整 C++ 类 + Blueprint 指南 ✓

---

## 待办 (下一步)

- [ ] UE5 项目集成测试
- [ ] 性能调优（GLM 5.2 调用延迟）
- [ ] 对 CosyVoice 本地部署（极致离线体验）
- [ ] 多人模式（多玩家共享绿洲世界）

---

## 问题排查

| 现象 | 原因 | 解决 |
|------|------|------|
| emotion返回degraded | GLM API 鉴权/超时 | 检查 ANTHROPIC_API_KEY；等待预热 |
| 摄像头不工作 | 权限/占用 | 关闭其他占用摄像头的程序 |
| 麦克风没声音 | Windows隐私设置 | 设置→麦克风→允许应用访问 |
| 甜女声没声音 | edge-tts 联网失败 | 检查网络/使用pyttsx3离线 |
| UE5 WebSocket 断 | 未实现重连 | 已加自动重连5s |
