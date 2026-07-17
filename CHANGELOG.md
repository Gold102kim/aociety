# Changelog

All notable launcher changes are recorded here. The project follows semantic versioning for engineering baselines; a version number does not imply production readiness.

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
