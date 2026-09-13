# subs/ — 影片字幕（中文卡拉OK）

5 首歌曲 MV 的中文字幕。构建产物，**同时需要安装进游戏** `languagebarrier/subs/`。

---

## 内容

### 轨道（10 个 `*.ass`）

对应 `patchdef.json` 的 `settings.karaokeSubs` 开关（启动器可选，默认 `all`）：

| 文件 | 用于 | 说明 |
|---|---|---|
| `mv_rnd_ed001.ass` … `mv_rnd_op001.ass` | `all`（默认） | CoZ 英文卡拉OK + **中文翻译行（逐字 `\kf` 高亮）** |
| `mv_rnd_*_tlonly.ass` | `tlonly` | 只有中文翻译行（同样逐字高亮） |
| `mv_rnd_*_karaonly.ass` | `karaonly` | **不在本目录**：CoZ 英文原件，未改动，也不属于我们的产出 |

影片 id 映射：`44`=`ed001`、`45`=`ed002`、`46`=`edfrau`、`47`=`livedance`、`48`=`op001`。

### 字体

- `fonts/RNDLyricSC-Bold.ttf` — 歌词字体，家族名 `RND Lyric SC`。
  由 Noto Sans **SC** Bold 静态实例改名而来（只动 name 表，字形未变）。
  **必须**同时放进 `languagebarrier/subs/fonts/` 并列入 `patchdef.json` 的
  `base.fmv.fonts`，否则 VSFilter 找不到它。
- `fonts/OFL-NotoSansSC.txt` — 上述字体上游的 SIL OFL 1.1 许可（随字体分发）。

### 工具（`tools/`）

与工作区 `scripts/` 下的同名文件**逐字节相同**，改一处必须同步另一处。

| 脚本 | 作用 |
|---|---|
| `build_lyric_subs.py` | 生成中文字幕（从唱词表格 + CoZ 英文模板） |
| `lyric_en_pass.py` | op001 的英文行额外一遍（被 `build_lyric_subs.py` import，**缺了会静默少一层**） |
| `make_lyric_font.py` | 从 `NotoSansSC-Bold-static.ttf` 生成 `RNDLyricSC-Bold.ttf` |
| `_sweep_verify.py` | **验收**：按文本配对「静态底行 ↔ 逐字扫过层」，查窗口/文本/扫过时长 |

> 旧接口的三个脚本（`_karaoke_test.py` / `_karaoke_verify.py` / `_karaoke_accept.py`）
> 已删除：它们调用的是改名前就废弃的 `karaoke_entry()`，且按**行序**配对，
> 遇到 op001 的英文插行会整段错位、报出成片假故障。验收一律用 `_sweep_verify.py`。

---

## 重建

需要一个含以下内容的**工作区**（本仓库不含译文表格与英文模板）：

```
<工作区>/
├── 歌词翻译/mv_rnd_*/..._歌词对照.xlsx   ← 译文 + 唱词时间（唯一真源）
├── RND补丁英文成品原版/languagebarrier/subs/  ← 模板（CoZ 英文原件）
└── fonts/NotoSansSC-Bold-static.ttf      ← 字体源（仅重做字体时需要）
```

```bash
# 空跑：打印逐行映射（译文、时间、字体缩放），不写盘
RND_ROOT=<工作区> python subs/tools/build_lyric_subs.py

# 生成并安装（--karaoke 必需，否则出来的是整行静态、没有逐字高亮！）
RND_ROOT=<工作区> RND_GAME=<游戏>/languagebarrier \
  python subs/tools/build_lyric_subs.py --karaoke --write
```

`build_lyric_subs.py` 只改 `translation*` style 行的文本载荷，
**保留** Layer/Start/End/位置/淡入淡出等全部原始字段（不重新计时）。

环境变量：

| 变量 | 缺省值 |
|---|---|
| `RND_ROOT` | 脚本上两级目录 |
| `RND_GAME` | `D:\Ruanjian\Steam\steamapps\common\ROBOTICS;NOTES DaSH -副本\languagebarrier` |

---

## 验收

```bash
RND_ROOT=<工作区> python subs/tools/_sweep_verify.py
```

期望：`problems: 0`（实测 210 对「静态底行 ↔ 逐字扫过层」全部通过）。

---

## 打包前必查

字幕是构建产物，**换代时最容易漏装**（曾导致实机看不到逐字高亮）。装机前确认：

1. 游戏 `languagebarrier/subs/` 下的 10 个文件带 `\kf`（不是整行静态）
2. `RNDLyricSC-Bold.ttf` 在 `subs/fonts/`，且 `patchdef.json` 的
   `base.fmv.fonts` 列了它
3. 数量对得上：带 `\kf` 的应为 196 / 172 / 160 / 293 / 216（按 ed001/ed002/edfrau/livedance/op001）

细节与本次踩坑复盘见 `../docs/CHANGES-影片字幕与卡拉OK.md`。
