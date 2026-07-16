# Aociety — 完整项目交接书

> **项目全称**: Aociety（绿洲虚拟世界 × 主动式情感AI游戏）
> 
> **交接日期**: 2026-07-10 → 2026-07-11
>
> **开发者**: Claude Code (基于 GLM 5.2 辅助生成)
>
> **项目主页**: `E:/Aociety-NEW/README.md`

---

# 第一部分：项目全景

## 这是做什么的？

### 🎮 游戏愿景

《Aociety》是一个受《头号玩家》"绿洲"(OASIS) 启发的 2D 开放世界社会经济模拟游戏 + **主动式情感AI陪伴系统**。

> **一句话**: 玩家在虚拟世界中与 36 个 AI NPC 互动，游戏通过摄像头+麦克风实时感知玩家情绪，NPC 会像"有温度的人"一样主动关怀。

### 👾 游戏世界设定

- **世界观**: 一个类似赛博朋克/封建城邦的虚构城市，分为4个街区
- **街区**:
  - **贫民街** (Slum) — 底层劳工聚集地，农坡地、鱼市前街、野径
  - **港口** (Dock) — 运河码头、船坞工坊、石桥街口
  - **工厂区** (Factory) — 磨坊前院、石料工地、矿砾区
  - **交易所** (Exchange) — 塔楼会客厅、钟楼市集、教堂墓园
- **经济系统**: 商品经济（面包、煤、罐头）+ 股票市场（海藻重工、市政债券、龟甲物流）+ 家族势力（海藻资本、镇政府、龟甲家族）
- **NPC**: 36 个具有独立身份、社会阶层、关系记忆、经济行为、情感状态的 AI 角色
- **时间系统**: 早/中/晚 时段循环，第1天起始于 8:00

### 🎯 情感AI的核心创新

本项目不是普通的情感识别，而是**主动式情绪关怀**：

```
摄像头/麦克风 → SenseVoice + FER+ + MediaPipe
       ↓
  情绪推断 (GLM 5.2)
       ↓
  AffectRuntime 融合趋势/效价/唤醒度
       ↓
  CarePolicy 判断"是否该关怀+如何关怀"
       ↓
  NPC产生关怀互动 + TTS甜女声(晓晓)
```

**谁爱了你？** 游戏里的 NPC。当情绪不佳时，NPC 会说出 "看你脸色不太好，今天是不是太拼了？" 并做出关怀动作。

## 情感类型覆盖

| 情感 | 效价范围 | 唤醒度范围 | NPC反应 |
|------|---------|----------|---------|
| **joy** 快乐 | 0.8-1.0 | 0.6-0.9 | 不干预或积极共情 |
| **sadness** 悲伤 | 0.1-0.3 | 0.5-0.8 | nudge / care 级关怀 |
| **anger** 愤怒 | 0.0-0.2 | 0.7-1.0 | care 级高主动 |
| **anxiety** 焦虑 | 0.1-0.3 | 0.6-0.9 | nudge / care 级 |
| **frustration** 沮丧 | 0.1-0.3 | 0.5-0.8 | nudge 级 |
| **surprise** 惊讶 | 0.4-0.8 | 0.6-1.0 | 视正负决定 |
| **neutral** 中性 | 0.45-0.55 | 0.0-0.3 | 不干预 |

## 项目位置

| 目录 | 内容 | 大小 |
|------|------|------|
| `E:/Aociety-NEW/` | Python后端 + 游戏数据 + 模型 + 文档 | 1.1 GB |
| `E:/Aociety-NEW/ue5_project/` | UE5.8 C++ 项目模板 | 92 KB |
| `E:/Aociety-NEW/backend/` | FastAPI 后端 (18个模块) | 526 KB |
| `E:/Aociety-NEW/services/` | 游戏服务 (6个模块, 含13K行 WorldEngine) | 2.2 MB |
| `E:/Aociety-NEW/engine/` | 情感计算引擎 (17个模块) | 1.1 MB |
| `E:/Aociety-NEW/models/` | 本地模型 (SenseVoice 900MB, FER+, MediaPipe) | 约 1 GB |

---

# 第二部分：游戏到底长什么样

## 当前可运行状态

你现在就能在命令行看到效果——虽然还没有图形界面。

### 在终端看到的"游戏世界"

```bash
curl http://127.0.0.1:8000/world/state | python -c "import sys,json; 
d=json.load(sys.stdin)['world_state'];
print(f'第{d[\"day\"]}天 {d[\"time_period\"]}');
for n in d['npcs'][:5]:
  print(f'  {n[\"name\"]} ({n[\"district\"]}) - {n[\"mood\"]} - {n[\"activity\"]}');
print(f'...{len(d[\"npcs\"])} NPCs total')"
```

