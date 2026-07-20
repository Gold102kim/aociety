# Changelog

## Unreleased

- 修复开发版游戏启动黑屏：启动 UnrealEditor 游戏模式时禁用 Python 初始化，避免自动 pip 安装阻塞地图加载。
- 强制初始化玩家相机，并在损坏的 Motion Matching 资源修复前启用安全回退，避免动画构建错误阻塞画面。
- 强化启动冒烟测试：必须确认地图完成加载、玩家 ViewTarget 生效，并支持游戏内截图审计。

All notable launcher changes are recorded here. The project follows semantic versioning for engineering baselines; a version number does not imply production readiness.

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
