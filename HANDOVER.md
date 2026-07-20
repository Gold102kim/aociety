# Aociety-NEW 交接说明

更新时间：2026-07-17

## 1. 当前目标

当前 Demo 是森林小镇中的 AI 居民体验：

- 玩家角色 Ecy 可在第三人称场景中移动并与居民互动。
- 林汐与小樱平时漫游、停留，并会自主对话。
- 所有可见居民台词均由 DeepSeek V4 Flash 实时生成或明确显示请求失败。
- 主动式情感关怀属于硬件端。游戏端只提供场景、交互和情绪上下文。

旧黑客松的股市、绿藻、海藻重工、公司和投资设定不属于本 Demo。

## 2. AI 路由

唯一居民模型路由：

```text
Base URL: https://api.deepseek.com
Model:    deepseek-v4-flash
Provider: deepseek
```

本机配置位于 Git 忽略的 `.env`：

```dotenv
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
```

森林居民代码不会读取或回退到 `TOKENHUB_*`、`GLM_*`、`OPENAI_API_KEY` 或 `ANTHROPIC_API_KEY`。

每次请求都带：

```json
{
  "thinking": {"type": "disabled"}
}
```

这是为了降低游戏交互延迟。成功响应必须严格包含：

```text
source=llm
provider=deepseek
model=deepseek-v4-flash
```

否则 UE 和服务端都会把结果降为 `source=error`，不会播放本地固定欢迎语冒充实时生成。

## 3. 服务端

启动：

```powershell
cd E:\Aociety-NEW
python -m uvicorn services.app:app --host 127.0.0.1 --port 8000
```

`start_backend.bat` 启动同一居民服务。`start_full.bat` 同时启动：

```text
services.app:app  -> AOCIETY_PORT，默认 8000
backend.main:app  -> HARDWARE_CARE_PORT，默认 8010
emotion_pipeline -> HARDWARE_CARE_PORT
```

这样游戏内 DeepSeek 请求和硬件情感管线不会争用端口或误走旧服务。

核心接口：

```text
GET  /health
POST /forest/probe
POST /forest/resident_chat
POST /npc/player_talk        兼容入口，森林居民会转发到新服务
POST /npc/conversation       兼容入口，森林居民会转发到新服务
```

`POST /forest/resident_chat` 请求：

```json
{
  "npc_id": "npc_01",
  "player_input": "今天适合散步吗？",
  "mode": "player",
  "counterpart_id": "",
  "scene_context": {
    "location": "forest_town",
    "weather": "晴朗",
    "player_position": {"x": 0, "y": 0, "z": 0}
  }
}
```

NPC-NPC 对话将 `mode` 设为 `ambient`，并填写另一名居民的 `counterpart_id`。

场景上下文采用白名单，避免旧世界状态进入提示词。两名居民各保留最多 12 条短期记忆；生成前会携带近期自身记忆和对方近期记忆。

## 4. UE5.8 对接

核心文件：

```text
ue5_project/Source/Aociety/Private/AocietyClientSubsystem.cpp
ue5_project/Source/Aociety/Private/AocietyGameMode.cpp
ue5_project/Source/Aociety/Private/AocietyNPCCharacter.cpp
ue5_project/Source/Aociety/Private/AocietyNPCBubbleWidget.cpp
```

数据流：

1. 玩家靠近 NPC 的对话 Trigger。
2. 玩家按 `E`，NPC 进入“实时思考”状态。
3. `UAocietyClientSubsystem` 调用 `/forest/resident_chat`。
4. UE 校验 NPC ID、mode、counterpart、source、provider 和 model。
5. 成功时显示象牙白气泡；失败时显示明确错误状态。
6. `AAocietyGameMode` 定时轮换林汐和小樱作为说话者，形成可视化 NPC-NPC 交流。

当前居民服务没有 `/ws/emotion`，因此 `bEnableEmotionWebSocket=false` 是默认值。HTTP 情绪轮询仍可保留；只有连接到真正提供该 WebSocket 的硬件服务时才应显式启用。

UE 当前使用两个明确地址：

```text
BackendURL     = http://127.0.0.1:8000   # 居民、世界、NPC
CareBackendURL = http://127.0.0.1:8010   # 情感、TTS、评估、WebSocket
```

`UAocietyGameInstance` 已实现 Launcher Contract 1.0，读取并校验 `LauncherSessionFile`、`LauncherContractVersion` 和 `LauncherLaunchId`。开发版允许没有启动器参数时直接调试；Shipping 构建会拒绝无效或过期会话。

## 5. 验收清单

后端：

- `/health` 的 `ai_provider=deepseek`。
- `/health` 的 `ai_model=deepseek-v4-flash`。
- `/forest/probe` 返回非空正文。
- 连续请求不是固定重复话术。
- 回复不出现旧黑客松背景词。
- DeepSeek 不可用时返回 `source=error`。

PIE：

- Ecy 不全黑、不镜面、不自发光。
- Ecy 移动时有自然动作，无 T Pose 或纯平移。
- 两名 NPC 开局比例正常，不变巨人。
- NPC 漫游时播放 Walk，停留时播放 Idle。
- 地图仅有两名居民和两个有效对话 Trigger。
- 气泡为象牙白实体样式。
- 玩家按 `E` 后先显示思考，再显示真实 DeepSeek 回复。
- NPC-NPC 对话能看到说话者、倾听者、姓名和真实 source/model。

## 6. 验证命令

```powershell
cd E:\Aociety-NEW
python -m pytest -q
curl.exe http://127.0.0.1:8000/health
curl.exe -X POST http://127.0.0.1:8000/forest/probe
```

UE C++ 最小编译验证使用 `AocietyEditor Win64 Development -NoLink`；最终交付前关闭 Editor 并执行完整链接。

## 7. 安全与 Git

- `.env` 不得加入 Git。
- 提交前执行 `git diff --check` 和敏感信息扫描。
- 不把 API Key 写入日志、README、HANDOVER、截图或提交信息。
- 旧提交中的历史密钥不会在本轮自动改写；仓库对外发布前应轮换密钥并单独清理历史。
