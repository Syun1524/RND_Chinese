# FORK-NOTES —— ROBOTICS;NOTES DaSH 简体中文汉化专用改版

**本目录（`LanguageBarrier_chs/`）是为机器人笔记 DaSH 汉化改过的版本，不是上游原件。**

| | |
|---|---|
| **用途** | **ROBOTICS;NOTES DaSH**（MAGES/5pb，Steam 版）**简体中文汉化补丁**的运行时 |
| **汉化项目** | [Syun1524/RND_Chinese](https://github.com/Syun1524/RND_Chinese) |
| **fork 自** | [CommitteeOfZero/LanguageBarrier](https://github.com/CommitteeOfZero/LanguageBarrier) |
| **基准提交** | `cc982fd9`（2025-04-27，"Fix time stamp rendering"） |
| **本分支** | `rnd-chinese` |
| **改动规模** | **13 个文件，+1667 / −1064 行** |

- 独立 fork 仓库：<https://github.com/Kurashift/LanguageBarrier_chs>（分支 `rnd-chinese`）
- `git diff cc982fd9` 即为本项目的完整改动集
- **上游原件请用 [CommitteeOfZero 的仓库](https://github.com/CommitteeOfZero/LanguageBarrier)**。
  本 fork 服务中文汉化，不保证与上游同步

> 上游此后新增了 `Hooking.*` / `NewHooks.*` / `ScriptDebugger.*` / `cryptbase.*`
> 等文件（大重构），**本 fork 尚未跟进**；那批改动与中文汉化无关，合并需单独评估。

## 改了什么

主要方向（按文件）：

| 文件 | 内容 |
|---|---|
| `GameText.cpp/.h` | 改动最大。中文码表/字体渲染（`forceIncludeHan`、`charsetHash` 缓存指纹、`missingGlyph` 兜底）、ruby 注音定位、backlog 名字右对齐、CJK 逐字断行与行首禁则、引号收窄、邮件/EXTRA 界面位移表 |
| `TextRendering.cpp/.h` | 中文码表相关的字形烘焙与缓存校验；`loadCache` 的语言校验改为跟随 `forceIncludeHan` |
| `Game.cpp/.h` | `fileIdRemap` 分支（换装）、`windowTitle`、`fileRedirection` 对象形式（按语言选图集） |
| `SigScan.cpp` | `pattern` 支持字符串数组逐个回退 + `occurrence`（一个 gamedef 兼容多个游戏版本） |
| `CustomInputRND.cpp` | 标题菜单鼠标悬停/点击宽度跟随中文图集 |
| `CriManaMod.cpp` | 影片字幕（中文卡拉OK + 翻译轨）相关调整 |
| `LanguageBarrier.vcxproj` | 构建配置（新增 `RubyBaseTable.inc` 等） |

`RubyBaseTable.inc` 是**生成文件**（由汉化仓库的 `scripts/gen_ruby_base_table.py`
从已部署 enscript 提取），用于对话框注音的水平定位。

## 构建

```
cd LanguageBarrier
build_lb.bat        # 需要 MSVC v142 + vcpkg（x86-windows-static）
```

产物为 `dinput8-Release/dinput8.dll`。

## 许可

沿用上游 MIT 许可，版权声明见 `LanguageBarrier/LICENSE`（原样保留）。
