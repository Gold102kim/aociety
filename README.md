# aociety · EchoVerse Launcher

## UE5 Aociety 游戏 Demo

仓库同时包含 UE5.8 森林小镇 Demo、DeepSeek 实时居民服务和硬件情感计算接口。游戏内有 Ecy 第三人称角色、两名自主漫游居民、NPC-NPC 对话与玩家按 `E` 交互；居民回复由 `deepseek-v4-flash` 实时生成，失败时明确显示 `source=error`，不会用固定台词冒充模型结果。

游戏、后端、Motion Matching、地图和验收说明见 [Aociety UE5 Demo](docs/AOCIETY_UE5_DEMO.md)。主动式情感关怀仍属于硬件端，游戏只提供场景、交互和必要的情绪上下文。

EchoVerse 的 Windows Electron 启动器工程。当前版本是可构建、可测试、可回滚的内部原型，重点是从对话开始建立自己的数字代表，覆盖账户入口、有限偏好记忆、主动保存待续内容、私密试答、世界/社交/虚拟分身页面、透明伴生模式，以及向 UE5 游戏交付启动会话的接口。

它还不是可公开运营的平台：账户仍保存在本机，AI 仍由开发机配置直连供应商，游戏票据仍是联调用原型。生产边界和阻断项见 [工程审计](docs/ENGINEERING_AUDIT.md) 与 [安全说明](SECURITY.md)。

## 公开源码与本机资源

本分支仅分发源码、配置模板、测试、文档和确认可分发的界面资源。角色模型、原始工程素材、UE 场景/角色二进制及测试音视频保留在本机，不随本次上传分发。来源与恢复说明见 [第三方资源](docs/THIRD_PARTY_ASSETS.md)。旧 Git 历史没有自动改写，不能把当前分支停止跟踪等同于历史已清除。

没有获授权的本机分身资源时，可明确使用源码模式完成检查和构建；页面会显示模型不可用的说明，不能将此构建当作包含全部游戏素材的完整游戏包：

```powershell
$env:ECHO_ALLOW_MISSING_LOCAL_ASSETS='1'
pnpm check
```

恢复模型和预览图后，取消该变量并运行默认严格资产检查。源码模式只允许二者同时缺失，存在但损坏或部分缺失仍然失败。UE 编辑器构建还需要 UE5.8 和受支持的 MSVC 工具链；静态契约测试不代替原生编译。

## 当前能力

- 软件启动后先进入注册/登录，登录成功前不能进入主界面。
- 注册只要求昵称、邮箱和密码，不要求填写人格问卷。登录后直接进入工作区，不再强制播放启动过渡；未填旧问卷的账户默认打开 AI 对话，已填旧问卷的账户保留首页入口。
- 旧版问卷资料保留在本机，可在个人页自愿补充；已填字段仍锁定。它不是开始聊天的条件，不会自动导入数字代表画像或附带于数字代表模型请求。
- 每个账户获得独立 Agent ID 和数字代表存储空间；基础模型服务可以被多个账户共享，并非每位玩家独占一套模型权重。
- 新账户的云端处理同意和偏好学习均默认关闭。本人独立同意云端处理后才能发送；学习另设关闭、只读、学习三种模式，可查看、纠正、忘记或重置有限偏好。
- 当前仅识别明确白名单表达中的回答长短和五类音乐偏好，不是通用语义画像。话题或草稿须主动保存，最多三条；私密试答不学习，参考答案和评分仅保留本轮。
- 临时模式不使用或新增长期画像，界面隐藏长期记忆和待续正文；退出后回读原资料，不删除原记录。停止生成保留当前临时模式及学习暂停保护。
- 日常聊天生成期间可直接“停止生成”，保留已发消息和未发送草稿；确认停止前暂停发送，取消失败可“重试停止”，晚到回复不再显示。停止不撤回已发给供应商的内容，也不撤销已经保存的偏好。
- 整页刷新或主渲染进程退出会结束本次登录并作废旧任务；重新登录读取原有资料和授权选择，不恢复聊天，也不恢复临时模式。
- 世界、社交、虚拟分身和个人主页具备基础内容与导航，退出登录位于个人主页。
- 提供获授权的本机 GLB 时，Three.js 可加载虚拟分身；页面隐藏时暂停渲染，伴生模式限制帧率，并支持 reduced-motion。源码和数字代表验收包不含受限人物模型；缺失或加载失败有说明和局部重试，不阻塞文字对话。
- 右上角菱形按钮可切换为透明无边框伴生窗口。
- 深色玻璃界面在导航和操作层提供局部背景折射、边缘高光与指针反馈，正文不变形；清晰、高对比和减少动态效果有相应降级。这是 Windows 上的网页实现，不是苹果原生 Liquid Glass，也未完成跨显卡性能认证。
- 退出或切换账户使未完成的登录、资料、AI 和游戏启动请求失效；取消 AI 会中止客户端 HTTP，不能保证供应商已经开始的计算或计费也随之停止。
- Launcher Session 通过版本化 JSON Schema 与 UE5 交接。

