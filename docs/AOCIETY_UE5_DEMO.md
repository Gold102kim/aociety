# Aociety UE5 Demo

Aociety 的 UE5.8 森林小镇 Demo。游戏内两名居民由 DeepSeek V4 Flash 实时生成对话；主动式情感关怀由硬件端负责，UE 只发送游戏场景和情绪上下文。

## 当前验收链路

```text
UE5.8
  -> POST http://127.0.0.1:8000/forest/resident_chat
  -> services.app
  -> https://api.deepseek.com
  -> deepseek-v4-flash
```

成功的居民回复必须同时满足：

```json
{
  "source": "llm",
  "provider": "deepseek",
  "model": "deepseek-v4-flash"
}
```

请求失败、响应无法解析或来源校验不通过时，服务返回 `source=error`。项目不会用固定台词冒充模型回复。

## 配置与启动

复制 `.env.example` 为 `.env`，只在本机填写密钥：

```dotenv
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
```

启动居民服务：

```powershell
python -m uvicorn services.app:app --host 127.0.0.1 --port 8000
```

也可以运行 `start_backend.bat`。`start_full.bat` 会把居民服务启动在 `8000`，硬件情感服务启动在 `8010`。

## 居民行为

- `npc_01`：林汐，安静温和，喜欢阅读和散步。
- `npc_02`：小樱，亲切活泼，喜欢料理和照顾花草。
- 玩家靠近并按 `E` 后发起实时请求。
- 两名居民自主漫游、播放 Idle/Walk，并定时进行真实 NPC-NPC 对话。
- 每轮请求携带场景白名单、时间、位置、交互对象和随机 nonce。
- 回复过滤股市、股票、交易、绿藻、海藻、重工、公司、投资等旧黑客松背景。
- 每次 DeepSeek 请求发送 `thinking: {"type":"disabled"}`，优先降低交互延迟。

## UE5.8 客户端

主要代码位于 `ue5_project/Source/Aociety`：

- `UAocietyClientSubsystem`：请求居民接口并严格校验 source/provider/model。
- `AAocietyGameMode`：绑定对话触发器并调度 NPC-NPC 交流。
- `AAocietyNPCCharacter`：漫游、停留、朝向、Idle/Walk、比例保护和实体气泡。
- `UAocietyNPCBubbleWidget`：象牙白实体气泡，显示思考、生成、倾听和失败状态。
- `AAocietyPlayerCharacter`：Ecy 第三人称控制、Motion Matching Driver 和 Manny 到 Ecy 实时重定向。

地图：`/Game/Aociety/Maps/Aociety_ForestSnowTown`。

当前 `services.app` 没有 `/ws/emotion` 路由，因此 UE 的旧 Emotion WebSocket 默认关闭，避免持续 403。硬件服务提供对应路由后可显式启用。

## 硬件主动关怀边界

`backend/` 和 `services/emotion_pipeline.py` 保留摄像头、麦克风、姿态、ASR、TTS 与硬件关怀能力。主动检测、关怀决策、语音和机器人动作属于硬件端；游戏端只发布必要的场景和情绪上下文。

## 验证

```powershell
python -m pytest -q
```

当前门禁包括：

- DeepSeek 是森林居民唯一可用路由。
- LLM 失败时返回 `source=error`，不回退固定台词。
- 玩家与 NPC-NPC 对话保留短期记忆。
- 旧故事词过滤与场景字段白名单。
- 地图仅有 2 名 NPC、2 个 Trigger 和 1 个 PlayerStart。
- Ecy Motion Matching、跳跃/落地、低幅度裙摆与头发二级运动。
- NPC 运行时比例保护、Idle/Walk 漫游和两套颜色变体。

## 目录

```text
services/                       居民服务、世界引擎和 DeepSeek 客户端
tests/                          居民服务测试
ue5_project/Source/Aociety/     UE5.8 C++ 客户端与角色代码
ue5_project/Content/Aociety/    Aociety 地图和资产
ue5_project/Content/Python/     UE 编辑器自动化与审计脚本
backend/                        硬件情感计算服务
SourceAssets/                   原始角色和 UI 素材
```
