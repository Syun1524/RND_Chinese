# LanguageBarrier —— ROBOTICS;NOTES DaSH 简体中文汉化专用改版

**这是 fork，不是上游原件。**

| | |
|---|---|
| **用途** | [ROBOTICS;NOTES DaSH](https://store.steampowered.com/app/1111390/)（MAGES/5pb）**简体中文汉化补丁**的运行时 |
| **汉化项目** | [Syun1524/RND_Chinese](https://github.com/Syun1524/RND_Chinese) |
| **fork 自** | [CommitteeOfZero/LanguageBarrier](https://github.com/CommitteeOfZero/LanguageBarrier) |
| **基准提交** | `cc982fd9`（2025-04-27） |
| **本分支** | `rnd-chinese` |
| **改动规模** | **13 个文件，+1667 / −1064 行** |

上游 LanguageBarrier 是 CoZ 为 MAGES 引擎游戏做**英化**补丁的运行时内核
（hook 大量游戏函数，实现资源重定向、渲染改动等）。本项目在其上加入
**中文**支持，其余保持原样。

**若你的目标是英化补丁，请用 [上游仓库](https://github.com/CommitteeOfZero/LanguageBarrier)。**

## 改了什么

`git diff cc982fd9` 即完整改动集，细节见 **[FORK-NOTES.md](FORK-NOTES.md)**。
主要方向：

| 方向 | 内容 |
|---|---|
| **中文渲染基础设施** | `forceIncludeHan`（中文码表必须全烘汉字）、`charsetHash` 缓存指纹、`missingGlyph` 兜底、`loadCache` 语言校验跟随 `forceIncludeHan` |
| **排版修复** | ruby 注音精确定位、backlog 名字右对齐、CJK 逐字断行 + 行首禁则、引号按半角步进绘制 |
| **界面 / 资源** | `fileIdRemap`（换装）、`fileRedirection` 按语言选图集、`windowTitle` 改写、SigScan 多版本兼容 |

## 构建

```
cd LanguageBarrier
build_lb.bat        # 需要 MSVC v142 + vcpkg（x86-windows-static）
```

产物为 `dinput8-Release/dinput8.dll`。

## 尚未跟进上游

上游在本 fork 的基准之后新增了 `Hooking.*` / `NewHooks.*` / `ScriptDebugger.*` /
`cryptbase.*` 等文件（一次大重构）。**本 fork 尚未合并**，那批改动与中文汉化
无关，合并需单独评估。

## 许可

MIT 许可与版权声明原样保留（见 [LanguageBarrier/LICENSE](LanguageBarrier/LICENSE)）。
因含 xy-VSFilter，二进制按 GPLv2 分发。

---

## 附：上游 LanguageBarrier 简介

> 以下摘自上游 README，供了解这个项目的全貌。

This is the core runtime component for Committee of Zero's MAGES engine game patches,
hooking lots of game engine functions to enable asset access redirection at filesystem
and higher levels, rendering changes and many more features.

As we try to support all games and any possible patches with a single binary, extensive
external configuration is required (in particular, the hooks here make little sense the
signatures pointing to their targets). See the root patch repositories (or patched game
installations) for details.
