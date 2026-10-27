# 0.6.0 依赖安全审计

以下保留 2026-10-14 的历史验证结果。2026-10-27 新披露告警、0.6.1 补丁及重新验证见 [安全维护记录](SECURITY_MAINTENANCE_20261027.md)，不能将旧结果当作当前安全保证。

验证日期：2026-10-14。此次仅将 Electron 直接依赖从固定 `43.1.1` 升到固定 `43.5.0`，其余直接依赖保持既有精确版本。应用版本为 `0.6.0`，未修改全局 Node.js、pnpm、注册表或安装 MSVC。

## 审计结果

初始 npm 审计报告有 84 项漏洞，其中 1 项 critical、50 项 high。先执行兼容范围内的正常更新与定向传递依赖更新，再为仍被选中的旧版本添加小范围覆盖。最终结果：

| 等级 | 最终数量 |
| --- | ---: |
| Critical | 0 |
| High | 0 |
| Moderate | 1 |
| Low / Info | 0 |

`pnpm audit --audit-level high --json --registry=https://registry.npmjs.org` 实际退出码为 `0`。没有忽略任何 advisory，也没有以高等级阈值掩盖下述 moderate 遗留风险。审计只反映当时数据库中的已知依赖问题，不等于软件已无安全风险。

## 最小覆盖

全部目标精确版本和 integrity 均通过官方 npm registry 元数据验证。兼容范围更新已解决 axios、fast-uri、joi、nanoid、postcss、source-map-js 和 undici 7 的已知问题；没有使用 `--latest` 泛升级。正常与定向更新仍选择旧版本的九项覆盖写在 `pnpm-workspace.yaml`：

| 选择器 | 固定修复版本 | 原因 |
| --- | --- | --- |
| `concurrently@10.0.3>shell-quote` | `1.11.0` | 上游精确固定旧版；修复命令注入和解析 DoS |
| `@xmldom/xmldom@0.8` | `0.8.15` | plist 的 XML 注入、CPU 和内存消耗修复 |
| `brace-expansion@1` | `1.1.21` | 保留旧 minimatch 所需的 1.x API；修复膨胀和递归 DoS |
| `brace-expansion@2` | `2.1.7` | 保留 minimatch 所需的 2.x API |
| `brace-expansion@5` | `5.0.12` | 保留新 minimatch 所需的 5.x API |
| `http-cache-semantics@4` | `4.3.0` | 修复跨用户缓存响应泄露 |
| `js-yaml@4` | `4.3.2` | 修复解析器 CPU 消耗和 merge 限额绕过 |
| `tar@7` | `7.5.21` | 修复成员选择中的不可捕获递归耗尽 |
| `undici@6` | `6.28.1` | 修复 WebSocket 子协议 DoS；不覆盖已正常更新的 7.x |

后续维护应逐项检查上游是否已采用安全版本，再解除相应覆盖；不要统一跨 major 替换。锁文件由正常 `pnpm install` 生成，没有手工编辑。

## 唯一遗留 advisory

[`GHSA-hp3w-g68c-fv3c`](https://github.com/advisories/GHSA-hp3w-g68c-fv3c)：`sprintf-js <=1.1.3` 的无界精度格式化 DoS，等级 moderate，npm 审计未提供 patched version。

实际路径为 `electron-builder → app-builder-lib → @electron/get → global-agent → roarr → sprintf-js`，另有 `dmg-builder → app-builder-lib` 的相同分支。审计将其标为开发依赖、可选依赖、非 bundled；项目发布文件仅包括生产前端、Electron 编译代码及 `package.json`，运行代码不直接引入这一构建日志分支。

该问题保留在报告中，不用不存在的版本或无依据的 API 替换绕过审计。构建工具仍应仅处理可信配置、下载来源和格式字符串，不能把“不进入运行包”当成无需防护。

## Electron 二进制与验证

Electron `43.5.0` 的[官方发布记录](https://releases.electronjs.org/release/v43.5.0)包含 Chromium `150.0.7871.250` 和内嵌 Node.js `24.19.0`。本次不仅修改 npm 版本：物理 `node_modules/electron/dist/version` 为 `43.5.0`，`electron.exe --version` 实际返回 `v43.5.0`。

该 npm 包不再提供自动安装二进制的 postinstall，构建 portable 前必须显式执行：

```powershell
pnpm install --frozen-lockfile
node node_modules/electron/install.js
pnpm check
pnpm audit --audit-level high
```

本机 Node 直连 GitHub 超时，使用 Windows HTTP 从同一个官方 GitHub release 下载 ZIP，验证 npm 包内置的官方 SHA-256，再由未修改的官方 installer 从本地 cache 解压。未使用第三方镜像、跳过校验或关闭 TLS 校验。`electron-v43.5.0-win32-x64.zip` 的验证值为：

```text
1fc131e62cafa02f0c94b5ec730c4eb1e8ce75e5f5b84f3c52a3443d86058184
```

本机 `pnpm check` 完整通过，包括新增 session、secret-scanner、asset-policy 回归及原有所有测试；默认严格资产模式使用仍在本机的授权资产，没有放宽门禁。生产构建为 10 个前端资源，初始 JS 为 `209.1 KiB`。`pnpm install --frozen-lockfile --ignore-scripts --offline` 也通过，用于验证本地 store 中的锁文件一致性，不替代上述 Electron 二进制安装。

初次验证工具为 Node.js `24.4.1`、宿主提供的 pnpm `11.25.0`，符合 `engines` 范围。收尾另外从官方 npm 下载项目固定 `pnpm@11.9.0` 到临时工具缓存，冻结离线安装及完整 `pnpm check` 也实际通过；没有替换全局工具。纯源码副本已成功打包 portable 并检查 ASAR 分发清单，详见 [整体验证](PROJECT_REVIEW_0.6.0.md)。此记录不声明尚未运行的 GitHub CI、代码签名或完整游戏验收已通过。
