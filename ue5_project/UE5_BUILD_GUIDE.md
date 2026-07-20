# UE5 项目启动与构建指南

## 项目结构
```
Aociety/
├── Aociety.uproject              # Unreal 项目文件
├── Source/                        # C++ 源码
│   ├── Aociety.Target.cs         # 主目标
│   ├── AocietyEditor.Target.cs   # 编辑器目标
│   └── Aociety/                  # 模块
│       ├── Aociety.Build.cs      # 依赖配置
│       ├── Public/                # 头文件
│       │   ├── Aociety.h
│       │   ├── AocietyClientSubsystem.h
│       │   ├── AocietyGameInstance.h
│       │   ├── AocietyGameMode.h
│       │   ├── CameraCaptureComponent.h
│       │   ├── MicCaptureComponent.h
│       │   └── TTSPlayer.h
│       └── Private/               # 实现
│           └── ...对应的 .cpp
├── Config/                        # 配置
│   ├── DefaultEngine.ini
│   ├── DefaultGame.ini
│   ├── DefaultEditor.ini
│   └── DefaultAociety.ini
└── Content/                       # UE资源
    ├── Maps/
    ├── UI/
    └── Audio/
```

## 第一次运行步骤

### 1. 下载/升级到 UE 5.8
打开 Epic Games Launcher → Unreal Engine → 安装版本 5.8.0+

### 2. 注册项目到引擎
打开 `Aociety.uproject` → 选择引擎版本 5.8 → 生成项目文件

或者手动:
```cmd
"C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\DotNET\UnrealBuildTool\UnrealBuildTool.exe" -projectfiles -project="%CD%\Aociety.uproject" -game -engine -progress
```

### 3. 编译 C++ 模块
```cmd
"C:\Program Files\Epic Games\UE_5.8\Engine\Build\BatchFiles\Build.bat" AocietyEditor Win64 Development -Project="%CD%\Aociety.uproject" -WaitMutex -FromMsBuild
```

### 4. 启动编辑器
```cmd
"C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe" "%CD%\Aociety.uproject"
```

## 必要的UE5插件

打开 `Edit → Plugins` 安装/启用:

| 插件 | 用途 |
|------|------|
| **OpenCV** | 摄像头采集（CameraCaptureComponent需要） |
| **WebSockets** | 实时双向通信（已默认启用） |
| **VaRest** (或JSON Blueprint Utilities) | 蓝图JSON处理 |
| **Audio Capture** | 麦克风录制 |

## 推荐UE版本

- 开发主版本：UE 5.8+
- 引擎要求 (EngineAssociation in uproject): `5.8`

## 一键打开项目

Windows 资源管理器里:
1. 右键点击 `Aociety.uproject`
2. 选择 "Generate Visual Studio Project Files"
3. 用 Visual Studio 打开生成的 `.sln`
4. 设置"AocietyEditor"为启动项目
5. 按 F5 编译+运行 UE5 编辑器

或者更简单:
```bash
start "" "C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe" "E:/Aociety-NEW/ue5_project/Aociety.uproject"
```

## 项目设置检查清单

打开 Project Settings → Maps & Modes:
- [x] Default Game Mode = AAocietyGameMode
- [x] Game Default Map = /Game/Maps/MainMap

Project Settings → Custom Settings → Aociety:
- [x] Default Backend URL = http://127.0.0.1:8000
- [x] Default Care Backend URL = http://127.0.0.1:8010
- [x] Default TTS Voice = xiaoxiao

## 默认蓝图继承

| 蓝图类 | 父类 |
|--------|------|
| BP_PlayerController | UAocietyPlayerController |
| BP_HUD | UAocietyHUD |

## 项目运行时依赖 (后端)

| 依赖 | 端口 | 作用 |
|------|------|------|
| Forest Resident Service | 8000 | 居民对话、世界、NPC |
| Hardware Care Backend | 8010 | 情感、TTS、评估、WebSocket |
| (可选) R1-Omni | 8001 | 本地情感推理 (如果不用GLM) |
| (可选) Arousal | 8002 | 本地唤醒度 |
| GLM 5.2 | Cloud | 主对话 + 情感推理 (tokenhub.market) |

启动后端:
```bash
start_full.bat
```

## 测试流程

1. 启动后端: `start_full.bat`
2. 启动UE5编辑器
3. 打开 Aociety.uproject
4. 按 Play 按钮
5. 在 Output Log 应该看到:
   ```
   [LogAociety] Subsystem initialized, backend=http://127.0.0.1:8000
   [LogAociety] WebSocket 连接成功
   ```
6. 角色应该开始推送摄像头帧和情感状态

## 已知限制 & 解决

1. **OpenCV UE插件未安装**:
   - 临时方案: 不使用CameraCaptureComponent，UE5自带的 ImageCapture 组件替代
   - 永久方案: 在 Marketplace 找 OpenCV UE 插件

2. **Windows Build Tools**:
   - 需要 VS 2022 Build Tools 或 VS 2019
   - 需要 Windows 10 SDK

3. **麦克风权限**:
   - Win10/11: 设置 → 隐私 → 麦克风 → 允许应用访问
