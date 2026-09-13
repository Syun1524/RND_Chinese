# 影片字幕（卡拉OK）变更记录

记录 2026-09-11 对 **5 首歌曲 MV 的中文字幕**所做的改动。

游戏目录：`D:\Ruanjian\Steam\steamapps\common\ROBOTICS;NOTES DaSH`
字幕目录：`languagebarrier/subs/`

---

## 1. 背景：三套字幕轨道

`patchdef.json` 的 `settings.karaokeSubs`（用户配置 / 启动器开关，默认 `all`）
在三个选项中选一套，靠 `fmv.subs` 映射到影片 id 44–48：

| 选项 | 文件 | 内容 |
|---|---|---|
| `all`（默认） | `mv_rnd_*.ass` | CoZ 英文卡拉OK（日语罗马音 + 英文翻译）+ **中文翻译行** |
| `tlonly` | `mv_rnd_*_tlonly.ass` | 只有中文翻译行 |
| `karaonly` | `mv_rnd_*_karaonly.ass` | 只有 CoZ 英文卡拉OK，**无中文**（CoZ 原件，未改） |

所以中文化只涉及前两套（各 5 个文件，共 10 个）。

---

## 2. 本次改动：中文翻译行改为逐字高亮（`\kf`）

### 做法

中文翻译行原本是**整行静态**文字（一行 `translation` style 的 Dialogue，
时间跨度 10 秒以上）。现改为按每个汉字分配 `\kf`（逐字扫过）时长：

- 每行总时长精确对齐该行的 `Start`–`End` 跨度（余数吸收到末字，不累积误差）
- 唱词表格里的每行给定时长（start/end），字在该区间内均分
- 行首前的静默窗口折进第 1 个字，行间停顿折进前一个字（`\kf` 单位从行首起算）
- **可见文本不变**：把 `{\kf<n>}` 去掉后与改动前的译文逐字相同

### 涉及文件（各 5 个）

```
mv_rnd_ed001.ass / _tlonly.ass
mv_rnd_ed002.ass / _tlonly.ass
mv_rnd_edfrau.ass / _tlonly.ass
mv_rnd_livedance.ass / _tlonly.ass
mv_rnd_op001.ass / _tlonly.ass
```

`_karaonly.ass` 五个文件**未改动**（与 CoZ 英文原件逐字节相同）。

### 顺带的两处样式改动

- `translation*` style 的字体改为 **`RND Lyric SC`**（见 §3）
- 字号 ×1.10（`translation` 45 → 49.5），过宽的行按右边距框单独 `\fs` 压回

---

## 3. 歌词字体：`RNDLyricSC-Bold.ttf`

| 项 | 值 |
|---|---|
| 家族名 | `RND Lyric SC`（weight 700） |
| 来源 | Noto Sans **SC** Bold（静态实例），仅改 name 表 |
| 授权 | SIL OFL 1.1（`subs/fonts/OFL-NotoSansSC.txt`） |
| 位置 | 包内 `languagebarrier/subs/fonts/`；仓库 `subs/fonts/` |

**为什么要改名**：Windows 已注册一个**可变字体**叫 `Noto Sans SC`
（`C:\Windows\Fonts\NotoSansSC-VF.ttf`）。两个字体同名时 GDI/VSFilter 可能选中可变那个，
渲染不可控。改成唯一家族名后匹配确定，字形本身未动。

**接线**：字体文件必须同时在 `subs/fonts/` 下，且列入
`patchdef.json` 的 `base.fmv.fonts`——`CriManaMod` 启动时逐个
`AddFontResourceExA` 给 VSFilter 用。

---

## 4. ⚠ 打包陷阱（本次实际踩到）

**字幕文件是构建产物，换代时极易漏装。** 本次故障经过：

1. `歌词翻译/build/` 里有带 `\kf` 的正确产物（14:53 构建）
2. 但 `成品ing/补丁包/languagebarrier/subs/` 里放的是 **08:18 那批没加
   `--karaoke` 的旧产物**（`\kf` 数 = 0，整行静态）
3. 实机安装的游戏目录正是从这个包装的 → 玩家看不到逐字高亮

**根因**：生成命令漏了 `--karaoke`；且该开关**默认关闭**，漏加不报错，
只是静默产出静态字幕，从文件外表看不出来。

**预防**：

- 生成时**必须**显式带 `--karaoke`：
  ```bash
  python subs/tools/build_lyric_subs.py --karaoke --write
  ```
- 打包后**必须**跑一遍验收（会报出 `\kf` 计数与文本一致性）：
  ```bash
  RND_ROOT=<工作区> python subs/tools/_sweep_verify.py
  ```
- 快速体检（`\kf` 应为 0 才是异常）：
  ```bash
  python - <<'PY'
  import io,os
  S=r"...\languagebarrier\subs"
  for f in sorted(os.listdir(S)):
      if f.endswith('.ass') and 'karaonly' not in f:
          print(f, io.open(os.path.join(S,f),encoding='utf-8-sig').read().count(chr(92)+'kf'))
  PY
  ```

---

## 5. 验证结果（2026-09-11）

| 项 | 结果 |
|---|---|
| 扫过总时长 vs 行跨度（全部 270 行） | 最大偏差 **5 cs**（0.05 秒） |
| 可见文本 vs 译文（去掉 `\kf` 后） | 不一致 **0** 处 |
| `\kf` 计数 | 196 / 172 / 160 / 293 / 216（5 首） |
| 渲染实测 | 用包内 `VSFilter.dll` 离屏渲染，红→绿随时间是单调扫过 |

> 注：旧接口的 `_karaoke_verify.py` / `_karaoke_accept.py` 会各报 2 处
> `mv_rnd_livedance` 的告警，属**误报**——那两条是带 `\N` 手动换行的静态
> 场景台词，检查脚本把 `\N` 当成了标签字符。非真实缺陷。
> 这两个脚本连同 `_karaoke_test.py` 已删除（调用的 `karaoke_entry()` 早已改名，
> 且按行序配对会被 op001 英文插行带偏）；验收统一用 `_sweep_verify.py`。

---

## 6. 相关文件

| 位置 | 内容 |
|---|---|
| 仓库 `subs/` | 10 个中文轨道 + `fonts/`（字体与 OFL）+ `tools/`（生成与验收脚本） |
| 仓库 `subs/README.md` | 用法与重建步骤 |
| 工作区 `歌词翻译/*/...歌词对照.xlsx` | 译文与唱词时间来源（**不在仓库内**） |
| 工作区 `scripts/` | 脚本原版（与 `subs/tools/` 逐字节相同） |
| 仓库 `subs/tools/lyric_en_pass.py` | op001 英文行 pass；`build_lyric_subs.py` 会 import 它 |
| 工作区 `RND补丁英文成品原版/languagebarrier/subs/` | 生成时的模板（CoZ 英文原件） |
