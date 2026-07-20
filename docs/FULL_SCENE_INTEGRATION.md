# 完整场景分支综合说明

## 来源

- GitHub 分支：`codex/aociety-full-2026-07-20`
- 分支头提交：`daf0045`
- 扩展城市场景提交：`812df03`

## 已综合内容

- 完整扩展地图原文件与场景生成脚本。
- 动态昼夜、天气、雾、天空光和夜间灯光。
- 世界碰撞边界。
- 游戏内暂停、返回主菜单和退出功能。
- Motion Matching 步幅校正代码及更新后的运动资源。
- 软件启动、主菜单、玩家会话和 DeepSeek 居民交互链路。

## 外部资源缺失

扩展地图引用以下 Marketplace 内容，但这些资源没有上传到 GitHub：

- `/Game/Modular_Rural_Cabin/...`
- `/Game/MagicTown/...`
- `/Game/Ophiopogon_japonicus_Nanite_Free/...`

因此默认运行不直接加载扩展地图。原地图保存在：

```text
SourceAssets/ImportedScene/Aociety_ForestSnowTown_Expanded.umap
```

生成脚本保存在：

```text
ue5_project/Content/Python/expand_forest_city.py
```

## 当前运行策略

- Marketplace 资源存在：使用原场景资源。
- Marketplace 资源缺失：自动生成只依赖 UE 基础形状的城镇回退，保证场景可见、可移动、可交互。
- Motion Matching 资源仍缺少有效 Skeleton，默认关闭；修复后可添加 `-AocietyEnableMotionMatching` 验证。
