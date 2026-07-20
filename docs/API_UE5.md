# Aociety 情感计算系统 — UE5 API 接口文档

> 本文档定义 Unreal Engine 5.8 客户端与 Python 后端之间的所有通信接口。
> 居民/世界基础地址：`http://127.0.0.1:8000`；情感/TTS/评估基础地址：`http://127.0.0.1:8010`。
> 旧示例中的单一 `BackendURL` 应分别替换为 `BackendURL`（8000）和 `CareBackendURL`（8010）。

---

## 目录

1. [REST API](#1-rest-api)
   - [1.1 情感分析](#11-情感分析)
   - [1.2 情感状态查询](#12-情感状态查询)
   - [1.3 NPC 主动关怀](#13-npc-主动关怀)
   - [1.4 世界状态](#14-世界状态)
   - [1.5 NPC 交互](#15-npc-交互)
   - [1.6 玩家性格评估](#16-玩家性格评估)
   - [1.7 记忆系统](#17-记忆系统)
2. [WebSocket API](#2-websocket-api)
   - [2.1 情感流](#21-情感流)
   - [2.2 世界状态流](#22-世界状态流)
3. [数据流架构](#3-数据流架构)
4. [UE5 集成指南](#4-ue5-集成指南)

---

## 1. REST API

### 1.1 情感分析

**端点：** `POST /emotion/analyze`

**用途：** UE5 将摄像头帧和/或麦克风音频发送至后端，后端返回玩家当前情感状态。

**请求：**

```json
{
  "image_base64": "/9j/4AAQ...",    // JPEG base64, 可选
  "audio_base64": "//uQx...",       // PCM16 base64, 可选
  "text_hint": "今天好累...",       // 文本输入, 可选
  "timestamp_ms": 1712345678901
}
```

**响应：**

```json
{
  "emotion": "sadness",
  "valence": 0.23,
  "arousal": 0.67,
  "support_need": 0.72,
  "trend": {
    "window_ms": 10000,
    "emotion_stability": 0.8,
    "valence_delta": -0.12,
    "arousal_delta": 0.08,
    "support_need_delta": 0.15,
    "label": "downward_negative"
  },
  "confidence_gap": 0.45,
  "top_candidates": [
    {"label": "sadness", "score": 0.72},
    {"label": "anxiety", "score": 0.15},
    {"label": "neutral", "score": 0.08}
  ],
  "degraded": false,
  "source_models": {
    "emotion": "glm-5.2",
    "va": "glm-5.2+arousal-service"
  }
}
```

**字段详解：**

| 字段 | 范围 | 说明 |
|------|------|------|
| `emotion` | enum | joy/sadness/anxiety/anger/frustration/surprise/neutral |
| `valence` | [0, 1] | 效价：0=极度负面, 1=极度正面 |
| `arousal` | [0, 1] | 唤醒度：0=极度平静, 1=极度激动 |
| `support_need` | [0, 1] | 关怀需求度 — 主动关怀系统的核心指标 |
| `trend.label` | enum | stable/downward_negative/upward_relief/high_arousal_rising |

**UE5 实现建议：**
- 每 1-3 秒发送一次摄像头帧（JPEG 质量 70-80）
- 音频每 0.5-1 秒发一个 chunk
- 文本 hint 在有玩家打字/语音输入时附带

---

### 1.2 情感状态查询

**端点：** `GET /emotion/state`

**用途：** UE5 轮询当前情感状态（如果不使用 WebSocket）

**响应：** 同 1.1 的响应格式。

---

### 1.3 NPC 主动关怀

**端点：** `POST /emotion/care`

**用途：** 根据玩家当前情绪，获取 NPC 的关怀回应。

**请求：**

```json
{
  "npc_id": "npc_03",
  "scene_context": {
    "district": "贫民街",
    "time": "evening",
    "nearby_npcs": ["npc_01", "npc_05"]
  }
}
```

**响应：**

```json
{
  "npc_line": "看你脸色不太好，今天是不是太拼了？",
  "action": "speak_kindly",
  "care_level": "care",
  "duration_seconds": 8.0,
  "emotion_reflected": "sadness"
}
```

**`action` 可能值：**

| 动作 | 含义 | UE5 表现 |
|------|------|----------|
| `pat_head` | 轻拍头 | NPC 做轻拍动画 |
| `offer_food` | 递食物 | NPC 做递物动画 |
| `sit_quietly` | 静坐陪伴 | NPC 坐下，不对话 |
| `speak_kindly` | 温柔说话 | NPC 播放对话 |
| `leave_space` | 留出空间 | NPC 走开几步 |
| `offer_seat` | 让座 | NPC 指向空位 |

**`care_level` 含义：**

| 等级 | support_need 范围 | 游戏响应 |
|------|-------------------|----------|
| `nudge` | 0.4 - 0.6 | 轻微关心，一句问候 |
| `care` | 0.6 - 0.8 | 主动关怀，特殊对话 |
| `guard` | > 0.8 | 紧急介入，改变场景氛围 |

---

### 1.4 世界状态

**端点：** `GET /world/state`

**用途：** 获取游戏世界的完整快照（NPC 位置、经济、事件等）

**响应：**

```json
{
  "world_state": {
    "day": 3,
    "clock_minutes": 720,
    "time_period": "afternoon",
    "npcs": [
      {
        "id": "npc_01",
        "name": "老陈",
        "district": "贫民街",
        "subregion_id": "forest_farm",
        "x": 430.0,
        "y": 320.0,
        "mood": "wary",
        "emotion": "neutral",
        "activity": "working",
        "relationship_with_player": "acquaintance"
      }
    ],
    "player": { ... },
    "goods": [ ... ],
    "stocks": [ ... ],
    "headline_news": [ ... ]
  }
}
```

**端点：** `POST /world/action`

**用途：** 玩家在世界中执行一个动作。

---

### 1.5 NPC 交互

**端点：** `POST /npc/player_talk`

**用途：** 玩家与 NPC 对话。

**请求：**

```json
{
  "npc_id": "npc_01",
  "district": "贫民街",
  "approach": "cautious",
  "player_input": "最近生意怎么样？",
  "player_position": {"x": 430.0, "y": 330.0}
}
```

**响应：**

```json
{
  "message": "ok",
  "world_state": { ... },
  "dialogue": {
    "npc_line": "...不太好，煤价跌得厉害。",
    "stance": "wary",
    "truthfulness": 0.7,
    "revealed_topic_ids": ["coal_price_crash"]
  }
}
```

**端点：** `GET /npc/list`

**用途：** 获取所有 NPC 列表。

**端点：** `GET /npc/{npc_id}`

**用途：** 获取单个 NPC 详细信息。

---

### 1.6 玩家性格评估

**端点：** `POST /assessment/start`

**用途：** 开始 8 维性格评估。

**响应：** `{"session_id": "uuid", "message": "评估已开始"}`

**端点：** `POST /assessment/turn`

**用途：** 提交一轮评估对话。

**端点：** `GET /assessment/state/{session_id}`

**用途：** 获取评估进度。

**端点：** `POST /assessment/finish/{session_id}`

**用途：** 完成评估。

**响应：**

```json
{
  "profile": {
    "Fe": 0.7, "Fi": 0.5,
    "Ni": 0.6, "Ne": 0.4,
    "Te": 0.3, "Ti": 0.7,
    "Se": 0.5, "Si": 0.8,
    "summary": "安静内敛，习惯照顾他人感受，压力下容易自我消化。",
    "care_preferences": {
      "preferred_style": "gentle",
      "privacy_sensitivity": "high",
      "active_care_threshold": 0.65
    }
  }
}
```

### 1.7 记忆系统

**端点：** `GET /memory/search?query=xxx&limit=10`

**端点：** `POST /memory/store`

---

### 1.8 TTS 文字转语音（甜女声）

**端点：** `GET /tts/voices`

列出可用甜女声。返回：
```json
{
  "voices": [
    {"id": "xiaoxiao", "name_cn": "晓晓", "description": "sweet-warm-young", "sweet": true},
    {"id": "xiaoyi",   "name_cn": "晓伊", "description": "warm-friendly", "sweet": true},
    {"id": "xiaomeng", "name_cn": "晓梦", "description": "cute-fresh-young", "sweet": true},
    {"id": "xiaomo",   "name_cn": "晓墨", "description": "literary-soft", "sweet": true},
    {"id": "xiaoxuan", "name_cn": "晓萱", "description": "warm-soft", "sweet": true}
  ],
  "current": "xiaoxiao"
}
```

**端点：** `POST /tts/voices/{voice_name}`

切换甜女声。

**端点：** `POST /tts/synthesize`

请求：
```json
{"text": "主人,要不要起来活动活动?", "voice": "xiaoxiao"}
```

响应：
```json
{
  "audio_base64": "SUQz...",           // MP3 bytes base64
  "audio_format": "mp3",
  "voice": "xiaoxiao",
  "voice_name_cn": "晓晓",
  "duration_estimate": 2.4,
  "text": "主人,要不要起来活动活动?"
}
```

**端点：** `POST /emotion/care_with_voice` (返回完整关怀 + 甜女声MP3)

请求同 `/emotion/care`，但响应额外包含 `audio_base64` 字段。

---

### 1.9 身体姿态/动作 (Pose)

**端点：** `POST /emotion/analyze` 接受更高层payload：
```json
{
  "image_base64": "...",          // 摄像头帧
  "pose_features": {              // 来自 MediaPipe Pose（可选）
    "landmarks": [...],            // 33 个关键点
    "posture_score": 0.7,          // 姿态端正度
    "activity_level": 0.3,         // 活动度
    "gesture_intensity": 0.2,     // 手势强度
    "is_sitting": false
  },
  "audio_base64": "...",          // 麦克风
  "text_hint": "...",             // 文本
  "timestamp_ms": 1712345678901
}
```

后端会把 `pose_features` 合并到情绪计算中影响 arousal（身体语言→唤醒度）。

---

### 1.10 端点总计 (32+)

| 类别 | 端点 | 说明 |
|------|------|------|
| **情感** | `POST /emotion/analyze` | 多模态情感分析 (视频+音频+文本+姿态) |
| | `GET /emotion/state` | 拉取当前情感状态 |
| | `POST /emotion/care` | NPC关怀 (纯文本) |
| | `POST /emotion/care_with_voice` | NPC关怀 + 甜女声MP3 |
| | `POST /emotion/reset` | 重置 |
| | `WS /ws/emotion` | 实时情感流 |
| **TTS** | `GET /tts/voices` | 列出甜女声 |
| | `POST /tts/voices/{name}` | 切换女声 |
| | `POST /tts/synthesize` | 文字转语音 |
| **评估** | `POST /assessment/start` | 开始8维评估 |
| | `POST /assessment/turn` | 提交评估回答 |
| | `POST /assessment/finish/{id}` | 完成评估 |
| **世界** | `GET /world/state` | 世界快照 |
| | `POST /world/action` | 玩家动作 |
| | `POST /world/end_day` | 结束一天 |
| | `POST /world/reset` | 重置世界 |
| **NPC** | `GET /npc/list` | NPC列表 |
| | `GET /npc/{id}` | NPC详情 |
| | `POST /npc/player_talk` | NPC对话 |
| **记忆** | `GET /memory/search` | 搜索记忆 |
| | `POST /memory/store` | 存储记忆 |

---

## 2. WebSocket API

对于实时性要求高的场景，使用 WebSocket 替代 REST。

### 2.1 情感流

**端点：** `ws://127.0.0.1:8000/ws/emotion`

**用途：** UE5 持续推送帧，后端实时返回情感分析结果。

**UE5 → 后端（每秒）：**

```json
{
  "image_base64": "...",
  "audio_base64": "...",
  "text_hint": "",
  "timestamp_ms": 1712345678000
}
```

**后端 → UE5（每次分析后）：**

```json
{
  "emotion": "sadness",
  "valence": 0.23,
  "arousal": 0.67,
  "support_need": 0.72,
  "trend": { ... },
  "confidence_gap": 0.45,
  "top_candidates": [...]
}
```

### 2.2 世界状态流

**端点：** `ws://127.0.0.1:8000/ws/world`

**UE5 → 后端：**

```json
{"type": "get_state"}
{"type": "action", "action_type": "work", "district": "贫民街", "payload": {}}
```

**后端 → UE5：**

```json
{"type": "world_state", "data": { ... }}
```

---

## 3. 数据流架构

```
┌────────────────────────────────────────────────────────────────┐
│                        UE5 客户端                               │
│                                                                │
│  ┌──────────┐  摄像头帧    ┌──────────┐  音频Chunk  ┌───────┐ │
│  │ CameraCapture │────────►│  AudioCapture │────────►│ HUD  │ │
│  └──────────┘     JPEG     └──────────┘    PCM16    └───────┘ │
│       │               b64        │               b64           │
│       ▼                          ▼                             │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │               WebSocket / HTTP Client                    │  │
│  └────────────────────────┬────────────────────────────────┘  │
└───────────────────────────┼────────────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────────────┐
│                      Python 后端 (8000)                        │
│                                                                │
│  ┌──────────────┐    ┌──────────────────┐    ┌─────────────┐  │
│  │ GLM 5.2      │    │  AffectRuntime    │    │  WorldEngine│  │
│  │ Emotion API  │◄──►│  + FusionScorer  │◄──►│  + NPC AI   │  │
│  └──────────────┘    └──────────────────┘    └─────────────┘  │
│       ▲                      ▲                      ▲          │
│       │                      │                      │          │
│  ┌────┴──────┐        ┌──────┴──────┐        ┌─────┴──────┐  │
│  │ GLM 5.2   │        │ R1-Omni    │        │ Arousal    │  │
│  │ (云端)    │        │ (8001)     │        │ (8002)     │  │
│  └───────────┘        └────────────┘        └────────────┘  │
└────────────────────────────────────────────────────────────────┘
```

## 4. UE5 集成指南

### 4.1 必装插件

- **VaRest** 或 **HTTP Blueprints** — REST API 调用
- **WebSocket** — 实时通信

### 4.2 主循环 (Tick)

```
每个 Tick (~60fps):
  1. 采集摄像头帧 (每 N 帧一次, 如每 15 帧)
     → JPEG 编码 → base64 → 暂存
  2. 采集麦克风 (每 0.5s)
     → PCM16 → base64 → 暂存
  3. 合并发送到 /emotion/analyze 或 ws://.../ws/emotion
  4. 获取情感状态
  5. 将 emotion/valence/arousal/support_need 暴露给蓝图
```

### 4.3 NPC 情感感知蓝图事件

**OnPlayerEmotionUpdated(EmotionState)**
- 当情感状态更新时触发
- NPC 行为树根据此调整

**OnNPCProactiveCare(NPCId, CareResponse)**
- 当 NPC 决定主动关怀时触发
- 播放对应动画和对话

### 4.4 BP 示例

```cpp
// 在 GameInstance 或 PlayerController 中
HttpRequest
  -> SetURL("http://127.0.0.1:8000/emotion/analyze")
  -> SetVerb("POST")
  -> SetHeader("Content-Type", "application/json")
  -> SetBodyAsString(CameraFrameJson)
  -> ProcessRequest()
  -> OnComplete: ParseResponse -> UpdatePlayerEmotion()
```

### 4.5 建议的渲染显示

在 UE5 HUD 上可选的显示元素：
- **情绪指示器**：一个圆环，颜色 = emotion, 大小 = arousal
- **NPC 关怀提示**：当 NPC 主动关怀时，显示对话气泡
- **支持引导**：当 support_need > 0.7 时，显示"附近有人想关心你"的提示
