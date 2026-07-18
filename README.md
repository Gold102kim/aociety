# aociety · EchoVerse Launcher

## UE5 Aociety 游戏 Demo

仓库同时包含 UE5.8 森林小镇 Demo、DeepSeek 实时居民服务和硬件情感计算接口。游戏内有 Ecy 第三人称角色、两名自主漫游居民、NPC-NPC 对话与玩家按 `E` 交互；居民回复由 `deepseek-v4-flash` 实时生成，失败时明确显示 `source=error`，不会用固定台词冒充模型结果。

游戏、后端、Motion Matching、地图和验收说明见 [Aociety UE5 Demo](docs/AOCIETY_UE5_DEMO.md)。主动式情感关怀仍属于硬件端，游戏只提供场景、交互和必要的情绪上下文。

EchoVerse 的 Windows Electron 启动器工程。当前版本是可构建、可测试、可回滚的内部原型，覆盖账户入口、首次资料、世界/社交/虚拟分身页面、人格 AI 对话、透明伴生模式，以及向 UE5 游戏交付启动会话的接口。

它还不是可公开运营的平台：账户仍保存在本机，AI 仍由开发机配置直连供应商，游戏票据仍是联调用原型。生产边界和阻断项见 [工程审计](docs/ENGINEERING_AUDIT.md) 与 [安全说明](SECURITY.md)。

## 当前能力

- 软件启动后先进入注册/登录，登录成功前不能进入主界面。
- 新账户完成一次自然的首次资料流程；已填写字段不可修改，空白字段可后续补充。
- 每个账户获得独立 Agent ID、人格档案和记忆命名空间；基础模型服务可以被多个账户共享，并非每位玩家独占一套模型权重。
- 资料保存后显示 2–3 秒启动过渡，再进入主界面。
- 世界、社交、虚拟分身和个人主页具备基础内容与导航，退出登录位于个人主页。
- Three.js 加载临时 GLB 虚拟分身；页面隐藏时暂停渲染，伴生模式限制帧率，并支持 reduced-motion。
- 右上角菱形按钮可切换为透明无边框伴生窗口。
- Launcher Session 通过版本化 JSON Schema 与 UE5 交接。

## 工具链

- Windows 10/11 x64
- Node.js 24.4.x
- pnpm 11.9.x

首次安装：

```powershell
pnpm install --frozen-lockfile
pnpm check
```

开发运行：

```powershell
pnpm dev
```

生成真正不依赖源码、Node.js 或 `node_modules` 的 portable EXE：

```powershell
pnpm dist:win
```

产物位于 `release/EchoVerse-Launcher-<version>-x64.exe`，旁边会生成 SHA-256 文件。项目总目录中早期的 6 KB C# 启动器只适合旧开发目录结构，不应作为发布包。

如果中国大陆网络访问 GitHub Release 超时，可只对当前终端临时指定镜像后重试；Electron 与构建工具仍会按锁文件/内置校验值验证：

```powershell
$env:ELECTRON_MIRROR='https://npmmirror.com/mirrors/electron/'
$env:ELECTRON_BUILDER_BINARIES_MIRROR='https://npmmirror.com/mirrors/electron-builder-binaries/'
pnpm install
pnpm dist:win
```

## 常用检查

| 命令 | 内容 |
| --- | --- |
| `pnpm typecheck` | React 与 Electron TypeScript |
| `pnpm test:auth` | 注册、登录、资料锁定、并发与备份恢复 |
| `pnpm test:ai` | 人格提示、供应商/模型匹配、URL 白名单与限流 |
| `pnpm test:contracts` | UE5 Launcher Session JSON Schema |
| `pnpm test:assets` | GLB 与预览图格式、结构和体积门禁 |
| `pnpm test:secrets` | 密钥与开发机绝对路径检查 |
| `pnpm check` | 全部类型检查、测试和生产构建 |

## 本地数据

开发版和打包版固定使用同一目录：

```text
%APPDATA%/echoverse-launcher/
  accounts.json       本地账户和资料
  accounts.json.bak   上一个有效备份
  ai.json             仅开发使用的模型配置
  sessions/           短时 UE5 启动会话
```

测试只使用系统临时目录，不会清空真实账户。账户密码保存为随机盐与 `scrypt` 哈希，但现实资料仍是本机明文 JSON；拥有当前 Windows 用户文件权限的人仍可读取或篡改它，因此不能把本地账户库当作生产认证系统。

## AI 开发配置

将 `config/ai.example.json` 的结构复制到 `%APPDATA%/echoverse-launcher/ai.json`，再在本机填写开发密钥。不要把真实密钥放入仓库、截图、日志或发布包。当前配置只允许 DeepSeek/OpenAI 官方 HTTPS Origin，并验证 provider 与模型名称的兼容关系。

人格请求默认只发送完成聊天所需的有限信号：显示名、性别、职业、人格字段、兴趣、喜欢的颜色和音乐，以及有限的本次对话历史。真实姓名、精确生日、居住地和信仰保持在本地，尚未建立长期记忆。

正式发布前必须改为 EchoVerse 服务端 AI 网关，由后端托管密钥并实现认证、配额、费用限制、审计、同意、删除和数据保留策略。曾经暴露过的开发密钥也必须在发布前轮换。

## 接入 UE5 游戏

1. 将 `config/game.example.json` 复制为 `config/game.local.json`。
2. 填写 UE5 开发构建的绝对路径和可选参数。
3. 重启 Launcher，点击“启动游戏”。

游戏端要求见 [UE5 交接文档](docs/UE5_GAME_HANDOFF.md)，机器可读格式见 [Launcher Session Schema](contracts/launcher-session.schema.json)。`prototype-local` ticket 只允许开发联调，Shipping 构建必须拒绝。

## 工程文档

- [架构](docs/ARCHITECTURE.md)
- [工程审计](docs/ENGINEERING_AUDIT.md)
- [安全说明](SECURITY.md)
- [贡献规范](CONTRIBUTING.md)
- [发布检查表](docs/RELEASE_CHECKLIST.md)

提交和发布前请遵循 `CONTRIBUTING.md` 与发布检查表，不要把“内部原型可运行”描述为“生产可用”。
