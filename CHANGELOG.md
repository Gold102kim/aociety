# Changelog

## Unreleased

- 综合完整场景分支：加入动态昼夜与天气、夜间灯光、世界边界、游戏内暂停菜单和运动资源更新。
- 完整地图缺少未上传的 Marketplace 依赖；保存原始扩展地图，并增加 UE 基础形状城镇回退，正常运行不再出现白色空场景或资源加载错误。
- Motion Matching 资源仍缺少有效 Skeleton，默认保持安全回退；可在资源修复后用 `-AocietyEnableMotionMatching` 开启验证。
- 新增 UE 原生主菜单：启动器先进入主菜单，再由“进入世界”加载森林场景。
- 启用 UE 5.8 官方 MCP、MCP Client Toolset 与 AI Assistant 编辑器插件；运行游戏时禁用开发插件，避免拖慢启动。
- 修复开发版游戏启动黑屏：启动 UnrealEditor 游戏模式时禁用 Python 初始化，避免自动 pip 安装阻塞地图加载。
- 强制初始化玩家相机，并在损坏的 Motion Matching 资源修复前启用安全回退，避免动画构建错误阻塞画面。
- 强化启动冒烟测试：必须确认地图完成加载、玩家 ViewTarget 生效，并支持游戏内截图审计。

All notable launcher changes are recorded here. The project follows semantic versioning for engineering baselines; a version number does not imply production readiness.

## [0.6.1] - 2026-10-27

- 针对新披露告警，更新 Electron 43.8.1、Vite 8.1.6、undici 6.29.1/7.30.1 与 fast-uri 3.1.9，保留同主版本 API。
- 本地打包先执行高危审计；包审查核对项目锁定版本、已安装 npm 元数据和两个实际 Electron EXE，拒绝旧内核或失败探测。
- 本轮验收包含此前源码中的隐私操作失败提示与重置确认修复，不改变玻璃外观、画像采集或账户结构。最新验证状态见 `docs/SECURITY_MAINTENANCE_20261027.md`，版本号不代表已完成生产发布。

## [0.6.0] - 2026-10-14

- 修复登录/退出/切换账户时的异步旧结果、伴生窗口资料残留，以及 AI 取消后占用或误释放新请求槽的问题。
- 游戏启动中退出会同步清理本次尚未交付的服务和会话，不误杀原有服务或已经交付的游戏。
- Python 模型请求禁用隐式重试，限制积压；阻塞硬件分析移出事件循环，关闭应用时释放资源；模型错误不回显上游原文。
- 旧 OpenClaw 助手不再隐式复制桌面登录或扫描全局账户状态，跨应用共享需显式选择。
- UE 请求统一 JSON 序列化、超时、数量限制和卸载取消；会话记录按账户/Agent 隔离，Shipping 在真实票据交换实现前拒绝本地票据。
- 居民模型上下文按随机游戏会话隔离、限量保存，旧客户端无作用域时不保留历史；UE 拒绝缺少显式模型/来源/路由信息的响应。
- Electron 升级至 43.5.0，锁文件及同主版本安全补丁消除全部已审计的严重/高风险项；保留无官方修复的构建工具中风险记录，不隐藏告警。
- 公开源码排除未经确认可分发的模型/场景和音视频，本机文件保留；新增缺失资产策略、敏感扫描器与会话负向测试。
- CI 审计全部依赖并运行离线 Python 回归；明确区分源码原型构建与完整游戏验收。UE C++ 原生编译仍待支持的 MSVC 环境。

## [0.5.1] - 2026-10-14

- 增加 iOS 风格深色玻璃材质：悬浮圆角侧栏、半透明卡片、静态光晕、高光细边和胶囊按钮。
- 标题栏提供“玻璃 / 清晰”切换并保存非敏感外观偏好；支持系统减少透明度、增强对比度与强制颜色回退。
- 3D 分身、聊天消息区不使用玻璃模糊；移除嵌套的旧模糊和分身装饰动画，保留原渲染预算及功能。
- 增加外观偏好容错与材质回退回归测试。

## [0.5.0] - 2026-10-14