输出类似:
```
第1天 早晨
  老陈 (贫民街) - wary - working
  阿德 (贫民街) - wary - working
  瘦猴 (贫民街) - neutral - working
  码头老赵 (港口) - neutral - working
  跛脚林 (港口) - neutral - panhandling
...36 NPCs total
```

### 游戏地图 (Godot 时代)
旧版游戏在 Godot 4.5 中有一个可玩的 2D 地图：
```
E:/Desktop/gamexu/  ← 原Godot项目（已不再主开发）
```
新项目使用 UE5.8 重建，地图数据在 `E:/Aociety-NEW/data/` 中。

### 游戏交互流程
```
1. 打开UE5客户端 → 连接后端 → 看到俯视地图
2. NPC在街区间走动，显示名字/状态
3. 玩家控制角色 → 靠近NPC → 按E对话
4. NPC通过GLM 5.2生成个性对话回复
5. 后台情感计算持续运行:
   摄像头 → 表情 → 情绪分析
   麦克风 → ASR转写 → 文本→情绪分析
6. 检测到情感低落 → NPC主动走向玩家 → 输出关怀对话
7. 玩家情绪回升 → NPC返回常规行为
```

### 现状: 能做什么不能做什么

| 功能 | 状态 | 说明 |
|------|:----:|------|
| 后端服务 | ✅ 完成 | FastAPI, 29个路由, 可运行 |
| GLM 5.2 情感推理 | ✅ 完成 | tokenhub.market 中转 |
| 世界引擎 (36 NPC) | ✅ 完成 | 经济/社交/记忆系统 |
| NPC对话 | ✅ 完成 | GLM 5.2 驱动 |
| 主动式NPC关怀 | ✅ 完成 | 规则+GLM双模 |
| 8维性格评估 | ✅ 完成 | 对话式MBTI |
| SenseVoice ASR | ✅ 完成 | 中文+情感标签 |
| FER+表情分析 | ✅ 完成 | ONNX本地推理 |
| MediaPipe FaceLandmarker | ✅ 完成 | 人脸网格478点 |
| MediaPipe PoseLandmarker | ✅ 完成 | 身体33关键点 |
| Edge TTS甜女声 | ✅ 完成 | 晓晓/晓伊/晓梦等8种 |
| 每日总结 | ⚠️ 代码迁移 | engine/summary/ 已迁移 |
| OpenClaw记忆 | ⚠️ 简易内存存储 | 完整版需OpenClaw运行时 |
| UE5.8 图形客户端 | 🔧 模板完成 | 待你打开项目编译 |
| 实时摄像头采集 | 🔧 服务完成 | 需真实UE5客户端驱动 |
| 实时麦克风采集 | 🔧 服务完成 | 需真实UE5客户端驱动 |

---

