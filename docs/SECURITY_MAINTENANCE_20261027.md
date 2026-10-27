# 0.6.1 安全维护与验收

日期：2026-10-27。继续数字代表本机验收，不扩展画像采集、界面材质或模型能力。

## 为什么先处理安全维护

上次源码提交 `2fbf9f6b9e4b9108b4c6487a96feb5e34aa07d9b` 的 [GitHub CI](https://github.com/Gold102kim/aociety/actions/runs/38737687418) 已完成且成功。但今天重新审计相同锁文件，结果为 4 高危、12 中危、6 低危、0 严重。历史 CI 成功不保证新披露漏洞已被处理。

本次并行启动的旧依赖构建 `release/representative-local-20261027T104610Z` 只保留用于追溯，已标注不交付；没有复制到 E 盘或公开发布。后续使用新时间戳目录，不覆盖旧版。

## 最小补丁

| 依赖 | 原版本 | 本次版本 | 官方依据 |
| --- | --- | --- | --- |
| Electron | 43.5.0 | 43.8.1 | [受损中间证书缓解](https://github.com/electron/electron/security/advisories/GHSA-jr5w-w6x2-84p9) |
| Vite | 8.1.5 | 8.1.6 | [Windows 编辑器启动边界](https://github.com/vitejs/launch-editor/security/advisories/GHSA-587h-7wmj-h5pm) |
| undici 6 | 6.28.1 | 6.29.1 | [过量内容编码处理](https://github.com/nodejs/undici/security/advisories/GHSA-xjj6-f33q-929c) |
| undici 7 | 7.30.0 | 7.30.1 | 同上 |
| fast-uri | 3.1.8 | 3.1.9 | [官方安全告警](https://github.com/advisories/GHSA-w74x-v6f9-j3xg)及同批解析问题 |

只修改两项直接依赖和已有 undici 6 覆盖，定向更新 undici/fast-uri 传递依赖；不使用 `--latest`，不添加产品依赖，不手工编辑锁文件。应用补丁版本升至 0.6.1，以区别此前 0.6.0 验收包。全局 Node.js、pnpm 和系统证书配置未修改。

## 不能只看 npm 版本

包审查先验证已安装 Electron npm 元数据等于项目精确 pin，再分别读取安装目录与打包目录实际 EXE 的 `process.versions.electron`。版本探测使用 RunAsNode，不启动正常应用，不加载继承的 `NODE_OPTIONS`；限制为 5 秒和 1 KiB 输出，失败或不匹配即拒绝验收。回归覆盖旧版本、空输出、异常退出及超时。

两种本地打包入口均新增高危审计前置门禁，顺序固定为审计、完整检查、打包；断网或审计失败不能当作通过。没有忽略 advisory 或降低严重性阈值。

## 当前验证状态

- 补丁后完整 `pnpm audit --audit-level low --json` 实际返回所有级别 0 项。这只表示当时漏洞库中的已知告警，不能解释为软件绝对安全。
- 旧 `sprintf-js` 告警已由上游于 2026-10-22 [撤回](https://github.com/advisories/GHSA-hp3w-g68c-fv3c)，不是本项目修好了该库；历史审计记录保留，不改写旧结果。
- `pnpm check` 完整通过，包括类型、隐私/会话、包策略、玻璃及生产构建；首屏 JavaScript 210.1 KiB，预算 225 KiB。`pnpm install --frozen-lockfile --offline` 通过，未重写锁文件。
- 实际 Electron 二进制仍待下载验证，新包和打包窗口回归尚未通过。GitHub 直连与备用下载尝试未完成时，不回退到旧内核、不跳过 TLS 或官方 SHA-256 校验，不将源码检查当作运行验收。

## 不变的边界

不访问或修改真实账户、聊天、模型密钥及原始素材；回归仅使用隔离账户和模拟模型传输，不产生付费调用。包内排除受限模型、UE 游戏、凭据和测试夹具。不改 `main`，不强推或改写历史，不自动发布 GitHub Release。既有旧包、旧历史素材和已暴露密钥的清理轮换不由本次维护自动完成。