- 重设计首页：欢迎区、森林小镇概念插画、游戏入口和三个真实可用的快捷入口，移除无交互新闻和模拟动态。
- 统一深色界面、间距、圆角、中文字体、按钮与焦点状态；保留账户偏好颜色及低动态模式。
- 侧栏新增直接 AI 对话入口，分身外观页同时展示性格信息和聊天入口。
- 聊天输入框固定在窗口内，消息与侧栏分别滚动；清空对话需确认，建议填入后自动聚焦。
- 使用 Canva 生成视觉方向板，Figma 创建可编辑的首页、聊天页、变量和组件参考稿。
- DeepSeek、账户数据、游戏配置和伴生渲染逻辑保持不变。

## [0.4.2] - 2026-10-14

- 登录首屏不再提前载入主页、世界、社交、档案和伴生页面；增加页面加载与失败反馈。
- 老账户登录过渡缩短到 650 毫秒，首次资料完成后保留完整过渡；过渡期间预加载主页。
- AI 对话支持 Ctrl+Enter 发送和失败重试，重试不重复插入玩家消息；中文输入法组合期间不触发快捷发送。
- 在发送到主进程前裁剪最近 12 条上下文，与既有模型上下文预算一致；界面记录仍保留。
- 首页“查看详情”可打开世界页面，世界页启动按钮显示忙碌状态，设置和下载入口提供当前功能说明。
- 增加首屏 225 KiB 预算、页面分包与聊天快捷键/上下文回归检查。模型服务保持 DeepSeek。

## [0.4.1] - 2026-10-14

- 分身预览与伴生模式统一限制到最高 30 FPS；不可见或卸载时停止渲染调度，模型加载期间不再空转。
- 本次登录期间切换页面保留 AI 聊天记录、草稿及正在等待的回复；退出登录后清空。
- 新消息自动跟随到底部；阅读较早消息时保留滚动位置。
- 游戏服务退出时立即中断健康检查，并限制探测总时长；主进程阻止并发启动。
- 会话文件创建失败时正确清理本次启动的服务。
- 增加渲染调度及服务异常退出、超时、成功启动的回归测试。

## [0.4.0] - 2026-07-20

### Added

- Launcher-managed resident service startup and health checks before opening the game.
- Local setup command for UnrealEditor, the isolated Python runtime and ignored machine configuration.
- UE Launcher Contract 1.0 parsing with expiry, launch ID, account and Agent validation.
- Game integration regression checks and a local UE runtime smoke test.

### Changed

- Split UE networking into resident/world port `8000` and hardware care/TTS/assessment port `8010`.
- Aligned hardware helper scripts and OpenClaw fallback port defaults.
- Made Windows build cleanup resilient to Desktop filesystem filters.
- Explicitly pass the forest map when launching UnrealEditor game mode to avoid an empty `Untitled` world.

## [0.3.0] - 2026-07-17

### Added

- Reproducible Node/pnpm toolchain, Windows CI, dependency update configuration and portable Electron Builder packaging.
- Contract, 3D asset, sensitive-material, account concurrency and AI provider regression checks.
- Windows application icon, release checksum generation and structured local diagnostic logs.
- Engineering audit, architecture, security, contribution and release documentation.

### Changed

- Clarified that accounts receive an independent Agent profile while sharing a base model service.
- Minimized profile fields sent to the model provider.
- Split the renderer into maintainable page and component modules.
- Stabilized the user data directory across development and packaged builds.

### Fixed

- Concurrent registrations could report success while silently losing one account.
- Invalid calendar dates could be stored.
- Account database corruption had no valid-backup fallback.
- Electron IPC, navigation, permissions and window controls trusted too broad a renderer boundary.
- OpenAI-compatible requests could receive a DeepSeek model identifier.
- AI requests lacked per-account concurrency/rate limits and provider URL allowlists.
- The 3D viewport leaked resources, rendered while hidden and overwrote its centered pose.
- Chat clearing, toast timers and lazy-render failures could leave inconsistent UI state.

## [0.2.0] - 2026-07-17

- Prototype milestone containing local accounts, first profile flow, DeepSeek persona chat, the temporary `ecy` avatar and companion mode.