# 第三部分：项目全景架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        UNREAL ENGINE 5.8                        │
│                                                                 │
│   AocietyClientSubsystem  ← WebSocket ←→ Backend (8000)        │
│   ├─ PushCameraFrame()    → POST /emotion/analyze              │
│   ├─ PushAudioChunk()     → POST /emotion/analyze              │
│   ├─ PushTextHint()       → POST /emotion/analyze              │
│   ├─ RequestNPCCare()     → POST /emotion/care                 │
│   ├─ OnEmotionUpdated     ← 状态变化时触发                     │
│   ├─ OnCareTriggered      ← NPC主动关怀时触发                   │
│   └─ OnTTSReady           ← TTS音频就绪时触发                   │
│                                                                 │
│   CameraCaptureComponent  ← USB摄像头                           │
│   MicCaptureComponent     ← 内置麦克风                          │
│   TTSPlayer               ← 播放甜女声MP3                       │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTP / WebSocket
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                   PYTHON BACKEND (端口 8000)                    │
│                                                                 │
│   ┌──────────────────────────────────────────────────────┐      │
│   │  FastAPI 后端 (backend/main.py)                      │      │
│   │                                                      │      │
│   │  情感端点                   世界/经济端点              │      │
│   │  POST /emotion/analyze      GET  /world/state        │      │
│   │  GET  /emotion/state        POST /world/action       │      │
│   │  POST /emotion/care         POST /ai/pulse           │      │
│   │  POST /emotion/reset        POST /world/end_day      │      │
│   │  WS   /ws/emotion           POST /world/reset        │      │
│   │                              POST /npc/player_talk   │      │
│   │  TTS端点                    POST /npc/conversation   │      │
│   │  GET  /tts/voices           GET  /npc/list           │      │
│   │  POST /tts/voices/{name}    GET  /npc/{id}           │      │
│   │  POST /tts/synthesize                                 │      │
│   │                             评估端点                  │      │
│   │ 记忆端点                    POST /assessment/start    │      │
│   │  GET  /memory/search        POST /assessment/turn     │      │
│   │  POST /memory/store         GET  /assessment/state/id │      │
│   │                              POST /assessment/finish  │      │
│   └──────────────────────────────────────────────────────┘      │
│                                                                 │
│    ┌──────┐ ┌──────┐ ┌──────┐ ┌──────────┐ ┌───────┐          │
│    │Vision│ │Audio │ │Pose  │ │  Engine   │ │ TTS   │          │
│    │Service│ │Service│ │Service│ │Controller│ │Service│          │
│    └──┬───┘ └──┬───┘ └──┬───┘ └────┬─────┘ └──┬────┘          │
│       │        │        │          │          │                │
│    FER+     SenseVoice MediaPipe  Emotion    Edge TTS          │
│    ONNX     ASR       Pose       Engine     (晓晓)             │
│    MediaPipe                    ├─VAD/ASR                      │
│    FaceLandmark                 ├─Gesture                      │
│                                 └─CarePolicy                   │
└─────────────────────────────────────────────────────────────────┘
```

# 第四部分：文件结构（每个文件都说明）

## 4.1 项目根目录

```
E:/Aociety-NEW/
├── .env                          ← 环境变量 (API Key, 端口, 开关)
├── .env.example                  ← 环境变量模板
├── requirements.txt              ← Python依赖清单
├── README.md                     ← 项目主页 (218行)
├── HANDOVER.md                   ← 本文档
├── start_full.bat                ← Windows一键启动 (后端+摄像头+麦克风)
├── start_backend.bat             ← Windows启动后端(无管线)
└── data/                         ← 世界引擎数据文件
    ├── npcs.json                 ← 36 NPC定义 (身份/阶层/行为/位置)
    ├── goods.json                ← 商品定义 (面包/煤/罐头)
    ├── stocks.json               ← 股票定义 (3只)
    ├── families.json             ← 家族势力 (海藻资本/镇政府/龟甲家族)
    ├── companies.json            ← 公司
    ├── events.json               ← 随机事件
    ├── macro.json                ← 宏观状态
    ├── districts.json            ← 街区地理
    ├── residences.json           ← 住宅定义
    ├── dialogue_templates.json   ← NPC对话模板
    ├── npc_prompt_profiles.json  ← NPC性格提示词
    ├── npc_path_plans.json       ← NPC路径规划
    ├── demo_flow.json            ← 演示流程
    ├── tasks.json                ← 任务定义
    ├── story_overrides.generated.json  ← 故事线改写
    └── poi_slots.json            ← 兴趣点插槽
