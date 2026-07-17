# 参与 EchoVerse Launcher 开发

感谢参与 EchoVerse。当前仓库是 Windows Electron 启动器原型；所有改动都应保持可重复构建、可验证和可回滚，并明确区分演示能力与生产能力。

## 开发环境

- Windows 10/11 x64
- Node.js 24.4.x（以 `.node-version` 和 `package.json#engines` 为准）
- pnpm 11.9.x（以 `packageManager` 为准）
- Git

不要使用 `latest` 绕过项目固定版本。工具链需要升级时，应在独立提交中同步修改版本约束、锁文件、CI 和发布验证记录。

## 首次安装

```powershell
git clone <repository-url>
cd aociety
pnpm install --frozen-lockfile
pnpm check
```

如果锁文件需要因依赖变更而更新，先修改 `package.json`，再执行正常的 `pnpm install`，审查 `pnpm-lock.yaml` 差异并在提交前重新运行 `pnpm check`。不要为了通过 CI 删除或手工改写锁文件。

## 常用命令

| 命令 | 用途 |
| --- | --- |
| `pnpm dev` | 启动 Vite 与 Electron 开发环境 |
| `pnpm typecheck` | 检查 React 与 Electron TypeScript |
| `pnpm test:auth` | 账户、资料不可变与并发写入回归测试 |
| `pnpm test:ai` | 人格提示、配置隔离和供应商适配测试 |
| `pnpm test:contracts` | Launcher Session JSON Schema 测试 |
| `pnpm test:assets` | 3D 模型与预览图门禁 |
| `pnpm test` | 运行全部模块测试 |
| `pnpm build` | 清理并生成生产前端与 Electron 代码 |
| `pnpm check` | 类型检查、测试和生产构建 |
| `pnpm dist:win` | 完整检查后生成 Windows portable 包 |

当前项目尚未配置统一 Lint/Format 命令。提交前应遵循现有 TypeScript/React 风格和 `.editorconfig`，并把引入 ESLint/Prettier 作为单独、可审查的工程变更。

## 分支与提交

- 从最新可用基线创建短生命周期分支，不直接在发布标签上工作。
- 一次提交只解决一个清晰问题；将依赖升级、大规模格式化和业务改动分开。
- 推荐提交前缀：`feat:`、`fix:`、`refactor:`、`test:`、`docs:`、`build:`、`chore:`。
- 不使用 `git reset --hard`、强制推送或覆盖他人未提交改动来整理历史。
- 提交前检查 `git status` 和 `git diff --check`，确认没有构建产物、账户数据或密钥。

## 代码边界

### React 与 Electron

- React 页面不得直接导入 `electron`、`node:*` 或访问文件系统。
- 新能力通过 `electron/preload.ts` 暴露具体业务方法，再由主进程实现。
- 禁止向页面暴露通用 `ipcRenderer.send/invoke`。
- 主进程必须验证发送窗口、顶层 Frame、可信 URL 和输入结构。
- 新窗口沿用沙箱、上下文隔离、关闭 Node 集成和默认拒绝导航/权限的策略。
- IPC 返回值使用可序列化、最小化的数据，不返回密钥、密码哈希、内部配置或供应商原始错误。

### 账户与资料

- 不在测试中使用真实账户库；测试必须创建系统临时目录并在结束时清理。
- 已首次保存的非空现实资料不可修改，空白字段可补充。新增入口必须复用领域层规则，不能只在 UI 禁用输入框。
- 修改账户结构时增加数据库版本迁移、旧数据夹具、失败回滚和备份恢复测试。
- 邮箱唯一性和并发一致性必须有回归测试；生产版一致性由服务端数据库事务保证。
- 每账户拥有独立 Agent 档案，但基础模型是共享服务；字段和文案不得暗示独占模型实例。

### AI

- 任何测试密钥只能使用不可访问真实服务的假值。
- 不读取通用的开发环境凭据；仅使用 EchoVerse 明确命名的配置入口。
- 新 provider 必须有 URL、模型兼容、错误、超时和响应解析测试。
- 不扩大个人资料发送范围，除非同时完成产品同意、隐私评审和文档更新。
- 生产设计必须通过服务端 AI 网关，客户端直连只允许本地原型。

### 游戏契约

- `contracts/launcher-session.schema.json` 是 Launcher 与 UE5 的机器可读契约。
- 向后兼容的可选字段可以在同一版本演进；改变必填字段语义或删除字段必须升级 `contractVersion`。
- 契约变更必须同时更新 `scripts/test-contracts.cjs`、`docs/UE5_GAME_HANDOFF.md` 和游戏端交接示例。
- Shipping 游戏不得接受 `prototype-local` ticket。

### 3D 资产

- 资产必须有明确来源、授权和允许分发的许可记录。
- GLB 和预览图放在 `public/models/`，不要把 Blender 临时缓存或未用贴图提交进运行包。
- 替换资产前运行 `pnpm test:assets`，并在目标低端机器检查加载时间、内存、帧率、透明模式和资源释放。
- 超过现有预算的资产需要书面说明和性能验证，不能仅提高门禁阈值。

## 配置与本地数据

- 可提交：`config/*.example.json`，内容只含占位符和说明。
- 不可提交：`config/*.local.json`、`userData/ai.json`、`accounts.json*`、`sessions/*.json`。
- 不把开发机绝对路径写入源码、示例或测试快照。
- 不清空真实账户数据作为测试准备；使用临时用户数据目录或专用测试账户。
- 构建前运行清理命令，避免旧哈希资源混入 `dist` 或安装包。

## 测试要求

每个修复至少包含能够在修复前失败、修复后通过的回归验证。根据改动范围选择：

- 纯函数和领域规则：模块测试；
- IPC/窗口安全：主进程负向测试和桌面冒烟测试；
- 用户流程：注册、登录、首次资料、补充、退出和重启后的 E2E；
- 外部服务：本地 mock，覆盖成功、超时、429、5xx、非法响应和取消；
- 3D/伴生模式：人工视觉验证加性能记录；
- UE5 契约：JSON Schema 测试加双方联调记录。

测试不得访问真实模型服务、消耗真实额度或依赖开发者个人配置。

## Pull Request 清单

- [ ] 变更目的、范围和用户影响说明清楚。
- [ ] 未混入无关格式化、生成文件或其他人的工作。
- [ ] `pnpm check` 在本机通过。
- [ ] 相关回归测试已新增或更新。
- [ ] 未提交密钥、账户资料、聊天内容、本机路径或发布产物。
- [ ] IPC、外部网络、个人数据和游戏票据变更完成安全评审。
- [ ] 架构、契约、交接或用户行为变化已更新文档。
- [ ] UI 改动验证了 1120×720 最小窗口、常用缩放、键盘操作和可读性。
- [ ] 说明了迁移、兼容、回滚和已知限制。

## 发布改动

普通 PR 不应自行宣布“生产可用”。发布负责人必须按照 `docs/RELEASE_CHECKLIST.md` 从干净提交生成产物，记录 Git 提交、测试结果、SHA-256、签名状态和回滚点。
