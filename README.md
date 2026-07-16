# EchoVerse Launcher

EchoVerse 的 Windows 桌面启动器原型，包含账户注册、登录、保持会话、启动器主页以及版本化的 UE5 游戏启动接口。

日常启动时可直接双击项目总目录中的 `EchoVerse启动器.exe`，不需要打开终端或运行开发命令。该程序会自动定位同目录下的 `软件端` 文件夹和 Electron 运行时。

软件每次启动均先显示账户登录界面。新账户注册成功后必须完成一次基础问卷，问卷会写入该账户档案，保存成功后才能进入启动器主页；再次登录已完成问卷的账户会直接进入主页。退出账户后立即返回登录界面。账户保存在 Electron 的 `userData/accounts.json` 中，密码仅保存随机盐和 `scrypt` 哈希，不保存明文。当前账户库适用于单机开发联调，正式联网版本仍需替换为平台账户后端。

创建账户时系统会同步分配唯一的 AI Agent 档案，初始状态为 `WAITING_FOR_PROFILE`。首次基础问卷保存后，身份、MBTI 和偏好会写入该 Agent，状态更新为 `READY`。虚拟分身页面的“与我的 AI 对话”会把这份结构化档案转换为人格提示，并通过共享 OpenAI Responses API 进行对话。当前仅发送最近 12 条本次会话记录，不包含长期记忆。

## 配置共享大模型

开发机可将 `config/ai.example.json` 复制为 `config/ai.local.json`，填写 OpenAI API Key 后重启软件。也可以通过项目专用的 `ECHOVERSE_OPENAI_API_KEY`、`ECHOVERSE_OPENAI_MODEL` 和 `ECHOVERSE_OPENAI_BASE_URL` 环境变量配置。软件不会读取通用 `OPENAI_API_KEY`，以免误用其他开发工具的凭据。检查人格提示与配置隔离逻辑：

```powershell
pnpm test:ai
```

`config/ai.local.json` 已被 Git 忽略。该文件只适用于本地原型测试，不得提交、分发或打包进客户端。正式发布时必须由平台后端保管 API Key，客户端只调用经过身份验证、限流和审计的平台 AI 接口。

## 伴生模式

完成登录和基础问卷后，点击窗口右上角的菱形按钮可进入基础伴生模式。主窗口会隐藏，并在当前显示器工作区右下角显示一个 300×360 的透明无边框分身窗口。拖动透明区域可移动窗口，双击角色或点击悬停后出现的展开按钮可恢复主界面；关闭桌宠窗口时也会自动恢复主界面。

## 玩家强调色

首次基础问卷提供九种颜色预设。选择颜色时问卷会即时预览，保存后颜色名称写入账户档案；后续登录会自动应用到导航栏、主要按钮、状态灯、启动序列、AI 聊天气泡和桌宠核心。旧档案中的常见颜色文本会映射到最接近的预设色，无法识别时回退到默认薄荷绿。

## 本地运行

```powershell
pnpm install
pnpm dev
```

账户模块测试：

```powershell
pnpm test:auth
```

## 接入本地 UE5 游戏

1. 将 `config/game.example.json` 复制为 `config/game.local.json`。
2. 填写 UE5 打包程序的绝对路径。
3. 重新启动 Launcher，点击“启动游戏”。

游戏端接口要求见 `docs/UE5_GAME_HANDOFF.md`，数据格式见 `contracts/launcher-session.schema.json`。

当前账户系统为本地原型，仅用于 UI 与启动流程验证，不可作为正式生产认证系统。