```

## 4.2 backend/ — FastAPI 后端 (核心业务层)

| 文件 | 行数 | 作用 |
|------|------|------|
| `main.py` | ~250 | **★ 主服务** 29个路由: 情感/世界/评估/记忆/TTS/WebSocket |
| `glm_adapter.py` | ~350 | **★ GLM 5.2适配器** — 替换Qwen3-Omni，调用tokenhub.market anthropic API |
| `affect_runtime.py` | ~440 | **★ 情感运行时** — 多模态融合、趋势分析、支持需求计算 |
| `assessment_engine.py` | ~600 | **★ 8维性格评估引擎** — 对话式MBTI (Fe/Fi/Ni/Ne/Te/Ti/Se/Si) |
| `assessment_prompts.py` | ~80 | 评估对话的提示词模板 |
| `assistant_service.py` | ~1300 | AI助手服务 (情绪关怀对话) |
| `assistant_store.py` | ~580 | 助手状态存储 |
| `care_prompts.py` | ~60 | 关怀响应提示词 |
| `personality_prompts.py` | ~50 | 人格分析提示词 |
| `activation_prompts.py` | ~60 | 激活流程提示词 |
| `openclaw_gateway.py` | ~320 | OpenClaw记忆系统网关 |
| `schemas.py` | ~400 | Pydantic 数据模型 (请求/响应) |
| `settings.py` | ~150 | 配置管理 (环境变量读取) |
| `auth.py` | ~40 | 基础认证 |
| `db.py` | ~450 | 数据库管理 |
| `desktop_speech.py` | ~350 | 桌面端语音处理 |

## 4.3 services/ — 游戏世界 + 采集管线

| 文件 | 行数 | 作用 |
|------|------|------|
| `engine.py` | **13,751** | **★★ WorldEngine** — 世界引擎本体 (经济/社交/NPC/新闻/股票/家族) |
| `ark_client.py` | ~1,100 | **★★ GLM 5.2 对话客户端** — NPC对话/新闻/脉冲/简报生成 (原豆包 → GLM) |
| `app.py` | ~200 | 游戏世界 FastAPI 子服务 (备选, 已合并到 backend/main.py) |
| `vision_service.py` | ~200 | **摄像头 + MediaPipe FaceLandmarker + FER+ 表情识别** (新版Tasks API) |
| `audio_service.py` | ~230 | **麦克风 + SenseVoice ASR + 声学特征** (阿里达摩院) |
| `body_pose_service.py` | ~250 | **身体姿态/动作检测** — MediaPipe Pose 33关键点 (新版Tasks API) |
| `emotion_pipeline.py` | ~150 | **★ 全管线协调** — 启动所有采集器, 数据汇聚后端 |
| `r1_omni_server.py` | ~100 | R1-Omni-0.5B 情感推理服务 (端口8001, 规则回退存根) |
| `arousal_server.py` | ~110 | Arousal 唤醒度服务 (端口8002, 规则回退存根) |
| `npc_story_overrides.py` | ~20 | NPC 故事线改写 |
| `tts_service.py` | ~150 | **Edge TTS 甜女声服务** (晓晓/晓伊/晓梦/晓墨/晓萱等8种) |

## 4.4 engine/ — 情感计算引擎 (迁移自lunwen项目)

| 文件 | 作用 |
|------|------|
| **core/** | 引擎核心 |
| `__init__.py` | 模块入口 |
| `clock.py` | 高精度时钟 |
| `config.py` | **★ 完整配置** (11个配置类: Video/Audio/Trigger/Fusion/Asr/Wake/Llml/Runtime/FaceTracking/Policy/Summary) |
| `engine_controller.py` | **★ EmotionEngine** 引擎控制器 (~1000行) |
| `event_bus.py` | 事件总线 |
| `types.py` | 数据类型 (AudioFrame/VideoFrame/CarePlan等) |
| **vision/** | 视觉模块 |
| `face_detector.py` | MediaPipe 人脸检测 |
| `face_tracker.py` | 人脸追踪 |
| `face_roi.py` | 人脸ROI提取 |
| `expression_classifier.py` | FER+ ONNX 表情分类 |
| `expression_mediapipe.py` | MediaPipe 表情检测 |
| `vision_risk.py` | 视觉风险评分 (疲劳/注意力/表情/视线) |
| `vision_types.py` | 视觉数据类型 |
| `frame_decode.py` | 帧解码工具 |
| **audio/** | 音频模块 |
| `acoustic_features.py` | 声学特征提取 |
| `acoustic_risk.py` | 声学风险评分 |
| `vad.py` | 语音活动检测 |
| `ring_buffer.py` | 音频环形缓冲区 |
| **nlp/** | 自然语言模块 |
| `asr_module.py` | ASR 转写模块 (sherpa-onnx/Vosk) |
| `alibaba_local.py` | 阿里本地ASR (备选) |
| `sherpa_kws.py` | 关键词唤醒 |
| `text_risk.py` | 文本风险评分 |
| `wake_word.py` | 唤醒词检测 |
| `lexicon_zh.txt` | 中文情感词典 |
| **trigger/** | 触发管理 |
| `fusion_scorer.py` | V+A+T 融合评分 (含人格调制) |
| `trigger_manager.py` | 关怀触发管理器 |
| **policy/** | 关怀策略 |
| `care_policy.py` | **★ 关怀策略** — LLM时机判断 + 规则引擎 |
| `llm_timing_confirm.py` | LLM关怀时机确认 |
| `timing_logger.py` | 时机日志 |
| `templates_zh.json` | 关怀模板 |
| **llm/** | LLM接口 |
| `llm_responder.py` | LLM响应器 (~1000行, 备用) |
| `prompts/` | 提示词目录 |
| **summary/** | 每日总结 |
| `daily_summarizer.py` | 每日总结生成器 |
| **comm/** | 通信 |
| `command_sender.py` | 命令发送 |
| **ingest/** | 数据注入 |
| `audio_ingestor.py` | 音频数据注入 |
| `video_ingestor.py` | 视频数据注入 |
| **tests/** | 测试 |

## 4.5 models/ — 本地模型

| 文件 | 大小 | 来源 |
|------|------|------|
| `models/ferplus/emotion-ferplus-8.onnx` | 10 MB | ONNX模型库 |
| `models/mediapipe/face_landmarker.task` | 4 MB | Google MediaPipe |
| `models/mediapipe/pose_landmarker.task` | 5.6 MB | Google MediaPipe |
| `models/asr/sherpa/sherpa-onnx-paraformer-zh-small-2024-03-09/model.int8.onnx` | 50 MB | sherpa-onnx |
| `models/asr/sensevoice_cache/iic/SenseVoiceSmall/model.pt` | 880 MB | ModelScope/阿里达摩院 |
| `models/tts/zh_CN-huayan-medium.onnx` | 30 MB | Piper TTS (备用) |
| `models/kws/` | 15 MB | 关键词唤醒模型 |

## 4.6 ue5_project/ — UE5.8 C++ 项目模板

| 文件 | 作用 |
|------|------|
| `Aociety.uproject` | ★ 项目文件 (引擎5.8, 依赖HTTP/Json/WebSockets) |
| `Source/Aociety/Aociety.Build.cs` | ★ 模块依赖配置 |
| `Source/Aociety.Target.cs` | 打包目标配置 |
| `Source/AocietyEditor.Target.cs` | 编辑器目标 |
| **Public/** | 头文件 |
| `Public/Aociety.h` | 模块入口 |
| `Public/AocietyClientSubsystem.h` | **★ 核心客户端** — HTTP+WS + 事件分发 |
| `Public/AocietyGameInstance.h` | 游戏实例 (自动启动连接) |
| `Public/AocietyGameMode.h` | 游戏模式 |
| `Public/CameraCaptureComponent.h` | **摄像头采集** (UE的MediaCapture或OpenCV) |
| `Public/MicCaptureComponent.h` | **麦克风采集** (UE的AudioCapture) |
| `Public/TTSPlayer.h` | **甜女声播放器** (下载MP3并播放) |
| **Private/** | 实现文件 |
| `Private/Aociety.cpp` | 模块初始化 |
| `Private/AocietyClientSubsystem.cpp` | **★ ~500行** WebSocket连接 + 情绪事件 + 关怀请求 |
| `Private/AocietyGameInstance.cpp` | 游戏实例实现 |
| `Private/AocietyGameMode.cpp` | 游戏模式实现 |
| `Private/CameraCaptureComponent.cpp` | 摄像头帧编码发送 |
| `Private/MicCaptureComponent.cpp` | 麦克风PCM16发送 |
| `Private/TTSPlayer.cpp` | 甜女声MP3解码播放 |
| `Source/README.md` | 模块说明 |
| **Config/** | 项目配置 |
| `Config/DefaultEngine.ini` | 引擎配置 (渲染/物理/碰撞) |
| `Config/DefaultGame.ini` | 游戏配置 (地图/后端URL/TTS) |
| `Config/DefaultEditor.ini` | 编辑器配置 |
| `Config/DefaultAociety.ini` | **★ Aociety特有配置** (后端URL/关怀阈值/帧率) |
| `UE5_BUILD_GUIDE.md` | UE5编译运行指南 |
| `Content/` | UE资产目录 (空, 待填充) |

## 4.7 docs/ — 文档

| 文件 | 行数 | 内容 |
|------|------|------|
| `docs/API_UE5.md` | **510** | **★ UE5 API对接完整文档 !** (所有端点+请求/响应+蓝图事件) |
| `docs/UE5_INTEGRATION.md` | **487** | **★ UE5集成完整指南** (蓝图函数库+事件调度+Widget) |
| `docs/AocietyClientSubsystem.h` | ~200 | C++ 头文件 (核心客户端) |
| `docs/AocietyClientSubsystem.cpp` | ~300 | C++ 实现 (WebSocket+心跳) |
| `docs/CameraCaptureComponent.h/cpp` | ~100/150 | C++ 摄像头组件 |
| `docs/MicCaptureComponent.h/cpp` | ~100/130 | C++ 麦克风组件 |
| `docs/TTSPlayer.h/cpp` | ~80/100 | C++ TTS音频播放 |
| `docs/API_UE5.md` | 510 | UE5 API文档 |

---

# 第五部分：核心API一览

## 情感API

```
POST /emotion/analyze
  → {"image_base64":"...","audio_base64":"...","text_hint":"今天好累"}
  ← {"emotion":"sadness","valence":0.23,"arousal":0.67,"support_need":0.72,"trend":{...}}

