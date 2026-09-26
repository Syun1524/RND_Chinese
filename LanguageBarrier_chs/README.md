# LanguageBarrier —— ROBOTICS;NOTES DaSH 简体中文汉化专用改版

> ## ⚠️ 这是 fork，不是上游原件
>
> | | |
> |---|---|
> | **用途** | **ROBOTICS;NOTES DaSH**（MAGES/5pb，Steam 版）**简体中文汉化补丁**的运行时 |
> | **汉化项目** | [Syun1524/RND_Chinese](https://github.com/Syun1524/RND_Chinese) |
> | **fork 自** | [CommitteeOfZero/LanguageBarrier](https://github.com/CommitteeOfZero/LanguageBarrier) |
> | **基准提交** | `cc982fd9`（2025-04-27，"Fix time stamp rendering"） |
> | **本分支** | `rnd-chinese` |
> | **改动规模** | **13 个文件，+1667 / −1064 行** |
>
> `git diff cc982fd9` 即为本项目的完整改动集。
> 改了什么、为什么改，见 **[FORK-NOTES.md](FORK-NOTES.md)**。
>
> **这是专门为汉化制作的版本**：上游 LanguageBarrier 服务 CoZ 的**英化**补丁，
> 本项目在其上加入**中文码表/字体渲染、ruby 注音定位、backlog 名字对齐、
> CJK 断行、引号收窄**等改动。**不要拿它当上游原件用** ——
> 若你的目标是英化补丁，请用 [上游仓库](https://github.com/CommitteeOfZero/LanguageBarrier)。
>
> 上游此后新增了 `Hooking.*` / `NewHooks.*` / `ScriptDebugger.*` / `cryptbase.*`
> 等文件（大重构），**本 fork 尚未跟进** —— 那批改动与中文汉化无关，合并需单独评估。
>
> MIT 许可与版权声明原样保留（见 `LanguageBarrier/LICENSE`）。

---

# LanguageBarrier（上游说明，原文保留）

This is the core runtime component for Committee of Zero's MAGES engine game patches, hooking lots of game engine functions to enable asset access redirection at filesystem and higher levels, rendering changes and many more features.

As we try to support all games and any possible patches with a single binary, extensive external configuration is required (in particular, the hooks here make little sense the signatures pointing to their targets). See the root patch repositories (or patched game installations) for details.

LanguageBarrier source code is [MIT licensed](LanguageBarrier/LICENSE), but due to inclusion of xy-VSFilter, our binaries fall under GPLv2. If this is a problem for you, you must remove the xy-VSFilter dependency by hand.