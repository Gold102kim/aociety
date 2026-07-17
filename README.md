# Aociety-NEW

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

## 配置

复制 `.env.example` 为 `.env`，填写本机密钥：

```dotenv
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
```

`.env` 已被 `.gitignore` 排除。不要把密钥写入源码、文档或提交记录。

旧的 `TOKENHUB_*`、`GLM_*`、`OPENAI_API_KEY` 和 `ANTHROPIC_API_KEY` 不会被森林居民客户端读取，也不会成为回退路由。

## 启动居民服务

```powershell
cd E:\Aociety-NEW
python -m uvicorn services.app:app --host 127.0.0.1 --port 8000
```

也可以运行 `start_backend.bat`。`start_full.bat` 会把居民服务启动在 `8000`，把硬件情感服务启动在 `8010`，避免两个 FastAPI 应用争用同一端口。

验证：

```powershell
curl.exe http://127.0.0.1:8000/health
curl.exe -X POST http://127.0.0.1:8000/forest/probe
curl.exe -X POST http://127.0.0.1:8000/forest/resident_chat `
  -H "Content-Type: application/json" `
  -d '{"npc_id":"npc_01","player_input":"今天林间适合散步吗？","mode":"player","scene_context":{"location":"forest_town","weather":"晴朗"}}'
```

`/health` 提供通用字段：

- `ai_enabled`
- `ai_configured`
- `ai_provider`
- `ai_model`
- `ai_base_url`

旧的 `glm_*` 健康字段暂时保留为兼容别名，但其值反映当前 DeepSeek 路由。

## 居民行为

- `npc_01`：林汐，安静温和，喜欢阅读和散步。
- `npc_02`：小樱，亲切活泼，喜欢料理和照顾花草。
- 玩家靠近并按 `E` 后发起一轮实时请求。
- 两名居民会按定时器自主交谈，并把对方听到的内容写入短期记忆。
- 每轮请求携带现场事件、场景白名单、时间戳、位置和随机 nonce。
- 回复会过滤股市、股票、交易、绿藻、海藻、重工、公司、投资等旧黑客松背景。
- 每次 DeepSeek 请求都发送 `thinking: {"type":"disabled"}`，优先降低交互延迟，不影响其仍为实时模型生成。

## UE5.8 客户端

主要代码位于 `ue5_project/Source/Aociety`：

- `UAocietyClientSubsystem`：请求居民接口并严格校验 source/provider/model。
- `AAocietyGameMode`：绑定对话触发器并调度 NPC-NPC 交流。
- `AAocietyNPCCharacter`：漫游、停留、朝向、Idle/Walk 和气泡状态。
- `UAocietyNPCBubbleWidget`：象牙白实体气泡，显示实时思考、生成、倾听和失败状态。

当前 `services.app` 没有 `/ws/emotion` 路由，因此 UE 的 `bEnableEmotionWebSocket` 默认关闭，避免 403 重连。需要连接硬件情感服务时，可在 Blueprint/C++ 中显式启用并指向提供该路由的服务。

## 硬件主动关怀边界

`backend/` 和 `services/emotion_pipeline.py` 保留摄像头、麦克风、姿态、ASR、TTS 与硬件关怀能力。主动检测、关怀决策、语音和机器人动作属于硬件端；游戏端只发布必要的场景和情绪上下文，不在 NPC 系统中重复实现硬件决策。

## 测试

```powershell
cd E:\Aociety-NEW
python -m pytest -q
```

测试覆盖：

- DeepSeek 是森林居民唯一可用路由。
- 旧 TokenHub/GLM 环境变量不能重定向居民请求。
- 玩家与 NPC-NPC 对话短期记忆。
- 旧故事词过滤。
- 场景字段白名单。
- `thinking` 被显式关闭。

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