GET /emotion/state
  ← {"emotion":"frustration","valence":0.2,"arousal":0.7,"trend":{...}}

POST /emotion/care
  → {"npc_id":"npc_01"}
  ← {"npc_line":"看你脸色不太好...","action":"speak_kindly","care_level":"care"}

WS /ws/emotion
  → {"image_base64":"...","audio_base64":"..."}
  ← {"emotion":"joy","valence":0.9,...}

POST /emotion/reset → {"status":"ok"}
```

## TTS API

```
GET /tts/voices
  ← {"voices":[...], "current":"xiaoxiao"}

POST /tts/voices/xiaomeng → {"current":"xiaomeng","name":"晓梦"}

POST /tts/synthesize
  → {"text":"好好休息","voice":"xiaoxiao"}
  ← {"audio_base64":"SUQz...","voice":"xiaoxiao","voice_name_cn":"晓晓","duration_estimate":2.5}
```

## 世界/NPC API

```
GET /world/state → {"world_state":{"day":1,"npcs":[...],"goods":[...],"stocks":[...]}}
POST /world/action → {"action_type":"work","district":"贫民街","payload":{}}
POST /npc/player_talk → {"npc_id":"npc_01","player_input":"最近生意怎么样？"}
                        ← {"dialogue":{"npc_line":"...","stance":"wary"}}
