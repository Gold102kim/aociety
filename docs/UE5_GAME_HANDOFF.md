# EchoVerse 启动器 ↔ UE5 游戏端交接文档

版本：Launcher Contract 1.0

适用范围：Windows UE5 客户端首次接入启动器

## 1. 游戏端必须预留的接口

游戏程序必须支持由启动器传入以下命令行参数：

```text
-LauncherSessionFile=<会话 JSON 的绝对路径>
-LauncherContractVersion=1.0
-LauncherLaunchId=<UUID>
```

UE5 启动后应在进入登录大厅之前读取这些参数。不要假设路径中没有空格或中文。

Blueprint 可使用 `Get Command Line` 获取完整参数；C++ 推荐使用：

```cpp
FString SessionFile;
FString ContractVersion;
FString LaunchId;

FParse::Value(FCommandLine::Get(), TEXT("LauncherSessionFile="), SessionFile);
FParse::Value(FCommandLine::Get(), TEXT("LauncherContractVersion="), ContractVersion);
FParse::Value(FCommandLine::Get(), TEXT("LauncherLaunchId="), LaunchId);
```

建议将解析和验证逻辑放入 `UGameInstanceSubsystem`，例如 `ULauncherSessionSubsystem`，保证切换地图后会话仍然存在。

## 2. 会话文件格式

格式的机器可读定义位于：`contracts/launcher-session.schema.json`。

示例：

```json
{
  "contractVersion": "1.0",
  "launchId": "20f2ea6e-898b-49dc-a37e-51c3f3722ce3",
  "issuedAt": "2026-07-15T08:00:00.000Z",
  "expiresAt": "2026-07-15T08:02:00.000Z",
  "launcher": {
    "version": "0.3.0",
    "platform": "win32",
    "locale": "zh-CN"
  },
  "account": {
    "accountId": "account-uuid",
    "displayName": "PlayerName"
  },
  "agent": {
    "agentId": "agent-uuid",
    "status": "READY",
    "profileVersion": 1,
    "baseModelId": "deepseek-v4-flash"
  },
  "auth": {
    "ticket": "一次性短期票据",
    "ticketType": "one-time-game-ticket",
    "exchangeUrl": "https://api.example.com/v1/game-session/exchange"
  },
  "game": {
    "channel": "development"
  }
}
```

读取后必须依次验证：

1. `contractVersion` 必须是游戏支持的版本，目前为 `1.0`。
2. 命令行的 `LauncherLaunchId` 必须与 JSON 内的 `launchId` 相同。
3. 当前 UTC 时间必须早于 `expiresAt`。
4. `accountId`、`ticket` 不得为空。
5. 文件读取完成后，不应长期在内存或日志中输出完整 `ticket`。

## 3. 正式认证流程

游戏端绝不能接收或保存平台账户的密码、Access Token 或 Refresh Token。启动器只向游戏交付有效期约 2 分钟且只能使用一次的 `game ticket`。

正式流程：

1. 启动器登录平台账户。
2. 启动器向账户后端申请一次性 `game ticket`。
3. 启动器生成会话 JSON 并启动 UE5。
4. UE5 读取 `ticket`，向 `auth.exchangeUrl` 发起 HTTPS `POST`。
5. 后端验证票据未使用、未过期、版本和渠道正确。
6. 后端返回游戏专用会话令牌及玩家基础资料。
7. 票据立即作废，游戏使用游戏会话令牌连接游戏服务。

建议请求：

```json
{
  "ticket": "ticket-from-launcher",
  "launchId": "uuid",
  "gameBuild": "0.1.0-dev",
  "contractVersion": "1.0"
}
```

建议成功响应：

```json
{
  "gameSessionToken": "short-lived-game-token",
  "expiresIn": 3600,
  "player": {
    "accountId": "account-uuid",
    "displayName": "PlayerName"
  }
}
```

当前启动器尚未接入云端账户后端，因此生成的 `prototype-local` 票据只能用于联调，不具备真实认证能力。UE5 开发版可以在明确标记为 Development 的构建中接受它，Shipping 构建必须拒绝。

## 4. UE5 启动状态与错误处理

游戏端至少需要区分以下状态：

- `NoLauncherArguments`：玩家绕过启动器直接运行游戏。
- `UnsupportedContractVersion`：契约版本不兼容。
- `SessionFileMissing`：会话文件不存在或无法读取。
- `SessionExpired`：会话文件已过期。
- `TicketExchangeFailed`：票据兑换失败。
- `Authenticated`：已取得游戏会话，可以进入主菜单。

开发版可允许 `NoLauncherArguments` 进入本地调试模式。正式发行版遇到前五项错误时，应显示清晰提示并提供“重新打开启动器”按钮，不应直接崩溃或无限重试。

## 5. 游戏打包交付给启动器端时需要提供

每次可运行版本请一并提供：

1. Windows 打包目录，不能只提供单个 `.exe`。
2. 主程序相对路径，例如 `Windows/EchoVerse.exe`。
3. 游戏版本号与渠道，例如 `0.1.0-dev`、`qa`、`release`。
4. 本版本支持的 Launcher Contract 版本列表。
5. 是否需要额外启动参数。
6. SHA-256 文件清单，后续用于启动器校验和更新。
7. 已知问题、最低系统要求和必要运行库。

启动器端收到版本后，将 `config/game.example.json` 复制为 `config/game.local.json`，填写实际的 `executablePath` 和 `workingDirectory` 即可联调。

## 6. 第一轮联调验收标准

- 从启动器点击“启动游戏”能够打开 UE5 客户端。
- 中文或带空格的安装路径可以正常工作。
- UE5 能读取账户 ID、显示名、语言和渠道。
- 过期或被修改的会话文件会被拒绝。
- 不支持的契约版本会给出明确错误。
- 游戏日志不会打印完整票据。
- 游戏关闭后可以再次从启动器正常启动。

## 7. 后续预留，不要求第一轮完成

- 游戏安装、增量更新、文件修复和版本回滚。
- UE5 向启动器报告下载、登录、排队和运行状态。
- 启动器好友在线状态与游戏邀请。
- 自定义 URL 协议，例如 `echoverse://join/<serverId>`。
- 崩溃报告、日志上传和跨进程遥测。
- 多环境切换：Development、QA、Staging、Production。