实施进度、已验证范围和未完成事项见 [数字代表开发记录](docs/DIGITAL_REPRESENTATIVE_PROGRESS.md) 与 [隐私及会话边界](docs/REPRESENTATIVE_PRIVACY_SESSION.md)。模拟测试不证明人格复刻、意识上传或用户留存提升。

## 工具链

- Windows 10/11 x64
- Node.js 24.4.x
- pnpm 11.9.x

首次安装：

```powershell
pnpm install --frozen-lockfile
node node_modules/electron/install.js
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

只验收数字代表和界面、明确排除角色模型与 UE 游戏时：

```powershell
pnpm dist:representative-local
```

该命令生成独立的 `release/representative-local-<timestamp>/` 目录，运行包内文件和敏感内容审查，不自动发布。产物未签名，仅供本机验收；当前校验值、账户备份要求及复现步骤见 [本机验收说明](docs/LOCAL_ACCEPTANCE.md)。不要同时运行共用本机数据的新旧版本，也不要将验收包作为完整游戏或公开运营版本上传。

如果中国大陆网络访问 GitHub Release 超时，可只对当前终端临时指定镜像后重试；Electron 与构建工具仍会按锁文件/内置校验值验证：

```powershell
$env:ELECTRON_MIRROR='https://npmmirror.com/mirrors/electron/'
$env:ELECTRON_BUILDER_BINARIES_MIRROR='https://npmmirror.com/mirrors/electron-builder-binaries/'
pnpm install
node node_modules/electron/install.js
pnpm dist:win
```

## 常用检查

| 命令 | 内容 |
| --- | --- |
| `pnpm typecheck` | React 与 Electron TypeScript |
| `pnpm test:auth` | 注册、登录、资料锁定、并发与备份恢复 |
| `pnpm test:ai` | 人格提示、供应商/模型匹配、URL 白名单与限流 |
| `pnpm test:representative` | 有限偏好、授权、加密存储、撤回与待续边界 |
| `pnpm test:simulation` | 私密试答配置、隐私版本与不学习约束 |
| `pnpm test:contracts` | UE5 Launcher Session JSON Schema |
| `pnpm test:assets` | GLB 与预览图格式、结构和体积门禁 |
| `pnpm test:secrets` | 密钥与开发机绝对路径检查 |
| `pnpm test:session` | 异步会话、游戏资源和 IPC 负向回归 |
| `pnpm test:package-policy` | 应用包路径、私有配置与模型二进制排除规则 |
| `pnpm test:ui` | 界面基础、辅助功能与玻璃光学逻辑 |
| `pnpm smoke:representative` | 可选隔离 Electron 界面回归；需已有 Playwright 环境 |
| `pnpm check` | 全部类型检查、测试和生产构建 |

可选桌面回归不在 `pnpm check` 内；先构建，再按 [本机验收说明](docs/LOCAL_ACCEPTANCE.md) 配置 Playwright 的 `NODE_PATH`，可针对源码或实际打包程序执行。它使用虚构账户、模拟模型传输与真实系统加密，不消耗真实模型额度。

Python 居民/硬件服务的隔离离线回归：

```powershell
python -m pip install -r requirements-resident.txt
python -B -m unittest discover -s tests -v
```

测试使用 mock 和临时目录，不需要真实 API Key，不调用付费模型。服务并发、关闭和可选旧助手的显式凭据共享边界见 [Python 审查](PYTHON_SERVICE_REVIEW.md)。

## 本地数据

开发版和打包版固定使用同一目录：

```text
%APPDATA%/echoverse-launcher/
  accounts.json       本地账户和资料
  accounts.json.bak   上一个有效备份
  ai.json             仅开发使用的模型配置
  representative/     每账户数字代表数据
    *.bin             系统加密的偏好、来源和主动保存的待续正文
    *.bin.privacy     不含来源/待续正文的隐私账本
  sessions/           短时 UE5 启动会话