GET /npc/list → {"npcs":[...]}
GET /npc/{id} → {"npc":{"id":"npc_01","name":"老陈",...}}
```

## 评估 API

```
POST /assessment/start → {"session_id":"...","message":"评估已开始"}
POST /assessment/turn → {"session_id":"...","player_input":"我喜欢...","finished":false}
POST /assessment/finish/{id} → {"profile":{"Fe":0.7,"Fi":0.5,...}}
```

## 记忆 API

```
GET /memory/search?query=今天&limit=10 → {"results":[...]}
POST /memory/store → {"key":"...","value":"...","tags":["..."]}
```

---

# 第六部分：模型详情

## 模型加载优先级

### ASR (音频→文字)
```
1. sherpa-onnx SenseVoice (ONNX) ← 最快，但 ONNX 版本需要额外下载
2. FunASR SenseVoiceSmall (PyTorch) ☆ 当前在用，880MB本地模型
3. sherpa-onnx Paraformer (备选)
```
当前使用: **FunASR SenseVoiceSmall** — 中文/WER < 3%, 内置情感识别

### 表情识别 (视频→表情)
```
FER+ ONNX (emotion-ferplus-8.onnx)
  - 8类: neutral, happiness, surprise, sadness, anger, disgust, fear, contempt
  - 64x64 输入, 单次推理 ~5ms

MediaPipe FaceLandmarker (478个面部关键点)
  - 视线追踪 (x/y)
  - 头部姿态
  - Blendshapes (52个面部运动单元)
  - 辅助表情判断
```

### 姿态识别 (视频→身体)
```
MediaPipe PoseLandmarker (33个关键点)
  - 身体姿态端正度 (肩膀水平度/躯干角度/弓背检测)
  - 活动水平 (关键点运动速度)
  - 手势强度 (手腕/手指运动幅度)
  - 坐姿/站姿
```

### TTS (文字→甜女声)
```
Edge TTS (微软云服务):
  xiaoxiao (晓晓)  - 甜、温暖、年轻 ★ 默认 ★
  xiaoyi   (晓伊)  - 温暖、自然
  xiaomeng (晓梦)  - 可爱、清新  
  xiaomo   (晓墨)  - 文艺、柔和
  xiaoxuan (晓萱)  - 温润
  xiaoran  (晓然)  - 自然柔和
  xiaohan  (晓涵)  - 温和
  xiang    (晓昂)  - 活力

离线备选: pyttsx3 (机械, 只能英文)
```

---

# 第七部分：如何运行

## 方式1: 完整启动 (后端+摄像头+麦克风+ASR+TTS)
```bash
cd E:/Aociety-NEW
.\start_full.bat
```

## 方式2: 仅后端
```bash
cd E:/Aociety-NEW
uvicorn backend.main:app --reload --port 8000
```

## 方式3: 完整管线 (单独启动采集)
```bash
# 终端1: 后端
uvicorn backend.main:app --reload --port 8000

# 终端2: 全管线采集
python -m services.emotion_pipeline --backend http://127.0.0.1:8000
```

## 方式4: 调试模式 (单独测试各模块)
```bash
# 测试 SenseVoice ASR
python -c "from services.audio_service import AudioService; ...

# 测试 Vision
python -c "from services.vision_service import VisionService; ...

# 测试 TTS
python -c "from services.tts_service import TTSService; ...
```

---

# 第八部分：环境变量 (.env)

```ini
# === 必填 (启动必需的) ===
TOKENHUB_API_KEY=your_tokenhub_key                         # tokenhub.market 中转Key
TOKENHUB_BASE_URL=https://api.tokenhub.market/v1           # GLM 5.2 API地址
TOKENHUB_MODEL=glm-5.2                                     # 模型名

# === 端口 ===
AOCIETY_PORT=8000        # 主后端
R1_OMNI_PORT=8001        # (备用) R1-Omni服务
AROUSAL_PORT=8002        # (备用) Arousal服务

