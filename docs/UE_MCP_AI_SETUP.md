# UE 5.8 MCP 与 AI 开发配置

## 当前结构

- UE 编辑器启用 `ModelContextProtocol`、`MCPClientToolset` 与 `AIAssistant`。
- UE MCP 服务地址为 `http://127.0.0.1:8181/mcp`。
- Codex 作为外部 MCP 客户端连接 UE；UE 5.8 当前没有独立命名为 `GPT` 或 `Codex` 的 `.uplugin`。
- 普通玩家从软件启动游戏时会禁用上述开发插件，避免增加游戏启动负担。
- 编辑器默认不自动启动 MCP 服务；需要远程调试时由开发者主动启用，仅允许可信客户端访问。

## Codex 配置

本机已执行：

```powershell
codex mcp add unreal_engine --url http://127.0.0.1:8181/mcp
```

检查配置：

```powershell
codex mcp get unreal_engine
```

新增 MCP 后需要重启 Codex 或开启新任务，使客户端重新加载全局配置。

## UE 编辑器配置

项目的 `DefaultEditorPerProjectUserSettings.ini` 已设置：

```ini
[/Script/ModelContextProtocolEngine.ModelContextProtocolSettings]
bAutoStartServer=False
ServerPortNumber=8181
ServerUrlPath=/mcp
bEnableToolSearch=True
```

需要使用 MCP 时，在 UE 编辑器 Project Settings → Plugins → Model Context
Protocol 中主动启用服务/自动启动，并重启编辑器。该选择应保存在本机配置；不要
为了个人调试把仓库的默认设置改回自动启动。停止使用时关闭服务。

仅在主动启用后打开 `Aociety.uproject`，日志才应包含：

```text
Starting MCP server on port 8181
Created new HttpListener on 127.0.0.1:8181
```

首次启用部分 UE 开发插件时，编辑器可能安装 Python 依赖并导致初始化较慢。只验证 MCP 服务时可临时用 `-DisablePython` 启动编辑器；正常需要 Python 编辑能力时不要添加该参数。

## 运行边界

- 编辑器开发：启用 MCP、AI Assistant 和工具集。
- 软件启动游戏：启动参数包含 `-DisablePlugins=AIAssistant,MCPClientToolset,ModelContextProtocol`。
- 不把任何模型 API Key 写入仓库、`.uproject` 或 UE 配置文件。
- UE MCP 日志会提示相关数据受 UE EULA 条款约束，连接模型服务前应确认数据使用政策。