```

测试只使用系统临时目录，不会清空真实账户。账户密码保存为随机盐与 `scrypt` 哈希；旧账户资料仍是本机明文 JSON，不能将本地账户库当作生产认证系统。

数字代表的有限偏好、短来源原文和主动保存的待续正文单独使用 Electron `safeStorage` 系统加密；隐私账本是明文版本、授权状态和随机条目标识，不含偏好值或正文，用于在异常恢复时阻止已撤回或已删内容重新生效。系统加密不可用时，不退回明文保存长期画像或待续内容。普通聊天历史不自动落盘；主动保存的话题或草稿是明确的例外。系统加密也不等于抵御已经控制当前 Windows 用户的程序。

## AI 开发配置

将 `config/ai.example.json` 的结构复制到 `%APPDATA%/echoverse-launcher/ai.json`，再在本机填写开发密钥。不要把真实密钥放入仓库、截图、日志或发布包。当前配置只允许 DeepSeek/OpenAI 官方 HTTPS Origin，并验证 provider 与模型名称的兼容关系。

数字代表对话及私密试答当前只支持 DeepSeek；底层服务仍保留 OpenAI 配置校验。模型配置不等于用户授权：未明确同意云端处理时，不发送对话或试答请求。普通对话发送昵称、当前输入、有限的本次历史，以及当前模式允许使用的有限偏好；不读取旧问卷字段来构造人格提示。学习关闭或临时模式不附带长期偏好；只读模式可使用已存偏好但不新增。

学习仅针对本人当前输入中符合白名单的明确表达；角色扮演、翻译、引用或恢复草稿等语境会暂停本次偏好学习，模型回复和历史消息不会作为画像证据。临时模式仍需独立云端授权，主进程仍会读取授权及加密状态；它不等于零磁盘读取、删除原资料或没有供应商处理。撤回授权、删除和会话变化会使不再有效的旧任务失效，但不能撤回供应商已收到的数据。

正式发布前必须改为 EchoVerse 服务端 AI 网关，由后端托管密钥并实现认证、配额、费用限制、审计、同意、删除和数据保留策略。曾经暴露过的开发密钥也必须在发布前轮换。

## 接入 UE5 游戏

本机首次配置：

```powershell
python -m venv runtime\aociety-python
runtime\aociety-python\Scripts\python.exe -m pip install -r requirements-resident.txt
pnpm configure:local-game
```

该命令会复用启动器本地 AI 配置，生成被 Git 忽略的 `.env`、`config/game.local.json` 和 `%APPDATA%/echoverse-launcher/game.json`。随后重启 Launcher，点击“进入游戏完善分身”。

当前开发入口使用 UnrealEditor 5.8 的 `-game` 模式。启动器会先检查并启动居民服务 `127.0.0.1:8000`，再把短时账户会话传入 UE。情感、TTS 和评估服务固定预留在 `127.0.0.1:8010`。

游戏端要求见 [UE5 交接文档](docs/UE5_GAME_HANDOFF.md)，机器可读格式见 [Launcher Session Schema](contracts/launcher-session.schema.json)。`prototype-local` ticket 只允许开发联调，Shipping 构建必须拒绝。

## 工程文档

- [0.6.1 安全维护与当前验收状态](docs/SECURITY_MAINTENANCE_20261027.md)
- [架构](docs/ARCHITECTURE.md)
- [工程审计](docs/ENGINEERING_AUDIT.md)
- [安全说明](SECURITY.md)
- [贡献规范](CONTRIBUTING.md)
- [发布检查表](docs/RELEASE_CHECKLIST.md)
- [数字代表开发记录与后续限制](docs/DIGITAL_REPRESENTATIVE_PROGRESS.md)
- [数字代表隐私与会话边界](docs/REPRESENTATIVE_PRIVACY_SESSION.md)
- [Apple 风格玻璃界面](docs/UI_APPLE_GLASS.md)
- [Liquid Glass 光学效果](docs/UI_LIQUID_GLASS.md)
- [Liquid Glass 交互与性能边界](docs/UI_LIQUID_GLASS_INTERACTION.md)
- [数字代表本机验收与复现](docs/LOCAL_ACCEPTANCE.md)

提交和发布前请遵循 `CONTRIBUTING.md` 与发布检查表，不要把“内部原型可运行”描述为“生产可用”。