# === 开关 ===
ENABLE_EMOTION=1         # 0 = 关闭情感计算 (只用世界引擎)
WORLD_PULSE_SECONDS=60   # 世界AI脉冲间隔

# 不要把真实密钥写进交接文档或提交到 Git。
```

---

# 第九部分：项目来源与关系

本项目是从之前的4个项目中迁移+整合而来：

### 原始项目路径

| 项目 | 位置 | 用途 |
|------|------|------|
| **lunwen** (论文) | `/e/Desktop/lunwen/` | 情感计算核心源代码来源 |
| **chonggou** (重构) | `/e/Desktop/chonggou/` | 树莓派Pi版本 (情感计算管线, 摄像头/麦克风采集) |
| **gamexu** (游戏) | `/e/Desktop/gamexu/` | Godot 4.5 版Aociety游戏 (36 NPC世界引擎) |
| **gpt聊天文档** | `/e/Desktop/gpt聊天文档/` | 设计文档/ICMI论文/模型选型/与博导讨论记录 |

### 迁移映射

```
lunwen/                      →  Aociety-NEW/
├── engine/ (完整)           →  engine/ (完整)
├── backend/
│   ├── affect_runtime.py    →  backend/affect_runtime.py
│   ├── assessment_engine.py →  backend/assessment_engine.py
│   └── openclaw_gateway.py  →  backend/openclaw_gateway.py
├── qwen_duplex_adapter.py   →  backend/glm_adapter.py (Qwen3→GLM替换)
├── assistant_service.py     →  backend/assistant_service.py
└── assistant_store.py       →  backend/assistant_store.py

