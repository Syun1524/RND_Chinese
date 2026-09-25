# 视频汉化（USM 重定向）

本目录存放替换游戏内影片的成品 USM。影片替换走 LanguageBarrier 的
`fileRedirection`（`mgsFileOpenHook` 对 movie 归档同样生效），**不改视频文件本身**、
不需要重打 movie.cpk。

## ★ 当前状态：只替换 dar020 一部（JP 版统一计划已取消）

> **2026-09-14 用户拍板取消「JP 版影片统一」计划**（13 部 JP 原片会让补丁包
> 从 142 MB 涨到 940 MB，体积不可接受）。
> 现在**实际生效的只有 dar020 一部**：`fileRedirection.movie = {"35": 77}`，
> `c0data.cls` 共 **79 行**（下标 77 = `movie_dar020.usm`）。
> 下面「JP 版影片统一」一节保留为**历史记录与重建指南** —— 想恢复随时照表重建，
> 但请注意它描述的不是当前发布状态。

## JP 版影片统一（历史方案，14 部，含 dar020；当前未启用）

英文版 movie.cpk 把 14 个 fileId 的内容换成了 `_en` 后缀的独立文件
（OP/ED×3/title/8 部 dar 短片/dar020），fileId 不变、内容不同；
其余 39 部两版逐字节一致（epilogue、livedance 就在其中，无需处理）。

为了「英文版游戏也显示日文版影片」，把日文母版的 13 部 JP 原片直接打进
c0data（**USM 本来就是合法容器，无需重封**；画面音轨都在里面），
并逐条重定向。加上用户自制的 dar020，movie 归档共 14 条：

| fileId | 文件 | 说明 |
|---|---|---|
| 11,15~20,22 | movie_dar001 / dar005c~h / dar007b | 8 部 dar 短片（JP 版） |
| 35 | movie_dar020.usm | **用户自制**画面 + 原音轨 |
| 44~46,48 | mv_rnd_ed001 / ed002 / edfrau / op001 | OP/ED（JP 版） |
| 49 | mv_rnd_title | 标题片（JP 版） |

`c0data.cls` 第 78~91 行（0 起）= 上表 14 个文件，`patchdef.json →
base.fileRedirection.movie` 的键值均为对应行号（例如 `"35": 78`）。
键 = EN 版 cpk 里 `_en` 文件占据的同一 fileId（两版 fileId 相同），
值 = c0data.cls 行号。

## 重封工具（仅 dar020 用到）

- `scripts/cpk_toc.py` —— 读 MAGES Steam 版 CPK（TOC 被乘法 LCG
  `key=0x655F; key*=0x4115` 逐字节 XOR 混淆，块=`tag(4)+u32 0+u64LE size+数据`），
  输出文件名 → ID 映射。
- `scripts/build_usm.py` —— dar020 专用重封器：保留原 USM 的容器结构
  （全部元数据块与逐帧 24 字节前置头），只替换帧数据、更新块长字段、
  重算 `VIDEO_SEEKINFO`（每 13 帧一条的文件绝对偏移索引）和 CRID 里的
  filesize/avbps。音轨块整段原样复制。
  ⚠️ 写死了 dar020 的参数（258 帧/20 行 seek/CRID 旧值），
  换别的影片要先改这些常量并重新核对结构。

## 已验证 / 待验证

- 已验证：13 部 JP 原片从日文母版 movie.cpk 原样解出（CRID 头校验）；
  dar020 重封件块遍历精确到 EOF、分流出视频=重编码 ES、音轨=原片逐字节
  一致、ffmpeg 全帧零错误解码、seek 表 20 条全部指向 `@SFV` 块魔数；
  deploy_patch 两处游戏安装 cls/c0data/fileRedirection 全部校验通过。
- 待验证：游戏内实际播放。重定向不命中时游戏回落播放原片（EN 片），无副作用。

## 目录内容（当前发布状态）

| 文件 | 说明 |
|---|---|
| `movie_dar020.usm` | **实际进补丁包的那一部**（4.4 MB）。用户自制画面 + 原音轨重封，`fileRedirection.movie = {"35": 77}` |
| `README.md` | 本文件 |

> 13 部 JP 原片**不在本目录**（计划已取消，未随包发布）。
> 若要恢复 JP 版统一，需从日文母版 `movie.cpk` 重新解出，照上面表格重建
> `c0data.cls` 与 `fileRedirection.movie`，并按 AGENTS 记录的代价重新评估体积。

