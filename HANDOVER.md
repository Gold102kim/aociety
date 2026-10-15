# Aociety-NEW 交接说明

更新时间：2026-10-15

## 数字代表开发（第一至十批）

第十批确认玻璃达到当前本机验收标准，回到原方案的隐私控制主线：取消请求
不再变更临时模式或解除学习暂停；临时状态返回脱敏副本，界面同步运行期模式；
整页刷新/主渲染退出结束旧登录，跨模式和跨文档旧任务失效。长期结构与资料不迁移，
不新增自动登录或完整历史保存。实现和测试见 `docs/REPRESENTATIVE_PRIVACY_SESSION.md`。

2026-10-15 上传前追加复核修复：隐私操作失败提示不再被恢复读取清掉，重置失败保留确认；确定性及隔离桌面回归通过。README 已同步当前行为。本次仅上传源码与可分发资源，不重新构建 E 盘第十批 EXE；审查和上传边界见 `docs/PROJECT_REVIEW_0.6.0.md`。

第九批保留第八批材质，优化高频指针合帧和读写顺序，补齐滚动、触摸、取消、
失焦及目标变化时的高光清理。隔离基线与新版交互回归见
`docs/UI_LIQUID_GLASS_INTERACTION.md`，不把布局读取次数变化称为帧率提升。

第八批在既有导航、分段栏和聊天输入区加入局部背景位移折射与方向性高光。
文字、输入控件和 3D 画布保持未过滤；清晰/高对比回退保留，不改账户与模型配置。
数学测试及实际像素对照用于验证边缘折射和中心稳定；实现边界见
`docs/UI_LIQUID_GLASS.md`，当前独立 EXE 与校验见 `docs/LOCAL_ACCEPTANCE.md`。

桌面端已开始按数字代表方案推进：免长问卷启动、DeepSeek 独立授权、
默认关闭的偏好学习、三种画像模式、临时对话、来源查看及修正删除。
当前只识别回答长短和五种音乐类型的明确表达，不具备通用语义画像或人格复刻能力。
旧问卷保留在原账户数据中，不自动导入或发送给对话模型。
新画像使用独立的系统加密文件和隐私账本，拒绝旧版本恢复被删数据。
第二批新增主动预览保存话题/草稿、重登后继续、完成及移除；最多 3 条，
只保留确认的片段，不保存完整聊天。恢复仅放回输入框，不自动发送，
不覆盖未保存文字；来自草稿的对话暂停偏好学习。临时模式由主进程拒绝待续操作。
完成或移除会删除保存正文，不留归档；重置同时清除待续内容。
第三批新增私密试答：同一情境可分别比较通用、本人修正偏好、修正加对话偏好，
每次点击 1 次请求；事实、风格、选择、帮助程度由本人分项评价，不生成人格百分比。
对照答案与评分仅留本轮窗口，不上传、不落盘、不反向学习；停止和撤权使晚到试答失效。
这只是受控本机评测入口，并非已经验证相似度；未进行真实模型的付费评测。
实现范围、测试命令和后续任务见 `docs/DIGITAL_REPRESENTATIVE_PROGRESS.md`。
第四批在源码工作区生成独立的本机便携验收包，并通过实际打包程序功能回归、
系统加密、包内审查及便携 EXE 启动退出检查；路径、校验值与手工步骤见
`docs/LOCAL_ACCEPTANCE.md`。未签名，不含受限角色模型和 UE 游戏，不作为公开发行版。
第四批生成时未替换 E 盘原程序、未改真实账户与本地配置，当时尚未上传该批代码；后续源码上传复核见上文。外部试用网关仍未完成。
第五批修正外观加载的固定成功提示、整页重载重试和旧问卷造成的初始化误导。
加载失败或 20 秒超时可以局部重试，文字对话与草稿保持可用；规划中的能力明确标注。
加载生命周期回归使用独立测试几何体，不分发受限人物素材。测试与限制见开发记录。
第六批让角色扮演、翻译、引用与恢复草稿触发的安全暂停如实显示，模型请求失败也不误报学习中。
暂停仅为本次会话状态，不落盘；清空对话恢复原模式并保留草稿与记忆，旧异步读取不能覆盖新状态。
没有扩大学习范围、增加依赖或调用真实模型；强制重载窗口后的完整会话恢复仍非本批能力。
第七批以 Apple Design 优化玻璃材质分层、导航分组、SVG 控件、开关与按压反馈。
正文减少玻璃嵌套，聊天建议进入主区，长说明渐进展开，关键隐私控制保留；账户和数据协议未改。
本轮设计与测试范围见 `docs/UI_APPLE_GLASS.md`；新便携包与旧版并存，不能混用相同版本号判断内容。

## 本轮源码审查状态

当前编辑工作区为独立的源码副本；完整本机素材仍保留在 E 盘原项目。
公开分支排除受限/未经确认的角色、场景和测试音视频，不改写历史。
恢复、依赖审计、自动验证及未完成条件见 `docs/PROJECT_REVIEW_0.6.0.md`。
特别注意：新 UE C++ 尚未通过原生编译（本机缺少有效 MSVC 工具链），
已有游戏二进制不代表包含本次源码修复；不要把静态检查称为游戏验收。

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

`UAocietyGameInstance` 已实现 Launcher Contract 1.0，读取并校验 `LauncherSessionFile`、`LauncherContractVersion` 和 `LauncherLaunchId`。开发版允许没有启动器参数时直接调试。Shipping 目前拒绝所有本地票据，直到实现真正的服务端票据交换；格式与有效期校验不能证明本地票据可信。

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
python -B -m unittest discover -s tests -v
curl.exe http://127.0.0.1:8000/health
curl.exe -X POST http://127.0.0.1:8000/forest/probe
```

UE C++ 最小编译验证使用 `AocietyEditor Win64 Development -NoLink`；最终交付前关闭 Editor 并执行完整链接。

## 7. 安全与 Git

- `.env` 不得加入 Git。
- 提交前执行 `git diff --check` 和敏感信息扫描。
- 不把 API Key 写入日志、README、HANDOVER、截图或提交信息。
- 旧提交中的历史密钥不会在本轮自动改写；仓库对外发布前应轮换密钥并单独清理历史。