gamexu/                      →  Aociety-NEW/
├── services/
│   ├── engine.py            →  services/engine.py
│   ├── ark_client.py        →  services/ark_client.py (豆包→GLM替换)
│   ├── app.py               →  services/app.py
│   └── npc_story_overrides.py → services/npc_story_overrides.py
├── data/*.json              →  data/
├── Main.gd                  →  ue5_project/ (Godot→C++重写)
└── ApiClient.gd             →  ue5_project/AocietyClientSubsystem (重写)
```

### 版本差异说明

| 特性 | lunwen (旧) | chonggou (旧) | Aociety-NEW (新) |
|------|:---------:|:-----------:|:--------------:|
| 主AI | Qwen3-Omni | 豆包+Piper | GLM 5.2 (统一) |
| 情感计算 | AffectRuntime | Pi版引擎 | AffectRuntime+引擎 |
| 游戏 | 无 | 无 | WorldEngine+UE5 |
| ASR | sherpa+Paraformer | sherpa+Vosk | **SenseVoice**(阿里) |
| TTS | 无 | Piper (离线) | Edge TTS(晓晓) |
| 表情 | FER+ | FER+ | FER++MPFace |
| 姿态 | 无 | 无 | MediaPipe Pose |
| 客户端 | 无 | 无 | UE5.8 C++ |
| 部署 | 单服务 | Pi Zero2W | 笔记本/UE5 |
| 关怀 | 规则+LLM | Pi规则 | 同lunwen |

---

# 第十部分：技术债务与待解决

## 技术债务

1. **OpenClaw记忆系统** — `backend/openclaw_gateway.py` 需要 OpenClaw CLI 运行时才能完整工作。当前用 `SimpleMemoryStore` 内存存储替代（`backend/main.py` 第36-52行）。需将内存存储改为持久化（SQLite / Redis / OpenClaw）。

2. **Godot → UE5 迁移未完成** — 原来的Godot项目 `E:/Desktop/gamexu/` 有完整的 2D 游戏前端。`ue5_project/` 只是 C++ 模板，内容/蓝图/地图全空。

3. **SenseVoice 模型更新** — 模型 `model.pt` 随时可能更新。可以从 ModelScope 下载新版本:
```python
from modelscope import snapshot_download
path = snapshot_download('iic/SenseVoiceSmall', revision='v2.0.2')
```

4. **GLM 5.2 API 依赖** — 依赖 `tokenhub.market` 中转。如果停止服务需要替换 API。

5. **tokenhub 连接缓慢** — 首次调用 GLM API 需要 5-10s 冷启动，之后 <1s。可在启动时预热:
```bash
curl -X POST http://127.0.0.1:8000/emotion/analyze \
  -H "Content-Type: application/json" \
  -d '{"text_hint":"预热"}'
```

## 性能指标 (参考)

| 操作 | 延迟 |
|------|------|
| GLM 5.2 情感推理 (冷启动) | 5-10 秒 |
| GLM 5.2 情感推理 (热) | 0.5-1.5 秒 |
| SenseVoice ASR 转写 | 0.6-1.2 秒 |
| FER+ 表情分类 | 5-10 ms |
| MediaPipe FaceLandmarker | 15-30 ms |
| MediaPipe PoseLandmarker | 20-40 ms |
| Edge TTS 合成 | 1-3 秒 (需联网) |
| 世界AI脉冲 (36 NPC) | 10-30 秒 |

## 待改进

- [ ] **多玩家模式**: 当前世界引擎支持多NPC, 但玩家数据结构只支持1人
- [ ] **CosyVoice 离线部署**: 与Edge TTS媲美但完全离线 (需要GPU)
- [ ] **长期用户记忆**: 持久化用户情感变化历史, 以季度/周为单位分析趋势
- [ ] **语音克隆**: 若有用户音频, 可克隆声线让NPC用"自己的声音"说话
- [ ] **GPU推理**: FunASR+Pose+表情 如果跑在GPU上可大幅提升速度
- [ ] **UE5 UI/UX**: 需要设计人物头像/表情气泡/情绪环等HUD元素

---

# 第十一：快速故障排查

### 启动报错
```
# 端口占用
Error: [WinError 10048] Only one usage of each socket address is normally permitted
→ taskkill /f /im python.exe 或 netsh int ip delete acl

# 找不到模块
ModuleNotFoundError: No module named 'services'
→ 从 E:/Aociety-NEW/ 目录运行

# 模型文件损坏
Unable to open zip archive (pose_landmarker.task)
→ 重新下载
```

### 运行时错误
```
# 后端健康检查失败
→ .env 中 API_KEY 是否填写
→ curl localhost:8000/health 是否正常

# 情感分析一直返回 degraded=True
→ source_models 字段显示 local_expression_fallback → GLM API 不可用
→ 检查 .env 的 TOKENHUB_API_KEY 和套餐状态

# NPC关怀没反应
POST /emotion/care 返回 "":"none"
→ 当前 support_need 较低 (<0.4)
→ 用坏情绪文本测试: "今天真的好累"

# TTS没声音
→ 需要联网 (Edge TTS 是云服务)
→ 检查 voice 参数是否正确开头
→ 备用: 修改 tts_service.py 设置 _tts_method = "pyttsx3"

# 摄像头/麦克风管线
→ 检查其他程序是否占用 (浏览器/微信等)
→ 检查设备权限 (Win10设置→隐私→摄像头/麦克风)
```

---

# 附录A：启动命令速查

```bash
# 后端
uvicorn backend.main:app --reload --port 8000

# 全管线 (开摄像头+麦克风+ASR+姿态)
python -m services.emotion_pipeline --backend http://127.0.0.1:8000

# ASR测试
python -c "from services.audio_service import AudioService; import scipy.io.wavfile as wav; sr,d=wav.read('data/test_zh.wav'); print(AudioService()._transcribe(d.astype('int16')))"

# TTS测试
python -c "from services.tts_service import TTSService; TTSService().synthesize('你好世界')"

# 情感测试
curl -X POST http://127.0.0.1:8000/emotion/analyze \
  -H "Content-Type: application/json" \
  -d '{"text_hint":"今天真的好累"}'

# 世界状态
curl http://127.0.0.1:8000/world/state | python -m json.tool | head 20

# GLM 5.2 API 直接测试
python -c "
import httpx, os
r=httpx.post('https://api.tokenhub.market/v1/chat/completions',
  json={'model':'glm-5.2','max_tokens':128,'messages':[{'role':'user','content':'Say OK'}]},
  headers={'Authorization':'Bearer '+os.environ['TOKENHUB_API_KEY']},
  timeout=30)
print(r.json())
"
```

---

# 附录B：技术选型理由 (摘自设计讨论)

| 决策 | 理由 |
|------|------|
| 为什么 GLM 5.2 > GPT-4o? | 同一tokenhub中转通道, 中文情感理解更好, 更便宜 |
| 为什么 SenseVoice > Paraformer? | 下一代, 内置情感识别, 多语言, 更快 |
| 为什么 Edge TTS > pyttsx3? | 质量好100倍, 晓晓甜美女声微软出品 |
| 为什么 FER+ > DeepFace? | 体积10MB VS 100MB, 速度快10倍 |
| 为什么 MediaPipe > OpenPose? | CPU实时33点, 无GPU要求 |
| 为什么 FastAPI > Flask? | 异步支持, 自动OpenAPI, Pydantic模型 |
| 为什么 Python > C#/Rust? | 快速迭代, ML生态, 与论文环境一致 |

---

**本文档结束. 祝你接手顺利! 🚀**
