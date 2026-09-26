# sc3tools —— ROBOTICS;NOTES DaSH 简体中文汉化专用改版

> ## ⚠️ 这是 fork，不是上游原件
>
> | | |
> |---|---|
> | **用途** | **ROBOTICS;NOTES DaSH**（MAGES/5pb，Steam 版）**简体中文汉化补丁**的文本工具 |
> | **汉化项目** | [Syun1524/RND_Chinese](https://github.com/Syun1524/RND_Chinese) |
> | **fork 自** | [CommitteeOfZero/sc3tools](https://github.com/CommitteeOfZero/sc3tools) |
> | **基准提交** | `6ba9278a`（2025-05-22，"Polished charset"） |
> | **本分支** | `rnd-chinese` |
> | **改动** | 3 个源文件 + 新增 `resources/rndzh/` 码表 |
>
> `git diff 6ba9278a` 即为本项目的完整改动集。
> 改了什么、为什么改，见 **[FORK-NOTES.md](FORK-NOTES.md)**。
>
> **这是专门为汉化制作的版本**：新增 `rndzh` game 条目（简体中文码表，4550 字符）
> 与中文管线的三处调整。**上游没有 `rndzh`** —— 若你要处理日文原版脚本，
> 用上游自带的 `rnd` 即可（本 fork 的 `rnd` 与上游行为完全一致）。
>
> MIT 许可与版权声明原样保留（见 `LICENSE`）。

### 本 fork 的用法（中文 / 日文分开）

```bash
sc3tools extract-text "mes00.cpk/*.msb" rnd      # 提日文原版脚本
sc3tools extract-text "enscript/*.msb" rndzh     # 提中文译文
sc3tools replace-text "cnscript/*.msb.txt" rndzh # 回写中文
```

| game | 码表 | 用途 |
|---|---|---|
| `rnd` | 3020 字符（日文原版，**与上游一致**） | 提取日文原版脚本 |
| `rndzh` | **4550 字符**（简体中文，**本 fork 新增**） | 提取 / 回写中文译文 |

> ⚠️ 码表是 `rust-embed` **编译期**打进 exe 的（`#[folder = "resources/"]`，
> **整目录**打包）。改码表、或增删 `resources/` 下任何文件，都必须
> `cargo build --release` 重编 —— 直接跑旧 exe 无效。

---

# sc3tools（上游说明，原文保留）

A CLI tool for extracting and modifying text in .scx and .msb scripts found in visual novels based on MAGES. engine. It's meant to be a replacement for the old, overly complicated tool which had the same name and was part of the now-abandoned [SciAdv.Net project](https://github.com/CommitteeOfZero/SciAdv.Net).

## Supported games

- STEINS;GATE (Steam)
- CHAOS;HEAD Love Chu☆Chu! (PS3 & Impacto)
- ROBOTICS;NOTES ELITE
- STEINS;GATE: Linear Bounded Phenogram (Steam)
- CHAOS;CHILD (Steam & GOG)
- STEINS;GATE 0 (Steam)
- CHAOS;CHILD Love Chu☆Chu!! (PS4 & Impacto)
- ROBOTICS;NOTES DaSH

## Usage

Run `./sc3tools` with no arguments to see the list of the avaliable commands, as well as the list of the supported games and their aliases (such as `sg0` for Steins;Gate 0).

Run `./sc3tools help <command>` to see the help message for a specific command.

Here's an example of how you can extract text from the Robotics;Notes scripts:

`./sc3tools extract-text C:/src/CoZ/rne-msb/*.msb rn`

The output files will be placed in a subfolder named `txt` (in this case, `C:/src/CoZ/rne-msb/txt`).
